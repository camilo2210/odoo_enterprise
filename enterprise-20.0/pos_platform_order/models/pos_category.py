# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class PosCategory(models.Model):
    _inherit = 'pos.category'

    service_hours_id = fields.Many2one('resource.calendar', string='Service Hours', groups="base.group_system",
        help='Only work for Platform Order. This calendar defines the service hours for this category.',
        default=lambda self: self.env.ref('pos_restaurant.pos_resource_preset', raise_if_not_found=False))
