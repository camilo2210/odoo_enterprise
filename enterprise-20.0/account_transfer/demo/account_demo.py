import time

from odoo import Command, _, models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template(model='account.journal.group', demo=True)
    def _auto_transfer_account_journal_group_demo(self, template_code):
        return {
            'account_transfer.ifrs_group': {
                'name': _("IFRS"),
            },
        }

    @template(model='account.journal', demo=True)
    def _auto_transfer_account_journal_demo(self, template_code):
        return {
            'auto_transfer_journal': {
                'name': _("IFRS Transfers"),
                'code': "IFRSA",
                'type': 'general',
                'show_on_dashboard': False,
                'sequence': 1000,
                'journal_group_id': 'account_transfer.ifrs_group',
            },
        }

    @template(model='account.transfer.model', demo=True)
    def _auto_transfer_account_transfer_model_demo(self, template_code):
        company = self.env.company
        return {
            self.company_xmlid('monthly_model'): {
                'name': _("IFRS rent expense transfer"),
                'date_start': time.strftime('%Y-01-01'),
                'frequency': 'month',
                'journal_id': 'auto_transfer_journal',
                'account_ids': [self._get_demo_account('expense_rent', 'expense', company).id],
                'line_ids': [
                    Command.create({
                        'account_id': self._get_demo_account('expense_rd', 'expense', company).id,
                        'percent': 35.0,
                    }),
                    Command.create({
                        'account_id': self._get_demo_account('expense_sales', 'expense_direct_cost', company).id,
                        'percent': 65.0,
                    }),
                ],
            },
            self.company_xmlid('yearly_model'): {
                'name': _("Yearly liabilites auto transfers"),
                'date_start': time.strftime('%Y-01-01'),
                'frequency': 'year',
                'journal_id': 'auto_transfer_journal',
                'account_ids': [Command.set([
                    self._get_demo_account('current_liabilities', 'liability_current', company).id,
                    self._get_demo_account('payable', 'liability_payable', company).id
                ])],
                'line_ids': [
                    Command.create({
                        'account_id': self._get_demo_account('payable', 'liability_payable', company).id,
                        'percent': 77.5,
                    }),
                    Command.create({
                        'account_id': self._get_demo_account('non_current_liabilities', 'liability_non_current', company).id,
                        'percent': 22.5,
                    }),
                ],
            },
        }
