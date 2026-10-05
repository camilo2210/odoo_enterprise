from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    vehicle_warehouse_ids = fields.Many2many(
        'planning.vehicle.warehouse',
        'planning_vehicle_warehouse_user_rel',
        'user_id', 'vehicle_id',
        string='Vehicle Warehouses',
    )
