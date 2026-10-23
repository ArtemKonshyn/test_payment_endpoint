from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from src.domain.constants import CartStatus, PaymentStatus
from src.infrastructure.models import (
    SQLCart,
    SQLCartItem,
    SQLPayment,
    SQLPaymentMethod,
    SQLProduct,
    SQLUser,
)


class Factory:
    """Creates and commits rows for tests."""

    def __init__(self, session: Session):
        self._session = session

    def user(self) -> SQLUser:
        unique = uuid4().hex[:8]
        return self._save(SQLUser(email=f"user-{unique}@example.com", name=f"User {unique}"))

    def product(self, price="10.00") -> SQLProduct:
        return self._save(SQLProduct(name="Product", price=Decimal(price), currency="USD"))

    def cart(self, user: SQLUser, status=CartStatus.ACTIVE) -> SQLCart:
        return self._save(SQLCart(user_id=user.id, status=status))

    def cart_item(self, cart: SQLCart, product: SQLProduct, quantity=1) -> SQLCartItem:
        return self._save(
            SQLCartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.price,
            )
        )

    def payment_method(self, user: SQLUser, provider_token="tok_test_visa", is_default=True) -> SQLPaymentMethod:
        return self._save(
            SQLPaymentMethod(user_id=user.id, provider_token=provider_token, is_default=is_default)
        )

    def payment(self, cart: SQLCart, payment_method: SQLPaymentMethod, status=PaymentStatus.PENDING) -> SQLPayment:
        return self._save(
            SQLPayment(
                cart_id=cart.id,
                user_id=cart.user_id,
                payment_method_id=payment_method.id,
                amount=Decimal("10.00"),
                currency="USD",
                status=status,
                idempotency_key=uuid4().hex,
            )
        )

    def _save(self, instance):
        self._session.add(instance)
        self._session.commit()
        return instance
