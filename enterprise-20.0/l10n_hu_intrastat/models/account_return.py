from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_hu_intrastat.hu_intrastat_goods_return_type':
            return date_to + relativedelta(days=15)
        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_hu_intrastat.hu_intrastat_goods_return_type':
            return {
                'name': self.env._("Contact Data"),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'l10n_hu_intrastat.intrastat.goods.contact.wizard',
                'target': 'new',
                'context': {
                    'default_company_id': self.env.company.id,
                    'default_return_id': self.id
                }
            }
        return super()._prepare_submission()
