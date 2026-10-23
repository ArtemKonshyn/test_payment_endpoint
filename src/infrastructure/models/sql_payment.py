from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.constants import FINISHED_PAYMENT_STATUSES
from src.infrastructure.databases.sql_alchemy import sqlalchemy_db as db
from src.infrastructure.models.sql_payment_method import SQLPaymentMethod


class SQLPayment(db.Model):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    cart_id: Mapped[UUID] = mapped_column(ForeignKey("carts.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    payment_method_id: Mapped[UUID] = mapped_column(ForeignKey("user_payment_methods.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str]
    idempotency_key: Mapped[str]
    provider_charge_id: Mapped[str | None]
    failure_reason: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    payment_method: Mapped[SQLPaymentMethod] = relationship()

    @property
    def is_finished(self) -> bool:
        return self.status in FINISHED_PAYMENT_STATUSES
