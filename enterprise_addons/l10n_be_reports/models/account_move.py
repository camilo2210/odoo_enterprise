from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_open_journal_report_tax_journal_items(self):
        params = {
            'name': 'Taxes Applied',
            'tax_type': 'tax',
        }
        date_options = {}
        if audit_id := self.env.context.get('working_file_id'):
            audit = self.env['account.return'].browse(audit_id)
            date_options = {
                'date': {
                    'date_from': audit.date_from,
                    'date_to': audit.date_to,
                    'range': 'custom',
                    'mode': 'range',
                }
            }
        options = self.env.ref("account_reports.journal_report").get_options(date_options)
        return self.env['account.journal.report.handler'].journal_report_action_open_tax_journal_items(options, params)
