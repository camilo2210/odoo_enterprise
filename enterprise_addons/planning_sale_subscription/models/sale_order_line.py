from datetime import datetime, time, timedelta

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _planning_slot_generation(self):
        super()._planning_slot_generation()
        recurring_sol = self.filtered(lambda sol: sol.product_id.recurring_invoice and sol.order_id.plan_id and sol.order_id.is_subscription)
        if recurring_sol:
            recurring_sol.mapped('planning_slot_ids').sudo().write({'state':  '1_draft'})

    def _planning_slot_values(self):
        vals = super()._planning_slot_values()
        order = self.order_id
        recurring_invoice = self.filtered(lambda sol: sol.product_id.recurring_invoice)
        if not order.plan_id or not recurring_invoice or not order.is_subscription or not vals.get('allocated_hours'):
            return vals

        if order.commitment_date:
            start_datetime = datetime.combine(order.commitment_date, time(8, 0, 0))
        elif order.start_date:
            start_datetime = datetime.combine(order.start_date, time(8, 0, 0))
        else:
            start_datetime = datetime.combine(fields.Datetime.now(), time(8, 0, 0))
        max_hours_per_day = self.env.company.resource_calendar_id.hours_per_day or 8
        allocated_hours = vals['allocated_hours']
        if allocated_hours < max_hours_per_day:
            end_datetime = start_datetime + timedelta(hours=allocated_hours)
        else:
            end_datetime = start_datetime + timedelta(days=allocated_hours // max_hours_per_day, hours=allocated_hours % max_hours_per_day)
        vals.update({
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'repeat': True,
            'repeat_type': 'until' if self.subscription_end_date else 'forever',
            'repeat_until': self.subscription_end_date,
            'repeat_unit': self.subscription_plan_id.billing_period_unit,
            'repeat_interval': self.subscription_plan_id.billing_period_value,
        })
        return vals
