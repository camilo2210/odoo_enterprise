# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    use_iot_box = fields.Boolean("IoT Box")
    iot_printer_id = fields.Many2one(
        'iot.device',
        domain=lambda self: [
            ('type', '=', 'printer'),
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id),
        ]
    )
    iot_display_id = fields.Many2one(
        'iot.device',
        domain=lambda self: [
            ('type', '=', 'display'), '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
        ],
    )
    iot_scanner_ids = fields.Many2many(
        'iot.device',
        domain=lambda self: [
            ('type', '=', 'scanner'), '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
        ],
        help="Enable barcode scanning with a remotely connected barcode scanner and card swiping with a Vantiv card reader."
    )
    iot_scale_id = fields.Many2one(
        'iot.device',
        domain=lambda self: [
            ('type', '=', 'scale'), '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
        ],
    )
    iot_device_ids = fields.Many2many('iot.device', compute="_compute_iot_device_ids")

    @api.depends('iot_printer_id', 'iot_display_id', 'iot_scanner_ids', 'iot_scale_id', 'receipt_printer_ids', 'preparation_printer_ids')
    def _compute_iot_device_ids(self):
        for config in self:
            printer_devices = config.receipt_printer_ids.mapped('iot_device_id') + config.preparation_printer_ids.mapped('iot_device_id')
            if config.use_iot_box:
                config.iot_device_ids = (
                    config.iot_printer_id
                    + config.iot_display_id
                    + config.iot_scanner_ids
                    + config.iot_scale_id
                    + printer_devices
                )
            else:
                config.iot_device_ids = printer_devices or False

            config.iot_device_ids += config.payment_method_ids.mapped('iot_device_id')
