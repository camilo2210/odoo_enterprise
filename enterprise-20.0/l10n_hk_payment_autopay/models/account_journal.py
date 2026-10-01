# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _default_outbound_payment_methods(self):
        res = super()._default_outbound_payment_methods()
        if self._is_payment_method_available("l10n_hk_mri"):
            res |= self.env.ref('l10n_hk_payment_autopay.account_payment_method_l10n_hk_mri')
        return res

    l10n_hk_autopay_payment_set_code = fields.Char(
        string="Payment Set Code",
        help="Three-letter code used to identify the payment set.",
    )
    l10n_hk_autopay_party_ref = fields.Char(
        string="Party Reference",
        help="Free format text field to record a party reference.",
    )
