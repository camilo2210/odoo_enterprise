from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def write(self, vals):
        if vals.get('end_date'):
            self._cancel_shift_recurrence(vals.get('end_date'))
        if vals.get('plan_id'):
            self._update_shift_recurrence(vals.get('plan_id'))
        return super().write(vals)

    def _cancel_shift_recurrence(self, end_date):
        for subscription in self.filtered('is_subscription'):
            if subscription.end_date != end_date:
                subscription.order_line.sudo().planning_slot_ids.action_cancel_recurrence(fields.Datetime.to_datetime(end_date))

    def _update_shift_recurrence(self, plan_id):
        recurring_plan = plan_id if not isinstance(plan_id, int) else self.env['sale.subscription.plan'].browse(plan_id)
        for subscription in self.filtered('is_subscription'):
            if subscription.plan_id != recurring_plan:
                subscription.order_line.sudo().planning_slot_ids.action_update_recurrence(recurring_plan)

    def _action_cancel(self):
        for subscription in self.filtered('is_subscription'):
            subscription.order_line.sudo().planning_slot_ids.action_cancel_recurrence(fields.Datetime.now())
        return super()._action_cancel()
