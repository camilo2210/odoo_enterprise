from odoo import fields, models

FISCAL_TEMPLATE_VARIABLES = {
    'gross goodwill': ('l10n_fr_reports.l10n_fr_2033_A', 'l10n_fr_fonds_commercial', 'brut_round'),
    'gross inventory': ('l10n_fr_reports.l10n_fr_2033_A', 'l10n_fr_stock', 'brut_round'),
    'share capital': ('l10n_fr_reports.l10n_fr_2033_A', 'l10n_fr_capital', 'net_round'),
    'extraordinary income': ('l10n_fr_reports.l10n_fr_2033_B', 'FR_2033_B_c290', 'balance'),
    'extraordinary expenses': ('l10n_fr_reports.l10n_fr_2033_B', 'FR_2033_B_c300', 'balance'),
    'research tax credit': ('l10n_fr_reports.l10n_fr_2069_RCI', 'l10n_fr_2069_research_credit', 'balance'),
    'average headcount': ('l10n_fr_reports.l10n_fr_2033_E', 'FR_2033_E_376', 'balance'),
}


class AuditReport(models.Model):
    _inherit = 'audit.report'

    def _get_l10n_fr_knowledge_report_data(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code not in self.company_id._get_france_country_codes():
            return {}

        variables_by_report = {}
        for variable_name, (report_xmlid, line_code, expression_label) in FISCAL_TEMPLATE_VARIABLES.items():
            report_variables = variables_by_report.setdefault(report_xmlid, {})
            report_variables[line_code, expression_label] = variable_name

        values = dict.fromkeys(FISCAL_TEMPLATE_VARIABLES, '')
        previous_options = {
            'date': {
                'date_from': fields.Date.to_string(self.start_date),
                'date_to': fields.Date.to_string(self.end_date),
            },
            'forced_companies': self.company_id.ids,
        }
        for report_xmlid, report_variables in variables_by_report.items():
            report = self.env.ref(report_xmlid).with_company(self.company_id)
            options = report.get_options(previous_options)
            for line in report._get_lines(options):
                for column in line.columns:
                    variable_name = report_variables.get((line.code, column.expression_label))
                    if variable_name:
                        values[variable_name] = column.name or ''
        return values
