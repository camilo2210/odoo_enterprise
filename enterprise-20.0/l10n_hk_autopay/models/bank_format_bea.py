# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class L10nhkBankFormatBea(models.AbstractModel):
    """
    Supports exporting batch payments in the Bank Of East Asia supported formats.
    Note that we do not support the notification lines at the moment.
    """
    _inherit = 'l10n_hk.bank.format'

    @api.model
    def _validate(self, file_format, payload):
        if file_format == 'l10n_hk_bea_csv':
            errors = []
            if not payload.get('batches'):
                errors.append(self.env._('The payment export payload is missing the payments information.'))
            if len(payload.get('batches', [])) > 1:
                errors.append(self.env._('You can only pay one batch at a time when using the BOC format.'))
            if any(payment["autopay_account_type"] != 'bban' for payment in payload["batches"][0]["payments"]):
                errors.append(self.env._('BEA csv export only support the bban account type.'))
            return errors

        return super()._validate(file_format, payload)

    @api.model
    def _generate(self, file_format, payload):
        if file_format == "l10n_hk_bea_csv":
            return self._generate_bea_csv_file(payload)

        return super()._generate(file_format, payload)

    def _generate_bea_csv_file(self, payload):
        entries = []
        batch = payload["batches"][0]
        entries.append(self._generate_bea_csv_batch_control_record(batch['header']))
        for payment in batch['payments']:
            entries.append(self._generate_bea_csv_entry_detail(payment))

        document_name = payload.get("document_name", "AutoPay")
        return "\r\n".join(entries).encode('utf-8'), '.csv', self._prepare_file_name('BEA', document_name)

    def _generate_bea_csv_batch_control_record(self, headers):
        return str(headers["nb_payments"])

    def _generate_bea_csv_entry_detail(self, payment):
        bank_account = payment["bank_account"]
        bank_code = bank_account._get_clearing_number('HK')
        holder_name = bank_account.holder_name or ""
        account_proxy_id = bank_account.sanitized_account_number

        return ",".join([
            str((payment.get('reference') or '')[:35]),                      # Transaction ref
            str((bank_code + account_proxy_id)[:37]),                        # Account Number
            str(holder_name[:140]),                                          # Account name
            f"{payment["amount"]:.2f}",                                      # Amount
        ])
