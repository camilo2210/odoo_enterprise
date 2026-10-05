from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    l10n_gt_final_consumer_limit = fields.Monetary(
        currency_field='currency_id',
        default=2499,
    )
    is_guatemalan_company = fields.Boolean(compute='_compute_is_guatemalan_company')

    @api.depends('company_id')
    def _compute_is_guatemalan_company(self):
        for config in self:
            config.is_guatemalan_company = config.company_id.country_code == 'GT'

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records and config.is_guatemalan_company:
            read_records[0]['_consumidor_final_id'] = self.env.ref('l10n_gt_edi.final_consumer').id
        return read_records

    def get_limited_partners_loading(self, offset=0):
        partner_ids = super().get_limited_partners_loading(offset)
        if self.is_guatemalan_company:
            final_consumer_id = self.env.ref('l10n_gt_edi.final_consumer').id
            if (final_consumer_id,) not in partner_ids:
                partner_ids.append((final_consumer_id,))
        return partner_ids
