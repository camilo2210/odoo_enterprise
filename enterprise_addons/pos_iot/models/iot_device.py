# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class IotDevice(models.Model):
    _name = 'iot.device'
    _inherit = ['iot.device', 'pos.load.mixin']

    associated_pos_config_ids = fields.Many2many(
        'pos.config', string="Associated PoS", compute='_compute_associated_pos_config_ids'
    )

    @api.model
    def _load_pos_data_domain(self, data):
        return [('id', 'in', data['pos.config'].iot_device_ids.ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['iot_ip', 'iot_id', 'identifier', 'type', 'name']

    @api.depends('type')
    def _compute_associated_pos_config_ids(self):
        """Find PoS configs where this device is used, or PoS configs
        that have a payment method using this device."""
        pos_config = self.env['pos.config']
        field_map = {
            'scanner': ('iot_scanner_ids', 'in'),
            'printer': ('iot_printer_id', '='),
            'display': ('iot_display_id', '='),
            'scale': ('iot_scale_id', '='),
        }

        if 'iot_fdm_be_id' in pos_config._fields:
            field_map['fiscal_data_module'] = ('iot_fdm_be_id', '=')
        elif 'iot_fdm_se_id' in pos_config._fields:
            field_map['fiscal_data_module'] = ('iot_fdm_se_id', '=')

        for device in self:
            pm_device_ids = self.env['pos.payment.method'].search([('iot_device_id', '=', device.id)]).mapped('config_ids')
            field, operator = field_map.get(device.type, (None, None))

            if not field:
                device.associated_pos_config_ids = pm_device_ids
                continue

            domain = Domain(['&', ('use_iot_box', '=', True), (field, operator, device.id)])
            device.associated_pos_config_ids = pos_config.search(domain) + pm_device_ids
