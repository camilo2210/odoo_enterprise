from ast import literal_eval

from odoo import api, fields, models
from odoo.fields import Domain


class MailActivitySchedule(models.TransientModel):
    _inherit = "mail.activity.schedule"

    employee_id = fields.Many2one(
        "hr.employee",
        compute="_compute_employee_id",
        store=False,
        readonly=False,
    )
    employee_id_domain = fields.Char(
        compute="_compute_employee_id_domain",
        export_string_translation=False,
    )

    @api.depends_context("voip_log_contact_id")
    def _compute_employee_id_domain(self):
        if not self.env.user.has_group("hr.group_hr_user"):
            # keep an always-empty domain: the user has no access to employees
            self.employee_id_domain = Domain.FALSE
            return
        if contact_id := self.env.context.get("voip_log_contact_id"):
            contact = self.env["res.partner"].browse(contact_id)
            domain = [
                ("id", "in", contact.employee_ids.ids),
                ("company_id", "in", self.env.companies.ids),
            ]
        else:
            domain = []
        self.employee_id_domain = domain

    def _get_res_model_fields(self):
        return {**super()._get_res_model_fields(), "hr.employee": "employee_id"}

    def _selection_res_model(self):
        res = super()._selection_res_model()
        if self.env.user.has_group("hr.group_hr_user"):
            res += [("hr.employee", self.env._("Employee"))]
        return res

    @api.depends("res_model_selection", "employee_id_domain")
    def _compute_employee_id(self):
        for activity in self:
            if activity.employee_id or activity.res_model_selection != "hr.employee":
                continue
            domain = literal_eval(activity.employee_id_domain)
            activity.employee_id = self.env.context.get("default_employee_id") or activity.env["hr.employee"].search(
                domain, limit=1,
            )

    def _get_partner_from_target(self):
        if self.res_model == "hr.employee":
            employee = self._get_applied_on_records()
            return employee.work_contact_id
        return super()._get_partner_from_target()
