from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.models import SQLPaymentMethod


class PaymentMethodRepository:

    def __init__(self, session: Session):
        self._session = session

    def find_default(self, user_id: UUID) -> SQLPaymentMethod | None:
        query = select(SQLPaymentMethod).where(
            SQLPaymentMethod.user_id == user_id, SQLPaymentMethod.is_default.is_(True)
        )
        return self._session.scalars(query.limit(1)).first()
