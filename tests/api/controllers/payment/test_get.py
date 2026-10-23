from http import HTTPStatus
from uuid import uuid4

from src.domain.constants import PaymentStatus


def test_returns_payment_of_user(client, factory, checkout, auth_headers):
    payment = factory.payment(checkout.cart, checkout.payment_method, status=PaymentStatus.SUCCEEDED)

    response = client.get(f"/payments/{payment.id}", headers=auth_headers(checkout.user))

    assert response.status_code == HTTPStatus.OK
    assert response.json["id"] == str(payment.id)
    assert response.json["status"] == PaymentStatus.SUCCEEDED


def test_payment_of_other_user_returns_404(client, factory, checkout, auth_headers):
    payment = factory.payment(checkout.cart, checkout.payment_method)

    response = client.get(f"/payments/{payment.id}", headers=auth_headers(factory.user()))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_unknown_payment_returns_404(client, checkout, auth_headers):
    response = client.get(f"/payments/{uuid4()}", headers=auth_headers(checkout.user))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_requires_token(client, factory, checkout):
    payment = factory.payment(checkout.cart, checkout.payment_method)

    response = client.get(f"/payments/{payment.id}")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
