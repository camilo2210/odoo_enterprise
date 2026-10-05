from odoo import api, fields, models


class IotDevice(models.Model):
    _inherit = 'iot.device'

    qcp_test_type = fields.Char(compute='_compute_qcp_test_type')
    quality_point_ids = fields.One2many('quality.point', 'device_id')

    @api.depends('type')
    def _compute_qcp_test_type(self):
        types = {'device': 'measure', 'scale': 'measure', 'camera': 'picture'}
        for device in self:
            device.qcp_test_type = types.get(device.type, '')
