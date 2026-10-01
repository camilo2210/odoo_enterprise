# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'pos.load.mixin']

    pos_order_ids = fields.One2many('pos.order', 'sale_order_id', string="Point of Sale Orders", readonly=True, groups="point_of_sale.group_pos_user")
    pos_order_resource_count = fields.Integer(string='Pos Order Resource Count', compute='_count_pos_order_resource', readonly=True, groups="point_of_sale.group_pos_user")

    def _count_pos_order_resource(self):
        for order in self:
            order.pos_order_resource_count = len(order.pos_order_ids)

    def action_view_pos_order_resource(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Orders'),
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.pos_order_ids.ids)],
        }
