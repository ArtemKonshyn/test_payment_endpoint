from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from src.domain.constants import LIVE_PAYMENT_STATUSES, UNFINISHED_PAYMENT_STATUSES
from src.infrastructure.models import SQLPayment


class PaymentRepository:

    def __init__(self, session: Session):
        self._session = session

    def create(self, **fields) -> SQLPayment:
        payment = SQLPayment(**fields)
        self._session.add(payment)
        self._session.flush()
        return payment

    def find_for_user(self, payment_id: UUID, user_id: UUID) -> SQLPayment | None:
        query = select(SQLPayment).where(SQLPayment.id == payment_id, SQLPayment.user_id == user_id)
        return self._session.scalars(query).one_or_none()

    def find_by_idempotency_key(self, user_id: UUID, idempotency_key: str) -> SQLPayment | None:
        query = select(SQLPayment).where(
            SQLPayment.user_id == user_id, SQLPayment.idempotency_key == idempotency_key
        )
        return self._session.scalars(query).one_or_none()

    def find_for_update(self, payment_id: UUID) -> SQLPayment | None:
        query = select(SQLPayment).where(SQLPayment.id == payment_id).with_for_update()
        return self._session.scalars(query).one_or_none()

    def has_live_payment(self, cart_id: UUID) -> bool:
        query = select(
            exists().where(SQLPayment.cart_id == cart_id, SQLPayment.status.in_(LIVE_PAYMENT_STATUSES))
        )
        return self._session.scalar(query)

    def find_unfinished_ids(self, updated_before: datetime) -> list[UUID]:
        query = select(SQLPayment.id).where(
            SQLPayment.status.in_(UNFINISHED_PAYMENT_STATUSES),
            SQLPayment.updated_at < updated_before,
        )
        return list(self._session.scalars(query))
