"""Base schema of the online shop, as given in the task (without sample data).

Revision ID: 0001
Revises:
Create Date: 2026-10-23
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_STATEMENTS = (
    'CREATE EXTENSION IF NOT EXISTS "pgcrypto"',
    """
    CREATE TABLE users (
        id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        email      TEXT        NOT NULL UNIQUE,
        name       TEXT        NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE products (
        id             UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
        name           TEXT           NOT NULL,
        price          NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
        currency       CHAR(3)        NOT NULL DEFAULT 'USD',
        stock_quantity INTEGER        NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
        created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
        updated_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE carts (
        id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    UUID        NOT NULL REFERENCES users(id),
        status     TEXT        NOT NULL DEFAULT 'active'
                               CHECK (status IN ('active', 'checked_out', 'abandoned')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX idx_carts_user_id ON carts(user_id)",
    """
    CREATE TABLE cart_items (
        id         UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
        cart_id    UUID           NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
        product_id UUID           NOT NULL REFERENCES products(id),
        quantity   INTEGER        NOT NULL CHECK (quantity > 0),
        unit_price NUMERIC(12, 2) NOT NULL,
        created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX idx_cart_items_cart_id ON cart_items(cart_id)",
    """
    CREATE TABLE user_payment_methods (
        id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id        UUID        NOT NULL REFERENCES users(id),
        provider_token TEXT        NOT NULL,
        last_four      CHAR(4),
        is_default     BOOLEAN     NOT NULL DEFAULT FALSE,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX idx_user_payment_methods_user_id ON user_payment_methods(user_id)",
)


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE user_payment_methods, cart_items, carts, products, users")
