from flask import Flask

from src.api.authentication import setup_jwt
from src.api.controllers.payment import blueprint as payment_blueprint
from src.celery_app import setup_celery
from src.cors import setup_cors
from src.dependency_container import setup_dependency_container
from src.error_handler import setup_error_handler
from src.infrastructure.databases.sql_alchemy import setup_sqlalchemy
from src.management import setup_management


def create_app(config) -> Flask:
    app = Flask(__name__.split(".")[0])
    app.config.from_object(config)
    app.url_map.strict_slashes = False

    setup_sqlalchemy(app)
    setup_jwt(app)
    setup_cors(app)
    setup_celery(app)
    setup_dependency_container(app)
    app.register_blueprint(payment_blueprint)
    setup_error_handler(app)
    setup_management(app)
    return app
