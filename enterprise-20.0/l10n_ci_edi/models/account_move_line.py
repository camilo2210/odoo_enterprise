from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_ci_edi_fne_item_id = fields.Char(string='FNE Item ID', copy=False)

    def _copy_data_extend_business_fields(self, values):
        # EXTENDS 'account'
        super()._copy_data_extend_business_fields(values)
        values['l10n_ci_edi_fne_item_id'] = self.l10n_ci_edi_fne_item_id
