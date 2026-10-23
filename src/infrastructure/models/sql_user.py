from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.databases.sql_alchemy import sqlalchemy_db as db


class SQLUser(db.Model):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str]
    name: Mapped[str]
