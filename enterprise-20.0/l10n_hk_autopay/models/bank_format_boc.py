# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, release


class L10nhkBankFormatBoc(models.AbstractModel):
    """
    Supports exporting batch payments in the Bank Of China Hong Kong supported format.
    Note that we do not support the notification lines at the moment.
    """
    _inherit = 'l10n_hk.bank.format'

    @api.model
    def _validate(self, file_format, payload):
        if file_format == 'l10n_hk_boc':
            errors = []
            if not payload.get('batches'):
                errors.append(self.env._('The payment export payload is missing the payments information.'))
            if len(payload.get('batches', [])) > 1:
                errors.append(self.env._('You can only pay one batch at a time when using the BOC format.'))
            payment_code = payload["batches"][0]["header"].get("payment_code") or "001"
            if not payment_code.isdigit() or not (1 <= int(payment_code) <= 100):
                errors.append(self.env._('For BOCHK Payment Type files, the Payment Code must be a number between 001 and 100.'))
            return errors

        return super()._validate(file_format, payload)

    @api.model
    def _generate(self, file_format, payload):
        if file_format == "l10n_hk_boc":
            return self._generate_boc_file(payload)

        return super()._generate(file_format, payload)

    def _generate_boc_file(self, payload):
        entries = []
        batch = payload["batches"][0]
        for payment in batch['payments']:
            entries.append(self._generate_boc_entry_detail(payment))
        entries.append(self._generate_boc_batch_control_record(batch['header']))

        document_name = payload.get("document_name", "AutoPay")
        return "\r\n".join(entries).encode('utf-8'), '.dat', self._prepare_file_name('BOCHK_PAYMENT', document_name)

    def _generate_boc_entry_detail(self, payment):
        bank_account = payment["bank_account"]
        bank_code = bank_account._get_clearing_number('HK') if payment["autopay_account_type"] == 'bban' else ""
        holder_name = bank_account.holder_name or ""
        account_proxy_id = bank_account.sanitized_account_number if payment["autopay_account_type"] == 'bban' else payment["account_proxy_id"]

        return "".join([                                                    # Total length: 373
            "1",                                                            # Control Code (Length 1)
            f"{bank_code + account_proxy_id:<34}",                          # Account Number (Length 34) - For bban, first 3 digits is the bank code
            f"{holder_name[:140]:<140}",                                    # Account name (Length 140)
            f"{payment["amount"]:>16.2f}",                                  # Amount (Length 16)
            f"{(payment.get('reference') or '')[:35]:<35}",                 # Debtor Reference (Length 35)
            f"{'':<140}",                                                   # Remark (Length 140)
            payment["autopay_account_type"].upper(),                        # Account Type (Length 4)
            f"{bank_code[:3]:<3}",                                          # Second Party Bank Code (Length 3)
        ])

    def _generate_boc_batch_control_record(self, headers):
        bank_account = headers["bank_account"]
        holder_name = bank_account.holder_name or ""
        return ''.join([                                                    # Total length: 212
            "FRPT",                                                         # Control Code (Length 4)
            f"{bank_account.sanitized_account_number:<14}",                 # Originating account number. Must be BOCHK account. (Length 14)
            f"{holder_name[:140]:<140}",                                    # Account name (Length 140)
            f"{headers["currency"]:<3}",                                    # Currency (Length 3)
            f"{headers["effective_date"]:%Y%m%d}",                          # Effective Date (Length 8)
            f"{headers["nb_payments"]:07}",                                 # Total Quantity (Length 7)
            f"{headers["amount_total"]:>16.2f}",                            # Total Amount (Length 16)
            f"{(headers.get('payment_code') or '001')[:3]:0>3}",            # Payment Type Number (Length 3)
            f"{release.version[:10]:<10}",                                  # Software version number (Length 10)
            f"{'':<7}",                                                     # Filler (Length 7)
        ])
