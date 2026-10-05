# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_pos_iot_worldline = fields.Boolean("Worldline Payment Terminal", help="The transactions are processed by Worldline via an IoT box. Setup your terminal on the related payment method.")
    module_pos_iot_six = fields.Boolean("Six Payment Terminal", help="The transactions are processed by Six via an IoT box. Setup your terminal on the related payment method.")

    # pos.config fields
    pos_use_iot_box = fields.Boolean(related='pos_config_id.use_iot_box', readonly=False)
    pos_iot_display_id = fields.Many2one(related='pos_config_id.iot_display_id', readonly=False)
    pos_iot_printer_id = fields.Many2one(related='pos_config_id.iot_printer_id', readonly=False)
    pos_iot_scale_id = fields.Many2one(related='pos_config_id.iot_scale_id', readonly=False)
    pos_iot_scanner_ids = fields.Many2many(related='pos_config_id.iot_scanner_ids', readonly=False)
