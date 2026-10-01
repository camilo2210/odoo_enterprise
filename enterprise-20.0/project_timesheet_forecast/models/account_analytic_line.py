from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    @api.model_create_multi
    def create(self, vals_list):
        analytic_lines = super().create(vals_list)
        analytic_lines.filtered('project_id')._recompute_planning_slots()
        return analytic_lines

    def write(self, vals):
        res = super().write(vals)
        if 'date' in vals or 'unit_amount' in vals or 'employee_id' in vals:
            self.filtered('project_id')._recompute_planning_slots()
        return res

    def _recompute_planning_slots(self):
        if not self:
            return
        dates = self.mapped('date')
        min_date = min(dates)
        max_date = max(dates)
        task_ids = self.task_id.ids
        if not all(t.task_id for t in self):
            task_ids.append(False)
        slots = self.env['planning.slot'].search([
            ('project_id', 'in', self.project_id.ids),
            ('employee_ids', 'in', self.employee_id.ids),
            ('start_datetime', '<=', max_date),
            ('end_datetime', '>=', min_date),
            ('task_id', 'in', task_ids),
        ])
        if slots:
            slots.invalidate_recordset(['timesheet_ids'])
            self.env.add_to_compute(slots._fields['effective_hours'], slots)

    @api.model
    def _get_assistant_odoo_models(self):
        return {
            **super()._get_assistant_odoo_models(),
            "planning.slot": {
                "label": self.env._("Configuring Planning Slots"),
                "target": {
                    "type": "field",
                    "target_model": "project.project",
                    "field": "project_id",
                },
            },
        }

    @api.model
    def _get_assistant_events_getters(self):
        def get_planning_slots(start, end):
            res = []
            dict_working_hours_per_employee_calendar = {}
            now = fields.Datetime.now()
            end_domain = end
            if now.date() == start.date():
                end_domain = now
            for slot in self.env["planning.slot"].search_read(
                domain=[
                    ("resource_ids.user_id", "=", self.env.user.id),
                    ("start_datetime", "<", end_domain),
                    ("end_datetime", ">=", start),
                ],
                fields=["role_id", "name", "start_datetime", "end_datetime", "allocated_hours", "project_id"],
                order="start_datetime",
            ):
                # by default the maximum for a suggested timesheet is 24 hours.
                slot["max_hours"] = 24
                if not self.env.user.employee_id.sudo()._is_flexible(fields.Date.to_date(start)):
                    empl_calendar = self.env.user.employee_resource_calendar_id
                    if empl_calendar not in dict_working_hours_per_employee_calendar:
                        dict_working_hours_per_employee_calendar[empl_calendar] = empl_calendar.get_work_hours_count(
                            start, end)
                    working_hours = dict_working_hours_per_employee_calendar[empl_calendar]
                    if not working_hours:
                        continue
                    slot["max_hours"] = working_hours
                elif self.env.user.employee_id.resource_calendar_id.hours_per_day:
                    slot["max_hours"] = self.env.user.employee_id.resource_calendar_id.hours_per_day
                slot["start"] = slot.pop("start_datetime")
                slot["stop"] = slot.pop("end_datetime")
                slot["duration"] = slot.pop("allocated_hours")
                slot["type"] = "meeting"
                slot["res_model"] = "planning.slot"

                name = slot.get("name") or ""
                role_name = slot.get("role_id")[1] if slot.get("role_id") else None
                slot["name"] = (
                    name
                    if 0 < len(name) <= 64
                    else role_name or self.env._("%(truncated_name)s...", truncated_name=name[:64]) or self.env._("Shift")
                )

                if project := slot.get("project_id"):
                    slot["_res_model"] = "project.project"
                    slot["_res_id"] = project[0]
                res.append(slot)

            return res

        return [
            *super()._get_assistant_events_getters(),
            {
                "sequence": 20,
                "getter": get_planning_slots,
            },
        ]
