from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

INTERVAL_TYPE = {
    'minutes': relativedelta(minutes=1),
    'hour': relativedelta(hours=1),
    'day': relativedelta(days=1),
    'week': relativedelta(days=7),
    'month': relativedelta(months=1),
    False: relativedelta(0),
}


class AIAutomationTrigger(models.Model):
    _name = "ai.automation.trigger"
    _description = "AI Automation Trigger"

    automation_id = fields.Many2one(
        "base.automation",
        string="Automation",
        ondelete="cascade",
        index="btree_not_null",
    )
    prev_trigger_date = fields.Datetime(string="Last Trigger Date", compute="_compute_prev_trigger_date")
    next_trigger_date = fields.Datetime(string="Next Trigger Date", required=True, default=fields.Datetime.now)

    @api.depends('next_trigger_date', 'automation_id.trg_date_range', 'automation_id.trg_date_range_type')
    def _compute_prev_trigger_date(self):
        for trigger in self:
            trigger.prev_trigger_date = (
                trigger.next_trigger_date - INTERVAL_TYPE[trigger.automation_id.trg_date_range_type] * trigger.automation_id.trg_date_range
                if trigger.next_trigger_date else False
            )

    def _advance_next_trigger_date(self):
        """Move `next_trigger_date` to the next slot the rule has not fired yet.
        Based on the `trigger_interval` and `trigger_interval_type` fields of the
        automation.
        """
        now = fields.Datetime.now()
        for trigger in self:
            interval = INTERVAL_TYPE[trigger.automation_id.trg_date_range_type] * trigger.automation_id.trg_date_range
            if not interval:
                continue
            next_date = trigger.next_trigger_date or now
            while next_date <= now:
                next_date += interval
            trigger.next_trigger_date = next_date
