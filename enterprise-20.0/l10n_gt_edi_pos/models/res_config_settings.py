from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_l10n_gt_final_consumer_limit = fields.Monetary(
        related='pos_config_id.l10n_gt_final_consumer_limit',
        readonly=False,
    )
