from odoo import models


class AccountProfitAndLossReportHandler(models.AbstractModel):
    _name = 'account.profit.and.loss.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = "Profit And Loss Custom Handler"

    def action_audit_cell(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])

        action = report.action_audit_cell(options, params)

        if options.get('multi_currency'):
            date_from, date_to = report._get_date_bounds_info(options, 'strict_range')
            action['context'].update({
                'currency_translation': report.currency_translation,
                'date_from': date_from,
                'date_to': date_to,
            })
            action['views'] = [(self.env.ref('account_reports.view_multi_currency_report_audit').id, 'list')]

        return action
