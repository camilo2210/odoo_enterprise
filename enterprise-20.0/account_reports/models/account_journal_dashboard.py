from odoo import models, fields

import ast


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _fill_general_dashboard_data(self, dashboard_data):
        super()._fill_general_dashboard_data(dashboard_data)

        for journal in self.filtered(lambda j: j.type == 'general'):
            is_return_journal = journal == journal.company_id.account_tax_return_journal_id
            dashboard_data[journal.id]['is_account_return_journal'] = is_return_journal

            if not is_return_journal:
                continue

            closest_return = self.env['account.return'].search_read(
                domain=[
                    *self.env['account.return']._check_company_domain(journal.company_id),
                    ('type_id.category', '=', 'account_return'),
                    ('is_completed', '=', False),  # Use = False for clearer intent
                ],
                fields=['date_deadline'],
                limit=1,
                order='date_deadline ASC',
            )

            if not closest_return:
                color = 'primary'  # invite the user to generate the returns by setting the account opening date
            else:
                deadline = closest_return[0]['date_deadline']
                today = fields.Date.context_today(self)

                if deadline < today:
                    color = 'danger'
                elif (deadline - today).days < 7:
                    color = 'warning'
                else:
                    color = 'secondary'

            dashboard_data[journal.id]['tax_return_button_color'] = color
            dashboard_data[journal.id]['tax_return_button_label'] = self.env._("Tax Returns")

    def action_open_bank_balance_in_gl(self):
        ''' Show the bank balance inside the General Ledger report.
        :return: An action opening the General Ledger.
        '''
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account_reports.action_account_report_general_ledger")

        action['context'] = dict(ast.literal_eval(action['context']), default_filter_accounts=self.default_account_id.code)

        return action
