from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ec_pos_consumer_final_limit = fields.Monetary(related="pos_config_id.l10n_ec_consumer_final_limit", readonly=False)
