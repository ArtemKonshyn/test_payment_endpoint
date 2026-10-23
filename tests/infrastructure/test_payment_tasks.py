from src.domain.constants import PaymentStatus
from src.infrastructure.tasks.payment_tasks import PROVIDER_UNAVAILABLE_REASON, process_payment


def test_payment_fails_when_provider_stays_unavailable(session, factory, checkout):
    broken_card = factory.payment_method(checkout.user, provider_token="tok_test_unavailable")
    payment = factory.payment(checkout.cart, broken_card)

    # Runs eagerly: every retry runs at once until max_retries is reached.
    process_payment.apply(args=[str(payment.id)])

    session.refresh(payment)
    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_reason == PROVIDER_UNAVAILABLE_REASON


def test_successful_payment_task(session, checkout, factory):
    payment = factory.payment(checkout.cart, checkout.payment_method)

    process_payment.apply(args=[str(payment.id)])

    session.refresh(payment)
    assert payment.status == PaymentStatus.SUCCEEDED
