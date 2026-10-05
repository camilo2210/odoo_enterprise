# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools import SQL


class SaleOrderLogReport(models.Model):
    _inherit = 'sale.order.log.report'

    referrer_id = fields.Many2one('res.partner', 'Referrer', readonly=True)
    commission_plan_id = fields.Many2one('commission.plan', readonly=True)

    def _select(self):
        return SQL("""
                %s,
                so.referrer_id AS referrer_id,
                so.commission_plan_id AS commission_plan_id
        """, super()._select())

    def _group_by(self):
        return SQL("""
            %s,
            so.referrer_id,
            so.commission_plan_id
        """, super()._group_by())
