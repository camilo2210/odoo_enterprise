# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class MailMessage(models.Model):
    _inherit = "mail.message"

    def write(self, vals):
        messages = super().write(vals)
        if vals.get("body"):
            tickets = self.env["helpdesk.ticket"].search(
                [
                    ("id", "in", self.filtered(lambda m: m.model == "helpdesk.ticket").mapped("res_id")),
                    ("team_id.use_ai", "=", True),
                ],
            )
            tickets.embedding_status = "dirty"
        return messages
