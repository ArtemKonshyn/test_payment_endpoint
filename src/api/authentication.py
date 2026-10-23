from http import HTTPStatus
from uuid import UUID

from flask import Flask
from flask_jwt_extended import JWTManager, get_jwt_identity

from src.api.responses import create_error_response
from src.domain.exceptions import UnauthorizedException

jwt = JWTManager()


def setup_jwt(app: Flask) -> None:
    jwt.init_app(app)
    jwt.unauthorized_loader(lambda reason: create_error_response(reason, HTTPStatus.UNAUTHORIZED))
    jwt.invalid_token_loader(lambda reason: create_error_response(reason, HTTPStatus.UNAUTHORIZED))
    jwt.expired_token_loader(
        lambda _header, _payload: create_error_response("Token has expired", HTTPStatus.UNAUTHORIZED)
    )


def current_user_id() -> UUID:
    """The user id from the `sub` claim of the token. Call only inside @jwt_required()."""
    try:
        return UUID(get_jwt_identity())
    except ValueError as error:
        raise UnauthorizedException("Token subject is not a valid user id") from error
