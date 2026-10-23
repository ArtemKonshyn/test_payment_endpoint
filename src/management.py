from pathlib import Path

import click
from flask import Flask
from flask_jwt_extended import create_access_token

from src.infrastructure.databases.sql_alchemy import sqlalchemy_db

SEED_FILE = Path(__file__).resolve().parent.parent / "sql" / "seed.sql"


def setup_management(app: Flask) -> None:

    @app.cli.command("seed")
    def seed():
        """Load the sample users, products, carts and cards."""
        with sqlalchemy_db.engine.begin() as connection:
            # no_parameters lets the driver run the whole multi-statement file at once.
            connection.exec_driver_sql(
                SEED_FILE.read_text(), execution_options={"no_parameters": True}
            )
        click.echo("Sample data loaded.")

    @app.cli.command("create-token")
    @click.argument("user_id", type=click.UUID)
    def create_token(user_id):
        """Print an access token for the user. There is no login endpoint in this service."""
        click.echo(create_access_token(identity=str(user_id)))
