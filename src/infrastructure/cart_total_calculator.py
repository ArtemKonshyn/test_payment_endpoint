from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain.ports import CartTotal
from src.infrastructure.models import SQLCartItem, SQLProduct


class SQLCartTotalCalculator:
    """Stand-in for the shop's existing total calculation service.

    The total is the sum of the cart item prices. Taxes, shipping and discounts
    belong to the real service. All products of a cart are assumed to have the
    same currency. An empty cart has a total of 0.
    """

    def __init__(self, session: Session):
        self._session = session

    def calculate(self, cart_id: UUID) -> CartTotal:
        query = (
            select(
                func.coalesce(func.sum(SQLCartItem.quantity * SQLCartItem.unit_price), 0),
                func.max(SQLProduct.currency),
            )
            .join(SQLProduct, SQLProduct.id == SQLCartItem.product_id)
            .where(SQLCartItem.cart_id == cart_id)
        )
        amount, currency = self._session.execute(query).one()
        return CartTotal(amount=amount, currency=currency)
