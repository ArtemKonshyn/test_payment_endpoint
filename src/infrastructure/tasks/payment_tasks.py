from uuid import UUID

from celery import shared_task
from flask import current_app

from src.domain.exceptions import PaymentProviderUnavailableException

MAX_RETRIES = 5
PROVIDER_UNAVAILABLE_REASON = "Payment provider is unavailable"


@shared_task(bind=True, acks_late=True, max_retries=MAX_RETRIES)
def process_payment(self, payment_id: str) -> None:
    service = current_app.container.payment_processing_service()
    try:
        service.process(UUID(payment_id))
    except PaymentProviderUnavailableException as error:
        if self.request.retries >= self.max_retries:
            service.fail(UUID(payment_id), reason=PROVIDER_UNAVAILABLE_REASON)
            return
        raise self.retry(exc=error, countdown=2 ** self.request.retries)


@shared_task
def requeue_stale_payments() -> None:
    """Recover payments that never reached the worker or whose worker died."""
    service = current_app.container.payment_processing_service()
    for payment_id in service.find_stale_payment_ids():
        process_payment.delay(str(payment_id))


class CeleryPaymentTaskQueue:

    def enqueue_processing(self, payment_id: UUID) -> None:
        process_payment.delay(str(payment_id))
