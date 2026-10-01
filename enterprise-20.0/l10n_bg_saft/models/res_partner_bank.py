from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    l10n_bg_saft_registration_number = fields.Char(
        string="Bank Registration Number (BG)",
        help="Unique identification number of the payment operator/electronic \
            money company - EIK for Bulgarian operators, VAT number or other \
            identification number for foreign operators",
    )
