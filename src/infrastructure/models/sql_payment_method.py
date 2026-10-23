from uuid import UUID

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.databases.sql_alchemy import sqlalchemy_db as db


class SQLPaymentMethod(db.Model):
    __tablename__ = "user_payment_methods"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    provider_token: Mapped[str]
    last_four: Mapped[str | None] = mapped_column(String(4))
    is_default: Mapped[bool]
