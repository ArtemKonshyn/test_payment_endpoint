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


class ActiveCartNotFoundException(NotFoundException):
    message = "User has no active cart"


class PaymentNotFoundException(NotFoundException):
    message = "Payment not found"


class CartHasLivePaymentException(ConflictException):
    message = "A payment for the active cart is already in progress"


class EmptyCartException(UnprocessableException):
    message = "Cart is empty"


class PaymentMethodNotFoundException(UnprocessableException):
    message = "User has no payment method"


class PaymentProviderUnavailableException(Exception):
    """The provider could not be reached. The charge is safe to retry."""
