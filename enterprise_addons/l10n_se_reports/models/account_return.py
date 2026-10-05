from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        months_per_period = return_type._get_periodicity_months_delay(company)

        if return_type_external_id in {'l10n_se_reports.se_tax_return_type', 'l10n_se_reports.se_ec_sales_list_return_type'} and not return_type.with_company(company).deadline_days_delay:
            if months_per_period == 1:
                return date_to + relativedelta(days=26)
            elif months_per_period == 3:
                return date_to + relativedelta(days=12) + relativedelta(months=1)
            else:
                return date_to + relativedelta(days=26) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_se_reports.se_tax_return_type':
            return self.env['l10n_se_reports.vat.return.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_se_reports.se_ec_sales_list_return_type':
            return self.env['l10n_se_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        return super()._prepare_submission()
