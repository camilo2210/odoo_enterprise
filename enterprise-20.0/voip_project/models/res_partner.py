from odoo import fields, models

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    commercial_partner_task_count = fields.Integer(
        related="commercial_partner_id.task_count",
        string="Commercial Partner Task Count",
        groups="project.group_project_user",
        related_sudo=False,
    )

    def action_voip_view_tasks(self):
        self.ensure_one()
        return self.commercial_partner_id.action_view_tasks()

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)
        has_access = (
            self.has_field_access(self._fields["commercial_partner_task_count"], "read") and
            self.env["project.task"].has_access("read")
        )
        if has_access:
            res.attr("commercial_partner_task_count")
