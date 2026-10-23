from datetime import timedelta
from enum import StrEnum


class CartStatus(StrEnum):
    ACTIVE = "active"
    CHECKED_OUT = "checked_out"
    ABANDONED = "abandoned"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# A cart can have at most one payment in these statuses (enforced by a partial unique index).
LIVE_PAYMENT_STATUSES = (PaymentStatus.PENDING, PaymentStatus.PROCESSING, PaymentStatus.SUCCEEDED)
UNFINISHED_PAYMENT_STATUSES = (PaymentStatus.PENDING, PaymentStatus.PROCESSING)
FINISHED_PAYMENT_STATUSES = (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED)

# An unfinished payment not touched for this long is handed to the worker again.
STALE_PAYMENT_AGE = timedelta(minutes=2)

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
IDEMPOTENCY_KEY_MAX_LENGTH = 255
