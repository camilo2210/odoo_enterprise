from odoo import api, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        dmfa_id = self.env.context.get('dmfa_id', False)
        if dmfa_id:
            self.env['l10n_be.dmfa'].browse(dmfa_id).payment_id = res[0].id
        return res
