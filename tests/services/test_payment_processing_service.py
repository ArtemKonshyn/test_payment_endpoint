from datetime import datetime, timedelta, timezone

import pytest

from src.domain.constants import STALE_PAYMENT_AGE, CartStatus, PaymentStatus
from src.domain.exceptions import PaymentProviderUnavailableException


@pytest.fixture
def processing_service(app):
    """Run a PaymentProcessingService method inside an app context, like the Celery task does."""

    def run(method_name: str, *args, **kwargs):
        with app.app_context():
            service = app.container.payment_processing_service()
            return getattr(service, method_name)(*args, **kwargs)

    return run


def test_successful_charge_completes_payment_and_cart(session, factory, checkout, processing_service):
    payment = factory.payment(checkout.cart, checkout.payment_method)

    processing_service("process", payment.id)

    session.refresh(payment)
    session.refresh(checkout.cart)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.provider_charge_id.startswith("ch_")
    assert checkout.cart.status == CartStatus.CHECKED_OUT


def test_declined_charge_fails_payment(session, factory, checkout, processing_service):
    declining_card = factory.payment_method(checkout.user, provider_token="tok_test_decline")
    payment = factory.payment(checkout.cart, declining_card)

    processing_service("process", payment.id)

    session.refresh(payment)
    session.refresh(checkout.cart)
    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_reason == "Card declined"
    assert checkout.cart.status == CartStatus.ACTIVE


def test_unavailable_provider_raises_and_keeps_payment_processing(
    session, factory, checkout, processing_service
):
    broken_card = factory.payment_method(checkout.user, provider_token="tok_test_unavailable")
    payment = factory.payment(checkout.cart, broken_card)

    with pytest.raises(PaymentProviderUnavailableException):
        processing_service("process", payment.id)

    session.refresh(payment)
    assert payment.status == PaymentStatus.PROCESSING


def test_finished_payment_is_not_processed_again(session, factory, checkout, processing_service):
    payment = factory.payment(checkout.cart, checkout.payment_method, status=PaymentStatus.FAILED)

    processing_service("process", payment.id)

    session.refresh(payment)
    session.refresh(checkout.cart)
    assert payment.status == PaymentStatus.FAILED
    assert payment.provider_charge_id is None
    assert checkout.cart.status == CartStatus.ACTIVE


def test_fail_marks_payment_failed(session, factory, checkout, processing_service):
    payment = factory.payment(checkout.cart, checkout.payment_method)

    processing_service("fail", payment.id, reason="Payment provider is unavailable")

    session.refresh(payment)
    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_reason == "Payment provider is unavailable"


def test_finds_only_stale_unfinished_payments(session, factory, checkout, processing_service):
    long_ago = datetime.now(timezone.utc) - STALE_PAYMENT_AGE - timedelta(seconds=1)
    stale_pending = factory.payment(checkout.cart, checkout.payment_method)
    stale_processing = factory.payment(factory.cart(checkout.user), checkout.payment_method, PaymentStatus.PROCESSING)
    stale_failed = factory.payment(factory.cart(checkout.user), checkout.payment_method, PaymentStatus.FAILED)
    factory.payment(factory.cart(checkout.user), checkout.payment_method)  # fresh
    for payment in (stale_pending, stale_processing, stale_failed):
        payment.updated_at = long_ago
    session.commit()

    stale_ids = processing_service("find_stale_payment_ids")

    assert set(stale_ids) == {stale_pending.id, stale_processing.id}
