from http import HTTPStatus


class ApiException(Exception):
    """An error that is shown to the API client with its own status code."""

    status_code = HTTPStatus.BAD_REQUEST
    message = "Bad request"

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class UnauthorizedException(ApiException):
    status_code = HTTPStatus.UNAUTHORIZED
    message = "Unauthorized"


class NotFoundException(ApiException):
    status_code = HTTPStatus.NOT_FOUND


class ConflictException(ApiException):
    status_code = HTTPStatus.CONFLICT


class UnprocessableException(ApiException):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY


class InvalidIdempotencyKeyException(ApiException):
    message = "Idempotency-Key header is required and must be at most 255 characters"


class CartNotFoundException(NotFoundException):
    message = "Cart not found"


class PaymentNotFoundException(NotFoundException):
    message = "Payment not found"


class CartNotActiveException(ConflictException):
    message = "Cart is not active"


class CartHasLivePaymentException(ConflictException):
    message = "Cart already has a payment in progress or completed"


class IdempotencyKeyReusedException(ConflictException):
    message = "Idempotency-Key was already used for a different cart"


class EmptyCartException(UnprocessableException):
    message = "Cart is empty"


class PaymentMethodNotFoundException(UnprocessableException):
    message = "User has no default payment method"


class PaymentProviderUnavailableException(Exception):
    """The provider could not be reached. The charge is safe to retry."""
