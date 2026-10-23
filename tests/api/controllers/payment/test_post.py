from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import func, select

from src.domain.constants import CartStatus, PaymentStatus
from src.infrastructure.models import SQLPayment

PAYMENTS_URL = "/payments"


def count_payments(session) -> int:
    return session.scalar(select(func.count()).select_from(SQLPayment))


def test_creates_pending_payment_for_active_cart(client, session, checkout, auth_headers, task_queue):
    response = client.post(PAYMENTS_URL, headers=auth_headers(checkout.user, "key-1"))

    assert response.status_code == HTTPStatus.ACCEPTED
    body = response.json
    assert body["status"] == PaymentStatus.PENDING
    assert body["amount"] == "20.00"
    assert body["currency"] == "USD"
    assert body["cart_id"] == str(checkout.cart.id)
    assert body["payment_method_id"] == str(checkout.payment_method.id)
    assert response.headers["Location"] == f"/payments/{body['id']}"

    payment = session.get(SQLPayment, UUID(body["id"]))
    assert payment.amount == Decimal("20.00")
    assert payment.idempotency_key == "key-1"
    assert task_queue.enqueued == [payment.id]


def test_ignores_carts_that_are_not_active(client, factory, checkout, auth_headers):
    paid_cart = factory.cart(checkout.user, status=CartStatus.CHECKED_OUT)
    factory.cart_item(paid_cart, checkout.product)

    response = client.post(PAYMENTS_URL, headers=auth_headers(checkout.user, "key-1"))

    assert response.json["cart_id"] == str(checkout.cart.id)


def test_repeated_idempotency_key_returns_same_payment(client, session, checkout, auth_headers, task_queue):
    headers = auth_headers(checkout.user, "key-1")
    first = client.post(PAYMENTS_URL, headers=headers)

    second = client.post(PAYMENTS_URL, headers=headers)

    assert second.status_code == HTTPStatus.OK
    assert second.json["id"] == first.json["id"]
    assert count_payments(session) == 1
    assert len(task_queue.enqueued) == 1


def test_repeated_idempotency_key_after_checkout_returns_same_payment(client, session, checkout, auth_headers):
    headers = auth_headers(checkout.user, "key-1")
    first = client.post(PAYMENTS_URL, headers=headers)
    checkout.cart.status = CartStatus.CHECKED_OUT
    session.commit()

    second = client.post(PAYMENTS_URL, headers=headers)

    assert second.status_code == HTTPStatus.OK
    assert second.json["id"] == first.json["id"]


def test_requires_token(client, checkout):
    response = client.post(PAYMENTS_URL, headers={"Idempotency-Key": "key-1"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_rejects_invalid_token(client, checkout):
    headers = {"Authorization": "Bearer not-a-token", "Idempotency-Key": "key-1"}

    response = client.post(PAYMENTS_URL, headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_requires_idempotency_key(client, session, checkout, auth_headers):
    response = client.post(PAYMENTS_URL, headers=auth_headers(checkout.user))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert count_payments(session) == 0


def test_rejects_too_long_idempotency_key(client, checkout, auth_headers):
    response = client.post(PAYMENTS_URL, headers=auth_headers(checkout.user, "k" * 256))

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_user_without_active_cart_returns_404(client, factory, auth_headers):
    user = factory.user()
    factory.payment_method(user)
    factory.cart(user, status=CartStatus.CHECKED_OUT)

    response = client.post(PAYMENTS_URL, headers=auth_headers(user, "key-1"))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_cart_with_live_payment_returns_409(client, session, checkout, auth_headers):
    client.post(PAYMENTS_URL, headers=auth_headers(checkout.user, "key-1"))

    response = client.post(PAYMENTS_URL, headers=auth_headers(checkout.user, "key-2"))

    assert response.status_code == HTTPStatus.CONFLICT
    assert count_payments(session) == 1


def test_cart_with_failed_payment_can_be_paid_again(client, factory, checkout, auth_headers):
    factory.payment(checkout.cart, checkout.payment_method, status=PaymentStatus.FAILED)

    response = client.post(PAYMENTS_URL, headers=auth_headers(checkout.user, "key-1"))

    assert response.status_code == HTTPStatus.ACCEPTED


def test_empty_cart_returns_422(client, factory, auth_headers):
    user = factory.user()
    factory.payment_method(user)
    factory.cart(user)

    response = client.post(PAYMENTS_URL, headers=auth_headers(user, "key-1"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_user_without_payment_method_returns_422(client, factory, auth_headers):
    user = factory.user()
    cart = factory.cart(user)
    factory.cart_item(cart, factory.product())

    response = client.post(PAYMENTS_URL, headers=auth_headers(user, "key-1"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def post_concurrently(app, user, auth_headers, idempotency_keys: list[str]) -> list:
    def pay(idempotency_key: str):
        return app.test_client().post(PAYMENTS_URL, headers=auth_headers(user, idempotency_key))

    with ThreadPoolExecutor(max_workers=len(idempotency_keys)) as executor:
        return list(executor.map(pay, idempotency_keys))


def test_concurrent_requests_with_different_keys_create_one_payment(app, session, checkout, auth_headers):
    responses = post_concurrently(app, checkout.user, auth_headers, ["key-1", "key-2"])

    assert sorted(response.status_code for response in responses) == [HTTPStatus.ACCEPTED, HTTPStatus.CONFLICT]
    assert count_payments(session) == 1


def test_concurrent_requests_with_same_key_return_same_payment(app, session, checkout, auth_headers):
    responses = post_concurrently(app, checkout.user, auth_headers, ["key-1", "key-1"])

    assert sorted(response.status_code for response in responses) == [HTTPStatus.OK, HTTPStatus.ACCEPTED]
    assert responses[0].json["id"] == responses[1].json["id"]
    assert count_payments(session) == 1
