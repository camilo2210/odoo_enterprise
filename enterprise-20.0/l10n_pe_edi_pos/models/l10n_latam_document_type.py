from odoo import api, models


class L10n_LatamDocumentType(models.Model):
    _name = 'l10n_latam.document.type'
    _inherit = ['l10n_latam.document.type', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        return False

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        if self.env.company.country_code == 'PE':
            result += ['report_name']
        return result
