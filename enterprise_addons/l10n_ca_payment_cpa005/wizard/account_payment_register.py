from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    l10n_ca_cpa005_transaction_code_id = fields.Many2one(
        comodel_name="l10n_ca_cpa005.transaction.code",
        string="EFT/CPA transaction code",
        help="Select the option that better represents the type/purpose of the payment. Every payment initiated using the "
        "Canadian EFT service must include a valid CPA code.",
    )

    @api.depends('payment_method_code', 'payment_type')
    def _compute_show_require_partner_bank(self):
        super()._compute_show_require_partner_bank()
        for wizard in self.filtered(lambda w: w.payment_method_code == 'cpa005' and w.payment_type == 'inbound'):
            # Uses the bank account configured on the journal.
            wizard.show_partner_bank_account = False
            wizard.require_partner_bank_account = False

    @api.depends('payment_type', 'payment_method_code', 'currency_id', 'journal_id.bank_account_id')
    def _compute_actionable_errors(self):
        super()._compute_actionable_errors()
        for wizard in self.filtered(lambda w: w.payment_method_code == 'cpa005'):
            actionable_errors = wizard.actionable_errors or {}
            if wizard.currency_id.name not in ('CAD', 'USD'):
                actionable_errors['cpa005_wrong_currency'] = {
                    'message': self.env._("CPA 005 Direct Debit operates in CAD or USD."),
                    'level': 'warning',
                }
            if wizard.payment_type == 'inbound' and not wizard.journal_id.bank_account_id:
                actionable_errors['cpa005_missing_journal_bank'] = {
                    'message': self.env._("Please set a Bank Account on the journal configuration for %s.", wizard.journal_id.display_name),
                    'action_text': self.env._("Configure Journal"),
                    'action': wizard.journal_id._get_records_action(name=self.env._("Journal")),
                    'level': 'warning',
                }
            wizard.actionable_errors = actionable_errors

    def action_create_payments(self):
        for wizard in self.filtered(lambda w: w.payment_method_code == 'cpa005'):
            if wizard.currency_id.name not in ('CAD', 'USD'):
                raise UserError(self.env._("CPA 005 Direct Debit operates in CAD or USD."))
            if wizard.payment_type == 'inbound' and not wizard.journal_id.bank_account_id:
                raise RedirectWarning(
                    self.env._("Please set a Bank Account on the journal configuration for %s.", wizard.journal_id.display_name),
                    wizard.journal_id._get_records_action(name=self.env._("Journal")),
                    self.env._("Configure Journal"),
                )
        return super().action_create_payments()

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals['l10n_ca_cpa005_transaction_code_id'] = self.l10n_ca_cpa005_transaction_code_id.id
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        payment_vals['l10n_ca_cpa005_transaction_code_id'] = self.l10n_ca_cpa005_transaction_code_id.id
        return payment_vals
