from odoo import Command, api, models
import ast


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def action_open_reconciliation_report(self):
        report_action = self.env['account.return.check'].action_audit_report(self.env.context.get('working_file_id'), 'account_reports.action_account_report_bank_reconciliation')
        report_action['context'] = dict(ast.literal_eval(report_action['context']), bank_reconciliation_report_journal_id=self.id)
        return report_action

    @api.model_create_multi
    def create(self, vals_list):
        journals = super().create(vals_list)
        for journal in journals:
            if journal.type != 'cash':
                continue

            journal._create_or_update_be_reco_models_for_cash()

        return journals

    def _create_or_update_be_reco_models_for_cash(self):
        self.ensure_one()

        reco_models = [
            (
                self.env.ref(f'l10n_be_reports.client_reco_model_{self.company_id.id}', raise_if_not_found=False),
                self.env._('Client'),
                f'l10n_be_reports.client_reco_model_{self.company_id.id}',
                self.env.ref(f'account.{self.company_id.id}_a400', raise_if_not_found=False)
            ),
            (
                self.env.ref(f'l10n_be_reports.provider_reco_model_{self.company_id.id}', raise_if_not_found=False),
                self.env._('Provider'),
                f'l10n_be_reports.provider_reco_model_{self.company_id.id}',
                self.env.ref(f'account.{self.company_id.id}_a440', raise_if_not_found=False)
            ),
            (
                self.env.ref(f'l10n_be_reports.private_reco_model_{self.company_id.id}', raise_if_not_found=False),
                self.env._('Private'),
                f'l10n_be_reports.private_reco_model_{self.company_id.id}',
                self.env.ref(f'account.{self.company_id.id}_a489', raise_if_not_found=False) or self.env.ref(f'account.{self.company_id.id}_a4891', raise_if_not_found=False)  # Different account depending if we have the asso or comp chart template
            ),
            (
                self.env.ref(f'l10n_be_reports.daily_cash_receipts_reco_model_{self.company_id.id}', raise_if_not_found=False),
                self.env._('Daily Cash Receipts'),
                f'l10n_be_reports.daily_cash_receipts_reco_model_{self.company_id.id}',
                self.env.ref(f'account.{self.company_id.id}_a7000', raise_if_not_found=False)
            ),
        ]

        for reco_model, name, xml_id, account_id in reco_models:
            if reco_model:
                reco_model.match_journal_ids |= self
                continue

            # Should never happen since those account are in the base belgium template
            if not account_id:
                continue

            self.with_context(foreign_record_to_create=True).env['account.reconcile.model']._load_records([{
                'xml_id': xml_id,
                'values': {
                    'name': name,
                    'company_id': self.company_id.id,
                    'match_journal_ids': [Command.link(self.id)],
                    'line_ids': [Command.create({
                        'account_id': account_id.id,
                    })],
                },
            }])
