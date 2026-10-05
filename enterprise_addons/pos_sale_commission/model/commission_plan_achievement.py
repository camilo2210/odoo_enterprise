# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleCommissionPlanAchievement(models.Model):
    _inherit = 'sale.commission.plan.achievement'

    type = fields.Selection(selection_add=[('amount_sold_pos', "Amount Sold (PoS)"), ('qty_sold_pos', 'Quantity Sold (PoS)')],
                            ondelete={'amount_sold_pos': 'cascade', 'qty_sold_pos': 'cascade'})
