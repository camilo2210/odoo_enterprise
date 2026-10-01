from odoo import models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    def _is_peruvian_national_bank_account(self):
        self.ensure_one()
        return self.bank_bic == 'BANCPEPL' and self._get_clearing_number('PE') == '18'
