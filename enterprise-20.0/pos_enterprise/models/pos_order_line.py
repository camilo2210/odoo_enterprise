# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    preparation_time = fields.Integer("Preparation Time", help="Time to prepare the order line", default=-1, readonly=True)
    service_time = fields.Integer("Service Time", help="Time to serve the order line", default=-1, readonly=True)

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['note', 'customer_note', 'qty']
