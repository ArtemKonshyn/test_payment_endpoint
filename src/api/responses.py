from http import HTTPStatus

from flask import Response, jsonify


def create_error_response(error_message: str, status: HTTPStatus) -> tuple[Response, HTTPStatus]:
    return jsonify({"error_message": error_message}), status
