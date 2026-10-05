from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def action_start_compliance_procedure(self):
        self.ensure_one()
        response = self.account_online_link_id._update_connection_status()

        if audit_uuids := response.get('alert_uuids'):
            return {
                'type': 'ir.actions.act_url',
                'url': self.env['account.online.link']._get_odoofin_url(f'/compliance/{audit_uuids[0]}'),
                'target': 'new',
            }
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        super()._fill_bank_cash_dashboard_data(dashboard_data)
        journals = self.browse(list(dashboard_data.keys()))
        # Fetching now to avoid having one query per journal in the loop bellow
        journals.fetch(['account_online_link_id'])
        payments_per_journal = dict(
            self.env['account.payment']._read_group(
                domain=[
                    ('journal_id', 'in', journals.ids),
                    ('could_initiate_payment', '=', True),
                    ('is_sent', '=', False),
                    ('state', '=', 'draft'),
                ],
                groupby=['journal_id'],
                aggregates=['id:recordset'],
            )
        )
        for journal_id, journal_data in dashboard_data.items():
            journal = self.browse(journal_id)
            if journal.account_online_link_id:
                journal_data['payments_ready_to_pay'] = len(payments_per_journal.get(journal, []))
                journal_data['should_show_compliance_button'] = journal.account_online_link_id.is_in_audit
