# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class L10nhkBankFormatBocNonPayment(models.AbstractModel):
    """
    Supports exporting batch payments in the Bank Of China Hong Kong Non-Payment Type (FPS) format.
    Note that we do not support the notification lines at the moment.
    """
    _inherit = 'l10n_hk.bank.format'

    @api.model
    def _validate(self, file_format, payload):
        if file_format == 'l10n_hk_boc_non_payment':
            errors = []
            if not payload.get('batches'):
                errors.append(self.env._('The payment export payload is missing the payments information.'))
            if len(payload.get('batches', [])) > 1:
                errors.append(self.env._('You can only pay one batch at a time when using the BOC format.'))
            return errors

        return super()._validate(file_format, payload)

    @api.model
    def _generate(self, file_format, payload):
        if file_format == "l10n_hk_boc_non_payment":
            return self._generate_boc_non_payment_file(payload)

        return super()._generate(file_format, payload)

    def _generate_boc_non_payment_file(self, payload):
        entries = []
        batch = payload["batches"][0]
        for payment in batch['payments']:
            entries.append(self._generate_boc_non_payment_entry_detail(payment, batch['header']))
        entries.append(self._generate_boc_non_payment_batch_control_record(batch['header']))

        document_name = payload.get("document_name", "AutoPay")
        return "\r\n".join(entries).encode('utf-8'), '.dat', self._prepare_file_name('BOCHK_NON_PAYMENT', document_name)

    def _generate_boc_non_payment_entry_detail(self, payment, headers):
        bank_account = payment["bank_account"]
        bank_code = bank_account._get_clearing_number('HK') if payment["autopay_account_type"] == 'bban' else ""
        holder_name = bank_account.holder_name or ""
        account_proxy_id = bank_account.sanitized_account_number if payment["autopay_account_type"] == 'bban' else payment["account_proxy_id"]

        return "".join([                                                    # Total length: 372
            f"{bank_code + account_proxy_id:<34}",                          # Account Number (Length 34) - For bban, first 3 digits is the bank code
            f"{holder_name[:140]:<140}",                                    # Account name (Length 140)
            f"{payment["amount"]:>16.2f}",                                  # Amount (Length 16)
            f"{(headers.get('reference') or '')[:35]:<35}",                 # Debtor Reference (Length 35)
            f"{(payment.get('reference') or '')[:140]:<140}",               # Reference (Length 140)
            payment["autopay_account_type"].upper(),                        # Account Type (Length 4)
            f"{bank_code[:3]:<3}",                                          # Second Party Bank Code (Length 3)
        ])

    def _generate_boc_non_payment_batch_control_record(self, headers):
        bank_account = headers["bank_account"]
        holder_name = bank_account.holder_name or ""
        return ''.join([                                                    # Total length: 193
            "CF",                                                           # Control Value (Length 2)
            f"{bank_account.sanitized_account_number:<14}",                 # Originating account number. Must be BOCHK account. (Length 14)
            f"{holder_name[:140]:<140}",                                    # Originating account name (Length 140)
            f"{headers["effective_date"]:%Y%m%d}",                          # Effective Date (Length 8)
            f"{headers["nb_payments"]:06}",                                 # Total Quantity (Length 6)
            f"{headers["amount_total"]:>16.2f}",                            # Total Amount (Length 16)
            f"{'':<7}",                                                     # Reserve (Length 7)
        ])
