from datetime import timedelta

from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_it_intrastat.it_intrastat_goods_return_type':
            return date_to + timedelta(days=25)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)
