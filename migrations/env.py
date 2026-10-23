from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config
fileConfig(config.config_file_name, disable_existing_loggers=False)

# Migrations are written by hand, so there is no target metadata for autogenerate.


def run_migrations_offline() -> None:
    context.configure(url=current_app.config["SQLALCHEMY_DATABASE_URI"], literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = current_app.extensions["migrate"].db.engine
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
