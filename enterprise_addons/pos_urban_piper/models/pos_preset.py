# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class PosPreset(models.Model):
    _inherit = 'pos.preset'

    identification = fields.Selection(
        selection_add=[('online', 'Online Food Delivery')],
        ondelete={
            'online': 'set default',
        },
    )

    def write(self, vals):
        res = super().write(vals)
        if 'pricelist_id' in vals and (online_presets := self.filtered_domain([('identification', '=', 'online')])):
            self.env['pos.urbanpiper.store'].search(
                [('preset_id', 'in', online_presets.ids)]
            )._assign_default_pricelist_to_aggregators()
        return res

    @api.model
    def _load_pos_data_domain(self, data):
        domain = super()._load_pos_data_domain(data)
        if store_preset := data['pos.config'].urbanpiper_store_id.preset_id:
            domain = Domain.OR([
                domain,
                Domain('id', '=', store_preset.id)
            ])
        return domain
