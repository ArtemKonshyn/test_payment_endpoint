from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.models import SQLCart


class CartRepository:

    def __init__(self, session: Session):
        self._session = session

    def find_for_update(self, cart_id: UUID, user_id: UUID) -> SQLCart | None:
        """Lock the user's cart until the transaction ends, so its checkouts run one at a time."""
        query = (
            select(SQLCart)
            .where(SQLCart.id == cart_id, SQLCart.user_id == user_id)
            .with_for_update()
        )
        return self._session.scalars(query).one_or_none()
