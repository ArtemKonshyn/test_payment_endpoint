from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


sqlalchemy_db = SQLAlchemy(model_class=Base)
migrate = Migrate()


def setup_sqlalchemy(app: Flask) -> None:
    sqlalchemy_db.init_app(app)
    migrate.init_app(app, sqlalchemy_db)
