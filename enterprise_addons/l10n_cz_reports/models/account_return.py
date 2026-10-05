from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_cz_reports.cz_tax_return_type':
            return self.env['l10n_cz_reports.tax.return.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_cz_reports.cz_vat_control_statement_return_type':
            return self.env['l10n_cz_reports.vat.control.statement.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_cz_reports.cz_vies_summary_return_type':
            return self.env['l10n_cz_reports.vies.summary.submission.wizard']._open_submission_wizard(self)

        return super()._prepare_submission()

    def _get_company_required_fields(self):
        fields = super()._get_company_required_fields()
        if self.company_id.country_id.code == 'CZ':
            fields.append(self.company_id.l10n_cz_tax_office_id)
        return fields
