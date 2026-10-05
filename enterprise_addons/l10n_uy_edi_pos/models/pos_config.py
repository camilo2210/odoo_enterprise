from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_uy_final_consumer_limit = fields.Monetary(
        string="Consumidor Final Max Amount",
        default=32000,
        help="Maximum POS sale amount for unidentified customers (Consumidor Final, or any customer"
        " missing a valid identification).\n"
        "The legal threshold is 5,000 UI (Res. DGI 531/2022), net of VAT, converted at the UI value"
        " fixed at the prior calendar-year end (2026: ~ UYU 32,117). Update this value yearly.",
    )

    def get_limited_partners_loading(self, offset=0):
        partner_ids = super().get_limited_partners_loading(offset)
        final_consumer = self.env.ref("l10n_uy.partner_cfu", raise_if_not_found=False)
        if self.company_id.account_fiscal_country_id.code == "UY" and final_consumer and (final_consumer.id,) not in partner_ids:
            partner_ids.append((final_consumer.id,))
        return partner_ids

    @api.model
    def _load_pos_data_read(self, records, config):
        data = super()._load_pos_data_read(records, config)
        if data and self.env.company.country_code == "UY":
            data[0]["_l10n_uy_consumidor_final_id"] = self.env.ref("l10n_uy.partner_cfu").id
        return data
