"""Payments for carts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE_STATEMENTS = (
    """
    CREATE TABLE payments (
        id                 UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
        cart_id            UUID           NOT NULL REFERENCES carts(id),
        user_id            UUID           NOT NULL REFERENCES users(id),
        payment_method_id  UUID           NOT NULL REFERENCES user_payment_methods(id),
        -- Snapshot of the total when the payment started.
        amount             NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
        currency           CHAR(3)        NOT NULL,
        status             TEXT           NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'processing', 'succeeded', 'failed')),
        -- Sent by the client in the Idempotency-Key header. Unique per user.
        idempotency_key    TEXT           NOT NULL,
        -- Charge id from the provider, set when the payment succeeds.
        provider_charge_id TEXT,
        failure_reason     TEXT,
        created_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
        updated_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_payments_user_idempotency_key UNIQUE (user_id, idempotency_key)
    )
    """,
    "CREATE INDEX idx_payments_cart_id ON payments(cart_id)",
    # A cart has at most one payment that is in progress or succeeded.
    # Failed payments do not count, so the user can try again.
    """
    CREATE UNIQUE INDEX uq_payments_cart_live ON payments(cart_id)
        WHERE status IN ('pending', 'processing', 'succeeded')
    """,
    # Used by the sweep that finds payments the worker never finished.
    """
    CREATE INDEX idx_payments_unfinished_updated_at ON payments(updated_at)
        WHERE status IN ('pending', 'processing')
    """,
)


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE payments")
