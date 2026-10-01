# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    @api.constrains('clearing_label_id', 'clearing_number')
    def _check_clearing_number(self):
        super()._check_clearing_number()
        for account in self.filtered(lambda b: b.clearing_number):
            if account.clearing_label_id.country_code == 'AE' and (len(account.clearing_number) != 9 or not account.clearing_number.isdigit()):
                raise ValidationError(_("UAE Routing Code Agent should be 9 digits only."))
