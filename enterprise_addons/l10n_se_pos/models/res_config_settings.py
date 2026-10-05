# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_iot_fdm_se_id = fields.Many2one(
        "iot.device",
        compute="_compute_pos_iot_fdm_se_id",
        domain="[('type', '=', 'fiscal_data_module')]",
        store=True,
        readonly=False,
    )

    @api.depends("pos_use_iot_box", "pos_config_id")
    def _compute_pos_iot_fdm_se_id(self):
        for res_config in self:
            res_config.pos_iot_fdm_se_id = (
                res_config.pos_config_id.iot_fdm_se_id if res_config.pos_use_iot_box else False
            )
