# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.fields import Domain
from odoo.tools import SQL

from odoo.addons.sale_subscription.models.sale_order import SUBSCRIPTION_STATES


class SaleSubscriptionReport(models.Model):
    _name = 'sale.subscription.report'
    _inherit = ["sale.report"]
    _description = "Subscription Analysis"
    _auto = False

    client_order_ref = fields.Char(string="Customer Reference", readonly=False)
    first_contract_date = fields.Date(string='First contract date', readonly=True)
    end_date = fields.Date('End Date', readonly=True)
    recurring_monthly = fields.Monetary('Monthly Recurring', readonly=True)
    recurring_yearly = fields.Monetary('Yearly Recurring', readonly=True)
    recurring_total = fields.Monetary('Recurring Revenue', readonly=True)
    is_subscription = fields.Boolean(readonly=True)
    template_id = fields.Many2one('sale.order.template', 'Subscription Template', readonly=True)
    country_id = fields.Many2one('res.country', 'Country', readonly=True)
    commercial_partner_id = fields.Many2one('res.partner', 'Customer Company', readonly=True)
    industry_id = fields.Many2one('res.partner.industry', 'Industry', readonly=True)
    close_reason_id = fields.Many2one('sale.order.close.reason', 'Close Reason', readonly=True)
    margin = fields.Float() # not used but we want to avoid creating a bridge module for nothing
    subscription_state = fields.Selection(SUBSCRIPTION_STATES, readonly=True)
    next_invoice_date = fields.Date('Next Invoice Date', readonly=True)
    plan_id = fields.Many2one('sale.subscription.plan', 'Plan', readonly=True)
    origin_order_id = fields.Many2one('sale.order', string='First contract', readonly=True)

    def _order_line_domain(self):
        return super()._order_line_domain() & Domain('order_id.subscription_state', '!=', False)

    def _sql_line_is_recurring(self, table):
        return SQL(
            """(
                %(product_recurring)s
                OR (
                    %(product_id)s IS NULL
                    AND %(display_type)s IS NULL
                    AND %(is_downpayment)s IS NOT TRUE
                    AND %(order_plan_id)s IS NOT NULL
                )
            )""",
            product_recurring=table.product_id.recurring_invoice,
            product_id=table.product_id,
            display_type=table.display_type,
            is_downpayment=table.is_downpayment,
            order_plan_id=table.order_id.plan_id,
        )

    def _select_dict(self, table):
        order_rate = self._case_value_or_one(table.order_id.currency_rate)
        rate = SQL("%s / %s", table.consolidation_rate, order_rate)
        is_recurring = self._sql_line_is_recurring(table)
        return super()._select_dict(table) | {
            'is_subscription': table.order_id.is_subscription,
            'subscription_state': table.order_id.subscription_state,
            'end_date': table.order_id.end_date,
            'first_contract_date': table.order_id.first_contract_date,
            'template_id': table.order_id.sale_order_template_id,
            'close_reason_id': table.order_id.close_reason_id,
            'next_invoice_date': table.order_id.next_invoice_date,
            'plan_id': table.order_id.plan_id,
            'origin_order_id': table.order_id.origin_order_id,
            'client_order_ref': table.order_id.client_order_ref,
            'recurring_monthly': SQL("""
                SUM(CASE WHEN %s THEN %s ELSE 0 END)
                / CASE %s WHEN 'week' THEN 7.0 / 30.437 WHEN 'month' THEN 1 WHEN 'year' THEN 12 ELSE 1 END
                / %s
                * %s""",
                is_recurring,
                table.price_subtotal,
                table.order_id.plan_id.billing_period_unit,
                table.order_id.plan_id.billing_period_value,
                rate,
            ),
            'recurring_yearly': SQL("""
                SUM(CASE WHEN %s THEN %s ELSE 0 END)
                / CASE %s WHEN 'week' THEN 7.0 / 30.437 WHEN 'month' THEN 1 WHEN 'year' THEN 12 ELSE 1 END
                / %s * 12
                * %s""",
                is_recurring,
                table.price_subtotal,
                table.order_id.plan_id.billing_period_unit,
                table.order_id.plan_id.billing_period_value,
                rate,
            ),
            'recurring_total': SQL("%s * %s", table.order_id.recurring_total, rate),
        }

    def _groupby_list(self, table):
        return super()._groupby_list(table) + [table.order_id.plan_id.id]

    def action_open_subscription_order(self):
        self.ensure_one()
        if self.order_reference._name == 'sale.order':
            action = self.order_reference._get_associated_so_action()
            action['views'] = [(self.env.ref('sale_subscription.sale_subscription_primary_form_view').id, 'form')]
            action['res_id'] = self.order_reference.id
            return action
        return {
            'res_model': self._name,
            'type': 'ir.actions.act_window',
            'views': [[False, "form"]],
            'res_id': self.id,
        }
