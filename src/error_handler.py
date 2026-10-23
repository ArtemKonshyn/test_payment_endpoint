import logging
from http import HTTPStatus

from flask import Flask
from werkzeug.exceptions import HTTPException

from src.api.responses import create_error_response
from src.domain.exceptions import ApiException

logger = logging.getLogger(__name__)


def setup_error_handler(app: Flask) -> None:

    @app.errorhandler(ApiException)
    def handle_api_exception(error: ApiException):
        return create_error_response(error.message, error.status_code)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        return create_error_response(error.description, error.code)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error: Exception):
        logger.exception("Unhandled exception", exc_info=error)
        return create_error_response("Internal server error", HTTPStatus.INTERNAL_SERVER_ERROR)
