from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_sk_is_bad_debt = fields.Boolean(
        string="Bad Debt",
        default=False,
        help="Mark this correction as bad debt for Slovak VAT Control Statement reporting.",
    )
