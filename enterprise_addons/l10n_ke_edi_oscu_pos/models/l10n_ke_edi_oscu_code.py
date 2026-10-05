from odoo import api, models


class L10nKeOSCUCode(models.Model):
    _name = 'l10n_ke_edi_oscu.code'
    _inherit = ['pos.load.mixin', 'l10n_ke_edi_oscu.code']

    @api.model
    def _load_pos_data_fields(self, config):
        return ['code_type']

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', data['product.product'].l10n_ke_packaging_unit_id.ids)]
