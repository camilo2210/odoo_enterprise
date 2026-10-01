from odoo import models, fields


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    vehicle_mapping_ids = fields.One2many(
        'planning.vehicle.warehouse',
        'warehouse_id',
        string='Vehicle Mappings',
    )
