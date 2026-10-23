from functools import wraps

from flask import request

from src.domain.constants import IDEMPOTENCY_KEY_HEADER, IDEMPOTENCY_KEY_MAX_LENGTH
from src.domain.exceptions import InvalidIdempotencyKeyException


def idempotency_key_required(view):
    """Pass the Idempotency-Key header to the view as `idempotency_key`."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER, "").strip()
        if not idempotency_key or len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise InvalidIdempotencyKeyException()
        return view(*args, idempotency_key=idempotency_key, **kwargs)

    return wrapper
