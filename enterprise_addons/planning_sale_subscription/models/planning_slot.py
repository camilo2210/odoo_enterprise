from odoo import models


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def action_cancel_recurrence(self, close_date):
        recurrencies = self.mapped('recurrency_id')
        recurrencies._delete_slot(close_date)
        recurrencies.write({
            'repeat_until': close_date,
            'repeat_type': 'until',
        })

    def action_update_recurrence(self, recurring_plan):
        recurrencies = self.mapped('recurrency_id')
        recurrencies.write({
            'repeat_unit': recurring_plan.billing_period_unit,
            'repeat_interval': recurring_plan.billing_period_value,
        })
