from marshmallow import Schema, fields


class PaymentSchema(Schema):
    id = fields.UUID()
    cart_id = fields.UUID()
    payment_method_id = fields.UUID()
    status = fields.String()
    amount = fields.Decimal(as_string=True)
    currency = fields.String()
    failure_reason = fields.String(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
