from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"
    _name = "voip.call"

    commercial_partner_task_count = fields.Integer(
        related="partner_id.commercial_partner_task_count",
        groups="project.group_project_user",
        related_sudo=False,
    )

    def action_view_tasks(self):
        self.ensure_one()
        action = self.partner_id.commercial_partner_id.action_voip_view_tasks()
        action["context"]["default_partner_id"] = self.partner_id.id
        return action
