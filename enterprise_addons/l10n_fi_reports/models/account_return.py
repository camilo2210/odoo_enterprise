from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_fi_reports.fi_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(days=12) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _prepare_submission(self):
        # EXTENDS account_reports
        if self.type_external_id == 'l10n_fi_reports.fi_ec_sales_list_return_type':
            return self.env['l10n_fi_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_fi_reports.fi_tax_return_type':
            return self.env['l10n_fi_reports.tax.report.submission.wizard']._open_submission_wizard(self)

        return super()._prepare_submission()
