# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'pos.load.mixin']

    resource_id = fields.Many2one('resource.resource', string="Resource", readonly=True)
