from odoo import fields, models


class AIComposer(models.Model):
    _inherit = 'ai.composer'

    interface_key = fields.Selection(
        selection_add=[
            ("timesheet_assistant_ai", "Summarize timesheet suggestions"),
        ],
        ondelete={
            "timesheet_assistant_ai": "cascade",
        },
    )
