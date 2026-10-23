from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.models import SQLPaymentMethod


class PaymentMethodRepository:

    def __init__(self, session: Session):
        self._session = session

    def find_for_user(self, user_id: UUID) -> SQLPaymentMethod | None:
        """The user's card. Each user is assumed to have exactly one."""
        query = select(SQLPaymentMethod).where(SQLPaymentMethod.user_id == user_id)
        return self._session.scalars(query).first()
