from odoo import models, fields


class GofoodIdempotencyKey(models.TransientModel):
    _name = 'gofood.idempotency.key'
    _description = 'GoFood Idempotency Key'

    key = fields.Char(string='Key', required=True, index=True)

    _key_uniq = models.Constraint(
        'unique(key)',
        'An idempotency key with the same value already exists.',
    )
