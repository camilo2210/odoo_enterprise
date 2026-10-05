# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.fields import Domain
from odoo.tools import SQL


class PlanningAnalysisReport(models.Model):
    _inherit = "planning.analysis.report"

    sale_order_id = fields.Many2one("sale.order", string="Sales Order", readonly=True)
    sale_line_id = fields.Many2one("sale.order.line", string="Sales Order Item", readonly=True)
    # Not using a related as we want to avoid having a depends.
    partner_id = fields.Many2one('res.partner', compute='_compute_partner_id', search='_search_partner_id')
    role_ids = fields.Many2many('planning.role', related="slot_id.role_ids")
    role_product_ids = fields.One2many('product.template', compute='_compute_role_product_ids', search='_search_role_product_ids')

    def _compute_partner_id(self):
        for slot in self:
            slot.partner_id = slot.sale_order_id.partner_id

    def _search_partner_id(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        return [('sale_order_id.partner_id', operator, value)]

    def _compute_role_product_ids(self):
        for slot in self:
            slot.role_product_ids = slot.role_id.product_ids

    @api.model
    def _search_role_product_ids(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        return [('role_id.product_ids', operator, value)]

    @property
    def _table_sql(self):
        return SQL("(%s %s %s %s %s)", self._select(), self._from(), self._join(), self._where(), self._group_by())

    @api.model
    def _select(self):
        return SQL("""%s,
            S.sale_order_id AS sale_order_id,
            S.sale_line_id AS sale_line_id
        """, super()._select())

    @api.model
    def _where(self):
        return SQL("""
            WHERE start_datetime IS NOT NULL
        """)

    @api.model
    def _group_by(self):
        return SQL("%s, S.sale_order_id, S.sale_line_id", super()._group_by())
