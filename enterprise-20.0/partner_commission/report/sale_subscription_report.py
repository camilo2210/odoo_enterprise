# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SaleSubscriptionReport(models.Model):
    _inherit = "sale.subscription.report"

    referrer_id = fields.Many2one('res.partner', 'Referrer', readonly=True)
    commission_plan_id = fields.Many2one('commission.plan', readonly=True)

    def _select_dict(self, table):
        so = table.order_id
        return super()._select_dict(table) | {
            'referrer_id': so.referrer_id,
            'commission_plan_id': so.commission_plan_id,
        }

    def _groupby_list(self, table):
        so = table.order_id
        return [*super()._groupby_list(table), so.referrer_id, so.commission_plan_id]
