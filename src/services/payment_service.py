import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.constants import PaymentStatus
from src.domain.exceptions import (
    ActiveCartNotFoundException,
    CartHasLivePaymentException,
    EmptyCartException,
    PaymentMethodNotFoundException,
    PaymentNotFoundException,
)
from src.domain.ports import CartTotalCalculator, PaymentTaskQueue
from src.infrastructure.models import SQLCart, SQLPayment
from src.infrastructure.repositories.cart_repository import CartRepository
from src.infrastructure.repositories.payment_method_repository import PaymentMethodRepository
from src.infrastructure.repositories.payment_repository import PaymentRepository
from src.services.transaction import transaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartedPayment:
    payment: SQLPayment
    created: bool  # False when the request repeats an earlier Idempotency-Key


class PaymentService:

    def __init__(
        self,
        session: Session,
        payment_repository: PaymentRepository,
        cart_repository: CartRepository,
        payment_method_repository: PaymentMethodRepository,
        cart_total_calculator: CartTotalCalculator,
        payment_task_queue: PaymentTaskQueue,
    ):
        self._session = session
        self._payments = payment_repository
        self._carts = cart_repository
        self._payment_methods = payment_method_repository
        self._total_calculator = cart_total_calculator
        self._task_queue = payment_task_queue

    def start_payment(self, user_id: UUID, idempotency_key: str) -> StartedPayment:
        """Start the payment for the user's active cart."""
        with transaction(self._session):
            # Checked before the cart lookup, so a repeated request still gets its payment after checkout.
            earlier_payment = self._payments.find_by_idempotency_key(user_id, idempotency_key)
            if earlier_payment is not None:
                return StartedPayment(payment=earlier_payment, created=False)

            cart = self._carts.find_active_for_update(user_id)
            if cart is None:
                raise ActiveCartNotFoundException()

            # Checked again under the cart lock: a request with the same key may have committed meanwhile.
            earlier_payment = self._payments.find_by_idempotency_key(user_id, idempotency_key)
            if earlier_payment is not None:
                return StartedPayment(payment=earlier_payment, created=False)

            payment = self._create_pending_payment(cart, idempotency_key)

        self._enqueue(payment.id)
        return StartedPayment(payment=payment, created=True)

    def get_payment(self, user_id: UUID, payment_id: UUID) -> SQLPayment:
        payment = self._payments.find_for_user(payment_id, user_id)
        if payment is None:
            raise PaymentNotFoundException()
        return payment

    def _create_pending_payment(self, cart: SQLCart, idempotency_key: str) -> SQLPayment:
        if self._payments.has_live_payment(cart.id):
            raise CartHasLivePaymentException()

        payment_method = self._payment_methods.find_for_user(cart.user_id)
        if payment_method is None:
            raise PaymentMethodNotFoundException()

        total = self._total_calculator.calculate(cart.id)
        if total.amount <= 0:
            raise EmptyCartException()

        return self._payments.create(
            cart_id=cart.id,
            user_id=cart.user_id,
            payment_method_id=payment_method.id,
            amount=total.amount,
            currency=total.currency,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
        )

    def _enqueue(self, payment_id: UUID) -> None:
        # The payment is already saved. If the queue is down, the stale payment sweep picks it up later.
        try:
            self._task_queue.enqueue_processing(payment_id)
        except Exception:
            logger.exception("Could not enqueue payment %s, the stale payment sweep will retry it", payment_id)
