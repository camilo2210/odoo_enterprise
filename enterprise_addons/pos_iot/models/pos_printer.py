# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    iot_device_id = fields.Many2one('iot.device', 'IoT Device', domain="['&', ('type', '=', 'printer'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    printer_type = fields.Selection(
        selection_add=[('iot', 'IoT')],
        ondelete={'iot': 'set default'}
    )

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        result += ['iot_device_id']
        return result

    @api.onchange("iot_device_id")
    def _onchange_iot_device_id(self):
        for printer in self:
            if printer.iot_device_id:
                printer.use_lna = printer.iot_device_id.iot_id.use_lna

    @api.onchange("use_lna")
    def _onchange_use_lna(self):
        """Automatically enable IoT LNA when selecting IoT printer
        and checking LNA checkbox"""
        for printer in self:
            if printer.printer_type == "iot" and printer.iot_device_id:
                printer.iot_device_id.iot_id.use_lna = printer.use_lna
