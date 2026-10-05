# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class L10nhkBankFormatHsbc(models.AbstractModel):
    """
    Supports exporting batch payments in HSBC formats.
    Also handles exporting for Hang Seng, as it uses the same formats.
    """
    _inherit = 'l10n_hk.bank.format'

    @api.model
    def _validate(self, file_format, payload):
        if file_format == 'l10n_hk_mri':
            errors = []
            if not payload.get('batches'):
                errors.append(self.env._('The payment export payload is missing the payments information'))
            else:
                for batch in payload["batches"]:
                    header = batch["header"]
                    bank_account = header["bank_account"]
                    if not bank_account.l10n_hk_account_type:
                        errors.append(self.env._("The First Party Bank Account is missing the HK Account Type."))
                    if not header.get("payment_code"):
                        errors.append(self.env._("Missing Payment Set Code."))
                    if not header.get("reference"):
                        errors.append(self.env._("Missing First Party Reference."))
                    missing_identifier = [payment["bank_account"].holder_name or self.env._("Unknown")
                                           for payment in batch["payments"] if not payment.get("identifier")]
                    if missing_identifier:
                        errors.append(self.env._(
                            "Some employees (%s) are missing an identifier (e.g. HKID or passport number).",
                            ", ".join(missing_identifier),
                        ))
            return errors

        return super()._validate(file_format, payload)

    @api.model
    def _generate(self, file_format, payload):
        if file_format == "l10n_hk_mri":
            return self._generate_mri_file(payload)

        return super()._generate(file_format, payload)

    def _generate_mri_file(self, payload):
        entries = []
        payload["batches"].sort(key=lambda b: b['header']['effective_date'])
        for batch in payload["batches"]:
            entries.append(self._generate_mri_batch_header_record(batch['header']))

            for payment in batch['payments']:
                entries.append(self._generate_mri_entry_detail(payment))

        document_name = payload.get("document_name", "AutoPay")
        return "\r\n".join(entries).encode('utf-8'), '.txt', self._prepare_file_name('HKMRI', document_name)

    def _generate_mri_batch_header_record(self, headers):
        bank_account = headers["bank_account"]
        acc_number = f"{bank_account.sanitized_account_number}{bank_account.l10n_hk_account_type}{headers['currency']}"

        return ''.join([                                                    # Total length: 400
            "PH",                                                           # Payment Header Indicator (Length 2)
            "F",                                                            # Autoplan Code (Length 1) - Currently only supports outbound payments
            f"{(headers.get('payment_code') or '')[:3]:<3}",                # Payment Set Code (Length 3)
            f"{(headers.get('reference') or '')[:12]:<12}",                 # First Party Reference (Length 12)
            f"{headers["effective_date"]:%Y%m%d}",                          # Value Date (Length 8)
            f"{acc_number:<35}",                                            # First Party Current Account Number, Standalone account / BIA (Length 35)
            f"{headers["currency"]:<3}",                                    # Currency, HKD/CNY (Length 3)
            f"{headers["nb_payments"]:07}",                                 # Number of Record (Length 7)
            f"{self._amount_in_cents(headers["amount_total"]):017}",        # Total Amount (Length 17)
            f"{'':<1}",                                                     # Filler (Length 1)
            f"{'':<311}",                                                   # Filler (Length 311)
        ])

    def _generate_mri_entry_detail(self, payment):
        bank_account = payment["bank_account"]
        bank_code = bank_account._get_clearing_number('HK') if payment["autopay_account_type"] == 'bban' else ""
        holder_name = bank_account.holder_name or ""
        account_proxy_id = bank_account.sanitized_account_number if payment["autopay_account_type"] == 'bban' else payment["account_proxy_id"]

        return "".join([                                                    # Total length: 400
            "PD",                                                           # Payment Detail Indicator (Length 2)
            f"{bank_code[:3]:<3}",                                          # Second Party Bank Code (Length 3)
            payment["autopay_account_type"].upper(),                        # Second Party ID Type (Length 4)
            f"{account_proxy_id[:34]:<34}",                                 # Second Party Account/Proxy ID (Length 34)
            f"{self._amount_in_cents(payment["amount"]):017}",              # Amount (Length 17)
            f"{(payment.get('identifier') or '')[:35]:<35}",                # Second Party Identifier (Length 35)
            f"{(payment.get('reference') or '')[:35]:<35}",                 # Second Party Reference (Length 35)
            f"{holder_name[:140]:<140}",                                    # Second Party Bank Account Name (Length 140)
            f"{'':<130}",                                                   # Filler (Length 130)
        ])
