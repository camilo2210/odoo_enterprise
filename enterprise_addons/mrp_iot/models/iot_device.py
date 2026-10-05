# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IotDevice(models.Model):
    _inherit = 'iot.device'

    trigger_ids = fields.One2many('iot.trigger', 'device_id')
