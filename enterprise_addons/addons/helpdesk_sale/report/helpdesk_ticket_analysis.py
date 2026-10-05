# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import SQL


class HelpdeskTicketReportAnalysis(models.Model):
    _inherit = 'helpdesk.ticket.report.analysis'

    sale_order_id = fields.Many2one('sale.order', string='Ref. Sales Order', readonly=True, groups="sales_team.group_sale_salesman,account.group_account_invoice")

    def _select(self):
        return SQL("%s, T.sale_order_id as sale_order_id", super()._select())
