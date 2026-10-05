# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        is_country_germany = self.company_id.country_id.code == 'DE'

        data['conditions']['code_de'] = is_country_germany
        if not is_country_germany:
            return data

        tss_id = self.config_id.l10n_de_fiskaly_tss_id and self.config_id.l10n_de_fiskaly_tss_id.split("|")[0]
        if not tss_id:
            data['conditions']['l10n_de_test_env'] = True
            return data

        if not self.l10n_de_fiskaly_time_start:
            data['conditions']['l10n_de_error'] = True
            return data

        data['extra_data']['tss'] = self._get_tss_values()
        return data

    def _get_tss_values(self):
        self.ensure_one()
        time_start = self.l10n_de_fiskaly_time_start.strftime("%Y-%m-%dT%H:%M:%S.000Z") if self.l10n_de_fiskaly_time_start else None
        time_end = self.l10n_de_fiskaly_time_end.strftime("%Y-%m-%dT%H:%M:%S.000Z") if self.l10n_de_fiskaly_time_end else None
        return [
            {'name': "TSE-Transaktion", 'value': self.l10n_de_fiskaly_transaction_number},
            {'name': "Bonnummer", 'value': self.id},
            {'name': "TSE-Start", 'value': time_start},
            {'name': "TSE-Stop", 'value': time_end},
            {'name': "TSE-Seriennummer", 'value': self.l10n_de_fiskaly_certificate_serial},
            {'name': "TSE-Zeitformat", 'value': self.l10n_de_fiskaly_timestamp_format},
            {'name': "TSE-Signatur", 'value': self.l10n_de_fiskaly_signature_value},
            {'name': "TSE-Hashalgorithmus", 'value': self.l10n_de_fiskaly_signature_algorithm},
            {'name': "TSE-PublicKey", 'value': self.l10n_de_fiskaly_signature_public_key},
            {'name': "Client Serial No.", 'value': self.l10n_de_fiskaly_client_serial_number},
        ]
