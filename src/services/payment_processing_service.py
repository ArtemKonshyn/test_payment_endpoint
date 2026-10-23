import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.constants import STALE_PAYMENT_AGE, CartStatus, PaymentStatus
from src.domain.ports import ChargeRequest, PaymentGateway
from src.infrastructure.models import SQLPayment
from src.infrastructure.repositories.cart_repository import CartRepository
from src.infrastructure.repositories.payment_repository import PaymentRepository
from src.services.transaction import transaction

logger = logging.getLogger(__name__)


class PaymentProcessingService:
    """Charges pending payments. Runs in the background worker.

    Every method is safe to run more than once for the same payment: finished
    payments are skipped, and the provider gets the payment id as its
    idempotency key, so a card is never charged twice.
    """

    def __init__(
        self,
        session: Session,
        payment_repository: PaymentRepository,
        cart_repository: CartRepository,
        payment_gateway: PaymentGateway,
    ):
        self._session = session
        self._payments = payment_repository
        self._carts = cart_repository
        self._gateway = payment_gateway

    def process(self, payment_id: UUID) -> None:
        """Charge the card. Raises PaymentProviderUnavailableException so the caller can retry."""
        with transaction(self._session):
            payment = self._payments.find_for_update(payment_id)
            if payment is None or payment.is_finished:
                return
            self._set_status(payment, PaymentStatus.PROCESSING)
            charge_request = ChargeRequest(
                provider_token=payment.payment_method.provider_token,
                amount=payment.amount,
                currency=payment.currency,
                idempotency_key=str(payment.id),
            )

        # No transaction is open during the call to the provider.
        result = self._gateway.charge(charge_request)

        with transaction(self._session):
            payment = self._payments.find_for_update(payment_id)
            if payment.is_finished:
                return
            if result.succeeded:
                self._complete(payment, result.provider_charge_id)
            else:
                self._fail(payment, result.failure_reason)

    def fail(self, payment_id: UUID, reason: str) -> None:
        """Give up on the payment, for example when the provider stays unavailable."""
        with transaction(self._session):
            payment = self._payments.find_for_update(payment_id)
            if payment is not None and not payment.is_finished:
                self._fail(payment, reason)

    def find_stale_payment_ids(self) -> list[UUID]:
        return self._payments.find_unfinished_ids(updated_before=_now() - STALE_PAYMENT_AGE)

    def _complete(self, payment: SQLPayment, provider_charge_id: str) -> None:
        payment.provider_charge_id = provider_charge_id
        self._set_status(payment, PaymentStatus.SUCCEEDED)

        cart = self._carts.find_for_update(payment.cart_id, payment.user_id)
        cart.status = CartStatus.CHECKED_OUT
        cart.updated_at = _now()
        logger.info("Payment %s succeeded", payment.id)

    def _fail(self, payment: SQLPayment, reason: str) -> None:
        payment.failure_reason = reason
        self._set_status(payment, PaymentStatus.FAILED)
        logger.info("Payment %s failed: %s", payment.id, reason)

    @staticmethod
    def _set_status(payment: SQLPayment, status: PaymentStatus) -> None:
        payment.status = status
        payment.updated_at = _now()


def _now() -> datetime:
    return datetime.now(timezone.utc)
