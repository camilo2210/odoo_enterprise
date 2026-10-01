from odoo import api, fields, models


class IotBox(models.Model):
    _inherit = 'iot.box'

    can_be_kiosk = fields.Boolean(compute='_compute_can_be_kiosk', store=True)
    pos_id = fields.Many2one('pos.config', string='Linked To Point of Sale', index='btree_not_null')

    @api.depends('device_ids.type')
    def _compute_can_be_kiosk(self):
        for record in self:
            device_types = {device.type for device in record.device_ids}
            # Kiosk mode is only available for devices with a display and a keyboard
            record.can_be_kiosk = 'display' in device_types and 'keyboard' in device_types

    @api.onchange('device_ids')
    def _onchange_device_ids(self):
        self._compute_can_be_kiosk()
