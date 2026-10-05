from odoo import api, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.model
    def get_assistant_data(self):
        ai_agent = self.env.ref('ai_timesheet_grid.ai_composer_timesheet_assistant', raise_if_not_found=False).ai_agent_id
        return {
            **super().get_assistant_data(),
            "is_agent_available": bool(ai_agent),
        }
