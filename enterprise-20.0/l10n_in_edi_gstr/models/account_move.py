# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_in_edi_send_invoice(self):
        res = super()._l10n_in_edi_send_invoice()
        if res:
            return res
        if self.l10n_in_edi_status == 'sent':
            response_json = self._get_l10n_in_edi_response_json()
            if irn := response_json.get('Irn'):
                self.l10n_in_irn_number = irn.lower()
        return res
