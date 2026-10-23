from uuid import uuid4

from src.domain.exceptions import PaymentProviderUnavailableException
from src.domain.ports import ChargeRequest, ChargeResult

DECLINE_TOKEN_SUFFIX = "_decline"
UNAVAILABLE_TOKEN_SUFFIX = "_unavailable"


class MockPaymentGateway:
    """Fake payment provider. The end of the card token picks the outcome.

    `..._decline` is declined, `..._unavailable` simulates an outage, and any
    other token succeeds. A real provider also receives the idempotency key and
    does not charge the card twice for the same key.
    """

    def charge(self, request: ChargeRequest) -> ChargeResult:
        if request.provider_token.endswith(UNAVAILABLE_TOKEN_SUFFIX):
            raise PaymentProviderUnavailableException("Payment provider is unavailable")

        if request.provider_token.endswith(DECLINE_TOKEN_SUFFIX):
            return ChargeResult(succeeded=False, failure_reason="Card declined")

        return ChargeResult(succeeded=True, provider_charge_id=f"ch_{uuid4().hex}")
