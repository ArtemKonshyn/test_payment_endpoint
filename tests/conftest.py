from dataclasses import dataclass
from uuid import UUID

import pytest
from dependency_injector import providers
from flask_jwt_extended import create_access_token
from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import TestConfig
from src.create_app import create_app
from src.infrastructure.databases.sql_alchemy import sqlalchemy_db
from src.infrastructure.models import SQLCart, SQLPaymentMethod, SQLProduct, SQLUser
from tests.factories import Factory

TABLES = "payments, cart_items, carts, user_payment_methods, products, users"


class FakePaymentTaskQueue:

    def __init__(self):
        self.enqueued: list[UUID] = []

    def enqueue_processing(self, payment_id: UUID) -> None:
        self.enqueued.append(payment_id)


@dataclass
class Checkout:
    """A user with an active cart (2 x 10.00 USD) and a default card."""

    user: SQLUser
    product: SQLProduct
    cart: SQLCart
    payment_method: SQLPaymentMethod


@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig())
    with app.app_context():
        upgrade()
    return app


@pytest.fixture(scope="session")
def engine(app):
    with app.app_context():
        return sqlalchemy_db.engine


@pytest.fixture
def session(engine):
    """A session for test setup and checks, separate from the one the app uses."""
    with Session(engine, expire_on_commit=False) as session:
        yield session
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))


@pytest.fixture
def factory(session):
    return Factory(session)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def task_queue(app):
    queue = FakePaymentTaskQueue()
    with app.container.payment_task_queue.override(providers.Object(queue)):
        yield queue


@pytest.fixture
def checkout(factory):
    user = factory.user()
    product = factory.product(price="10.00")
    cart = factory.cart(user)
    factory.cart_item(cart, product, quantity=2)
    payment_method = factory.payment_method(user)
    return Checkout(user=user, product=product, cart=cart, payment_method=payment_method)


@pytest.fixture
def auth_headers(app):
    def make_headers(user: SQLUser, idempotency_key: str | None = None) -> dict:
        with app.app_context():
            headers = {"Authorization": f"Bearer {create_access_token(identity=str(user.id))}"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    return make_headers
