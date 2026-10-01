# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    referrer_id = fields.Many2one("res.partner", "Referrer", readonly=True)
    commission_plan_id = fields.Many2one("commission.plan", readonly=True)

    def _select_dict(self, table):
        return super()._select_dict(table) | {
            'referrer_id': table.order_id.referrer_id,
            'commission_plan_id': table.order_id.commission_plan_id,
        }
