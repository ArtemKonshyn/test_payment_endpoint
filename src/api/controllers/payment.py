from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from flask import Blueprint, url_for
from flask_jwt_extended import jwt_required

from src.api.authentication import current_user_id
from src.api.middleware import idempotency_key_required
from src.api.schemas.payment import PaymentSchema
from src.dependency_container import DependencyContainer
from src.services.payment_service import PaymentService

blueprint = Blueprint("payment", __name__)


@blueprint.route("/payments", methods=["POST"])
@jwt_required()
@idempotency_key_required
@inject
def start_payment(
    idempotency_key: str,
    payment_service: PaymentService = Provide[DependencyContainer.payment_service],
):
    started = payment_service.start_payment(user_id=current_user_id(), idempotency_key=idempotency_key)
    status = HTTPStatus.ACCEPTED if started.created else HTTPStatus.OK
    location = url_for(".get_payment", payment_id=started.payment.id)
    return PaymentSchema().dump(started.payment), status, {"Location": location}


@blueprint.route("/payments/<uuid:payment_id>", methods=["GET"])
@jwt_required()
@inject
def get_payment(
    payment_id: UUID,
    payment_service: PaymentService = Provide[DependencyContainer.payment_service],
):
    payment = payment_service.get_payment(user_id=current_user_id(), payment_id=payment_id)
    return PaymentSchema().dump(payment)
