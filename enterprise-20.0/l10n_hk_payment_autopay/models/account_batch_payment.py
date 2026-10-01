# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.exceptions import RedirectWarning, ValidationError


class AccountBatchPayment(models.Model):
    _inherit = "account.batch.payment"

    def _validate_journal_for_autopay(self):
        journal = self.journal_id
        error_msgs = []

        if not journal.bank_account_id:
            error_msgs.append(self.env._("Please set a bank account on the %(journal)s journal."))
        if not journal.l10n_hk_autopay_payment_set_code:
            error_msgs.append(self.env._("Please set a Payment Set Code on the %(journal)s journal."))
        if not journal.l10n_hk_autopay_party_ref:
            error_msgs.append(self.env._("Please set a Party Reference on the %(journal)s journal."))

        payments = self.payment_ids.filtered(lambda p: p.payment_method_code == "autopay")
        bban_payments = payments.filtered(lambda p: p.l10n_hk_autopay_account_type == 'bban')
        if bban_payments:
            if bban_payments.filtered(lambda p: not p.partner_bank_id):
                error_msgs.append(self.env._("Some payments in the %(journal)s batch have no bank account set."))
            if bban_payments.filtered(lambda p: not p.partner_bank_id._get_clearing_number('HK')):
                error_msgs.append(self.env._("Some payments in the %(journal)s batch have a bank account with no bank code set."))

        other_payments = payments - bban_payments
        if other_payments.filtered(lambda p: not p.l10n_hk_autopay_account_proxy_id):
            error_msgs.append(self.env._("Some payments in the %(journal)s batch have no AutoPay Account Proxy ID set."))

        if error_msgs:
            raise RedirectWarning(
                message='\n'.join(error_msgs) % {"journal": journal.display_name},
                action={
                    'views': [(False, 'form')],
                    'res_model': 'account.journal',
                    'type': 'ir.actions.act_window',
                    'res_id': journal.id,
                    'target': 'current',
                },
                button_text=self.env._("Go to the journal"),
            )

    def _get_methods_generating_files(self):
        res = super()._get_methods_generating_files()
        res.append("l10n_hk_mri")
        return res

    def _generate_export_file(self):
        if self.payment_method_code != "l10n_hk_mri":
            return super()._generate_export_file()

        self._validate_journal_for_autopay()
        batches = []
        for date, payments in sorted(self.payment_ids.grouped("date").items()):
            batches.append(
                {
                    "header": {
                        "effective_date": date,
                        "amount_total": sum(payments.mapped("amount")),
                        "bank_account": self.journal_id.bank_account_id,
                        "currency": self.currency_id.name,
                        "nb_payments": len(payments),
                        "payment_code": self.journal_id.l10n_hk_autopay_payment_set_code,
                        "reference": self.journal_id.l10n_hk_autopay_party_ref or "",
                    },
                    "payments": [
                        {
                            "payee_name": payment.partner_id.name,
                            "account_proxy_id": payment.l10n_hk_autopay_account_proxy_id,
                            "autopay_account_type": payment.l10n_hk_autopay_account_type,
                            "amount": payment.amount,
                            "bank_account": payment.partner_bank_id,
                            "identifier": payment.partner_id.name,
                            "reference": payment.name,
                        }
                        for payment in payments
                    ],
                }
            )

        payload = {
            "document_name": f"AutoPay-{self.journal_id.code}",
            "batches": batches,
        }

        errors = self.env["l10n_hk.bank.format"]._validate(self.payment_method_code, payload)
        if errors:
            raise ValidationError("\n".join(errors))

        file_content, file_extension, file_name = self.env["l10n_hk.bank.format"]._generate(self.payment_method_code, payload)
        return {
            "file": file_content,
            "filename": f"{file_name}.{file_extension}",
        }
