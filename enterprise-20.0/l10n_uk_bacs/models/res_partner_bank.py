# -*- coding: utf-8 -*-
import re

from odoo import api, models, _
from odoo.exceptions import UserError


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    def _is_valid_uk_bank_account(self):
        self.ensure_one()

        if self.account_type == 'iban' and self.sanitized_account_number[:2] == 'GB':
            return True
        sort_code_regex = re.compile(r'^\d{2}-?\d{2}-?\d{2}$')
        return (
            bool(self.sanitized_account_number and self.sanitized_account_number.isdigit() and len(self.sanitized_account_number) == 8)
            and bool(self._get_clearing_number('GB') and sort_code_regex.match(self._get_clearing_number('GB')))
        )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_linked_to_ddi(self):
        if self.env['bacs.ddi'].search_count([('partner_bank_id', 'in', self.ids), ('state', '=', 'active')], limit=1):
            raise UserError(_('You cannot delete a bank account linked to an active BACS Direct Debit Instruction.'))
