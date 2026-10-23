from pathlib import Path

from flask import Blueprint, send_from_directory

DOCS_DIRECTORY = Path(__file__).resolve().parents[3] / "docs"

blueprint = Blueprint("docs", __name__)


@blueprint.route("/docs", methods=["GET"])
def swagger_ui():
    """Swagger UI, served by the API itself so it can call the API without CORS."""
    return send_from_directory(DOCS_DIRECTORY, "index.html")


@blueprint.route("/openapi.yaml", methods=["GET"])
def openapi_spec():
    return send_from_directory(DOCS_DIRECTORY, "openapi.yaml", mimetype="application/yaml")
