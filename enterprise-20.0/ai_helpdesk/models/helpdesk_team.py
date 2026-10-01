# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    use_ai = fields.Boolean(string="Enable AI features")
    ticket_similarity_time_range = fields.Selection(
        selection=[
            ("1w", "Last Week"),
            ("3m", "Last 3 Months"),
            ("6m", "Last 6 Months"),
            ("1y", "Last 365 days"),
            ("forever", "Forever"),
        ],
        string="Include Tickets from",
        default="forever",
    )
    ai_agent_id = fields.Many2one(
        "ai.agent",
        string="Agent",
        compute="_compute_ai_agent",
        store=True,
        readonly=False,
    )
    ticket_similarity_threshold = fields.Float(
        string="Similarity Threshold",
        help="How close tickets should be to be considered similar.",
        required=True,
        default=0.45,
    )

    _ticket_similarity_threshold_is_between_0_and_1 = models.Constraint(
        "CHECK(ticket_similarity_threshold >= 0 AND ticket_similarity_threshold <= 1.0)",
        "The ticket similarity threshold must be between 0 and 1.0",
    )

    def write(self, vals):
        result = super().write(vals)
        if vals.get("use_ai"):
            self.env.ref("ai.ir_cron_embed_records")._trigger()
        return result

    @api.depends("use_ai")
    def _compute_ai_agent(self):
        """Initialises AI agent when the `use_ai` flag changes"""
        for team in self:
            if team.use_ai and not team.ai_agent_id:
                team.ai_agent_id = self.env.ref(
                    "ai.ai_default_agent",
                    raise_if_not_found=True,
                )
