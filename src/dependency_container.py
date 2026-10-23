from dependency_injector import containers, providers
from flask import Flask

from src.infrastructure.cart_total_calculator import SQLCartTotalCalculator
from src.infrastructure.databases.sql_alchemy import sqlalchemy_db
from src.infrastructure.gateways.mock_payment_gateway import MockPaymentGateway
from src.infrastructure.repositories.cart_repository import CartRepository
from src.infrastructure.repositories.payment_method_repository import PaymentMethodRepository
from src.infrastructure.repositories.payment_repository import PaymentRepository
from src.infrastructure.tasks.payment_tasks import CeleryPaymentTaskQueue
from src.services.payment_processing_service import PaymentProcessingService
from src.services.payment_service import PaymentService


def setup_dependency_container(app: Flask) -> None:
    app.container = DependencyContainer()


class DependencyContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(packages=["src.api"])

    # The scoped session of Flask-SQLAlchemy: one session per app context.
    session = providers.Object(sqlalchemy_db.session)

    payment_repository = providers.Factory(PaymentRepository, session=session)
    cart_repository = providers.Factory(CartRepository, session=session)
    payment_method_repository = providers.Factory(PaymentMethodRepository, session=session)

    cart_total_calculator = providers.Factory(SQLCartTotalCalculator, session=session)
    payment_gateway = providers.Factory(MockPaymentGateway)
    payment_task_queue = providers.Factory(CeleryPaymentTaskQueue)

    payment_service = providers.Factory(
        PaymentService,
        session=session,
        payment_repository=payment_repository,
        cart_repository=cart_repository,
        payment_method_repository=payment_method_repository,
        cart_total_calculator=cart_total_calculator,
        payment_task_queue=payment_task_queue,
    )
    payment_processing_service = providers.Factory(
        PaymentProcessingService,
        session=session,
        payment_repository=payment_repository,
        cart_repository=cart_repository,
        payment_gateway=payment_gateway,
    )
