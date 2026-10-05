# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    def _l10n_in_get_invalid_ifsc_accounts(self):
        IFSC_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
        return self.filtered(
            lambda bank_account: not IFSC_PATTERN.match(bank_account.bank_bic or '')
        )
