# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class IotBox(models.Model):
    _name = 'iot.box'
    _inherit = ['iot.box', 'pos.load.mixin']

    associated_pos_config_ids = fields.Many2many(
        'pos.config', string="Associated PoS", compute='_compute_associated_pos_config_ids'
    )

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', data['iot.device'].iot_id.ids)]

    @api.model
    def _load_pos_data_dependencies(self):
        return ['iot.device']

    @api.model
    def _load_pos_data_fields(self, config):
        return ['ip', 'name', 'identifier', 'use_lna']

    @api.depends('device_ids')
    def _compute_associated_pos_config_ids(self):
        """Find PoS configs where at least one IoT device of this box is used,
        or PoS configs that have a payment method using a device of this box."""
        for box in self:
            domain = Domain('use_iot_box', '=', True) & Domain.OR(
                Domain(field_name, 'in', box.device_ids.ids)
                for field_name in (
                    'iot_printer_id', 'iot_display_id', 'iot_scale_id', 'iot_scanner_ids'
                )
            )
            box.associated_pos_config_ids = (
                self.env['pos.config'].search(domain)
                + self.env['pos.payment.method'].search([
                    ('iot_device_id', 'in', box.device_ids.ids)
                ]).mapped('config_ids')
            )

    @api.onchange("use_lna")
    def _onchange_use_lna(self):
        """Automatically enable IoT printer LNA when
        enabling LNA on the IoT Box record"""
        for box in self:
            iot_printers = box.device_ids.filtered(lambda p: p.type == "printer")
            self.env["pos.printer"].sudo().search(
                [("printer_type", "=", "iot"), ("iot_device_id", "in", iot_printers.ids)]
            ).use_lna = box.use_lna
