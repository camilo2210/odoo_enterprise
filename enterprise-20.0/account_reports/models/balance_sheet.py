from odoo import models
from odoo.fields import Domain


class AccountBalanceSheetReportHandler(models.AbstractModel):
    _name = 'account.balance.sheet.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = "Balance Sheet Custom Handler"

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        companies = self.env['res.company'].browse(report.get_report_company_ids(options))
        has_cta_expr = any(
            expression.formula == '_report_engine_cumulative_translation_adjustment'
            for line in report.line_ids
            for expression in line.expression_ids
        )
        if report.currency_translation == 'cta' and len(companies.currency_id) > 1 and not has_cta_expr:
            warnings['account_reports.common_possibly_unbalanced_because_cta'] = {}

    def action_audit_cell(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        report_line = self.env['account.report.line'].browse(params['report_line_id'])

        action = report.action_audit_cell(options, params)

        date_from, date_to = report._get_date_bounds_info(options, 'strict_range')
        action['context'].update({
            'currency_translation': report.currency_translation,
            'date_from': date_from,
            'date_to': date_to,
        })

        if options.get('multi_currency'):
            action['views'] = [(self.env.ref('account_reports.view_multi_currency_report_audit').id, 'list')]

        if report_line.code in ('CTA', 'OCI'):
            column_group_options = report._get_column_group_options(options, params.get('column_group_index'))
            action['views'] = [(self.env.ref('account_reports.view_cumulative_translation_adjustment_audit_tree').id, 'list')]
            action['domain'] = Domain.AND([
                report._get_options_domain(column_group_options, 'strict_range'),
                Domain('account_type', 'in', ['equity', 'equity_unaffected', 'income', 'income_other', 'expense_direct_cost', 'expense', 'expense_depreciation', 'expense_other']),
            ])
            action['context'].update({
                'group_by': ['account_type', 'account_id']
            })

        return action

    def _report_engine_cumulative_translation_adjustment(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        cumulative_translation_adjustment = report._compute_cumulative_translation_adjustment(options, date_scope)
        return {
            expression: {k: -v for k, v in cumulative_translation_adjustment.items()}  # opposite sign because OCI are in the liabilities
            for formula, expressions in formulas_dict.items()
            for expression in expressions
        }
