"""Interfaces of the external parts the payment services depend on."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CartTotal:
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class ChargeRequest:
    provider_token: str
    amount: Decimal
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class ChargeResult:
    succeeded: bool
    provider_charge_id: str | None = None
    failure_reason: str | None = None


class CartTotalCalculator(Protocol):
    """The existing service that calculates how much to pay for a cart."""

    def calculate(self, cart_id: UUID) -> CartTotal: ...


class PaymentGateway(Protocol):
    """The external payment provider.

    Declines are returned as a failed ChargeResult. Outages raise
    PaymentProviderUnavailableException. Charging again with the same
    idempotency key must not charge the card twice.
    """

    def charge(self, request: ChargeRequest) -> ChargeResult: ...


class PaymentTaskQueue(Protocol):
    """Hands a payment to the background worker."""

    def enqueue_processing(self, payment_id: UUID) -> None: ...
