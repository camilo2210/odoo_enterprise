from odoo import fields, models, api
from datetime import timedelta


class PosPrepOrder(models.Model):
    _inherit = 'pos.prep.order'

    completion_time = fields.Integer("Completion Time", help="Time in minutes to complete the order (preparation + service time)")

    @api.model
    def _clean_preparation_data(self):
        orders = self.env['pos.prep.order'].search([('write_date', '<=', fields.Datetime.now() - timedelta(days=1))])
        orders.unlink()
        return True

    @api.model
    def update_last_order_change(self, order):
        super().update_last_order_change(order)
        categ = order.lines.product_id.pos_categ_ids
        pdis = self.env['pos.prep.display']._get_preparation_displays(order, categ.ids)
        for display in pdis:
            display._send_load_orders_message(True, '', order.id)
