from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from http import HTTPStatus
from uuid import UUID, uuid4

from sqlalchemy import func, select

from src.domain.constants import CartStatus, PaymentStatus
from src.infrastructure.models import SQLPayment


def payments_url(cart_id) -> str:
    return f"/carts/{cart_id}/payments"


def count_payments(session) -> int:
    return session.scalar(select(func.count()).select_from(SQLPayment))


def test_creates_pending_payment(client, session, checkout, auth_headers, task_queue):
    response = client.post(payments_url(checkout.cart.id), headers=auth_headers(checkout.user, "key-1"))

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



def test_repeated_idempotency_key_returns_same_payment(client, session, checkout, auth_headers, task_queue):
    headers = auth_headers(checkout.user, "key-1")
    first = client.post(payments_url(checkout.cart.id), headers=headers)

    second = client.post(payments_url(checkout.cart.id), headers=headers)

    assert second.status_code == HTTPStatus.OK
    assert second.json["id"] == first.json["id"]
    assert count_payments(session) == 1
    assert len(task_queue.enqueued) == 1


def test_idempotency_key_reused_for_other_cart_returns_409(client, factory, checkout, auth_headers):
    other_cart = factory.cart(checkout.user)
    factory.cart_item(other_cart, checkout.product)
    headers = auth_headers(checkout.user, "key-1")
    client.post(payments_url(checkout.cart.id), headers=headers)

    response = client.post(payments_url(other_cart.id), headers=headers)

    assert response.status_code == HTTPStatus.CONFLICT


def test_requires_token(client, checkout):
    response = client.post(payments_url(checkout.cart.id), headers={"Idempotency-Key": "key-1"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_rejects_invalid_token(client, checkout):
    headers = {"Authorization": "Bearer not-a-token", "Idempotency-Key": "key-1"}

    response = client.post(payments_url(checkout.cart.id), headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_requires_idempotency_key(client, session, checkout, auth_headers):
    response = client.post(payments_url(checkout.cart.id), headers=auth_headers(checkout.user))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert count_payments(session) == 0


def test_rejects_too_long_idempotency_key(client, checkout, auth_headers):
    response = client.post(payments_url(checkout.cart.id), headers=auth_headers(checkout.user, "k" * 256))

    assert response.status_code == HTTPStatus.BAD_REQUEST



def test_unknown_cart_returns_404(client, checkout, auth_headers):
    response = client.post(payments_url(uuid4()), headers=auth_headers(checkout.user, "key-1"))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_cart_of_other_user_returns_404(client, factory, checkout, auth_headers):
    other_user = factory.user()

    response = client.post(payments_url(checkout.cart.id), headers=auth_headers(other_user, "key-1"))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_cart_not_active_returns_409(client, factory, checkout, auth_headers):
    paid_cart = factory.cart(checkout.user, status=CartStatus.CHECKED_OUT)
    factory.cart_item(paid_cart, checkout.product)

    response = client.post(payments_url(paid_cart.id), headers=auth_headers(checkout.user, "key-1"))

    assert response.status_code == HTTPStatus.CONFLICT


def test_cart_with_live_payment_returns_409(client, session, checkout, auth_headers):
    client.post(payments_url(checkout.cart.id), headers=auth_headers(checkout.user, "key-1"))

    response = client.post(payments_url(checkout.cart.id), headers=auth_headers(checkout.user, "key-2"))

    assert response.status_code == HTTPStatus.CONFLICT
    assert count_payments(session) == 1


def test_cart_with_failed_payment_can_be_paid_again(client, factory, checkout, auth_headers):
    factory.payment(checkout.cart, checkout.payment_method, status=PaymentStatus.FAILED)

    response = client.post(payments_url(checkout.cart.id), headers=auth_headers(checkout.user, "key-1"))

    assert response.status_code == HTTPStatus.ACCEPTED


def test_empty_cart_returns_422(client, factory, checkout, auth_headers):
    empty_cart = factory.cart(checkout.user)

    response = client.post(payments_url(empty_cart.id), headers=auth_headers(checkout.user, "key-1"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_user_without_payment_method_returns_422(client, factory, auth_headers):
    user = factory.user()
    cart = factory.cart(user)
    factory.cart_item(cart, factory.product())

    response = client.post(payments_url(cart.id), headers=auth_headers(user, "key-1"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY





def test_concurrent_requests_create_one_payment(app, session, checkout, auth_headers):
    def pay(idempotency_key: str) -> int:
        response = app.test_client().post(
            payments_url(checkout.cart.id), headers=auth_headers(checkout.user, idempotency_key)
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        status_codes = sorted(executor.map(pay, ["key-1", "key-2"]))

    assert status_codes == [HTTPStatus.ACCEPTED, HTTPStatus.CONFLICT]
    assert count_payments(session) == 1
