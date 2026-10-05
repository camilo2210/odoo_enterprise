# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    l10n_hk_account_type = fields.Selection([
        ('SA', 'Savings Account'),
        ('CU', 'Current Account'),
    ], string='HK: Account Type', help="Type of the bank account.", default='SA')

    def _compute_sanitized_account_number(self):
        bank_hk = self.filtered(lambda a: a.country_code == 'HK')
        for account in bank_hk:
            if account.account_number:
                account.sanitized_account_number = re.sub(r"\D+", "", account.account_number)
        super(ResPartnerBank, self - bank_hk)._compute_sanitized_account_number()
