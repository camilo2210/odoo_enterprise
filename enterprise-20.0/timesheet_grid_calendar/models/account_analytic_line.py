from collections import defaultdict
from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    @api.model
    def _normalize_events(self, events):
        """
        When an all-day event is present, these events take precedence and the other events are discarded. If more than
        one all-day event is present, the suggested time is evenly distributed between each event.
        """
        allday_events = []
        for event in events:
            if event.get('allday'):
                allday_events.append(event)

        if not allday_events:
            return super()._normalize_events(events)

        average_hour = allday_events[0]['max_hours'] / len(allday_events)
        for event in allday_events:
            event['max_hours'] = average_hour
        return allday_events

    @api.model
    def _get_assistant_calendar_resolve_models_project(self, res_ids_by_model):
        return {}

    @api.model
    def _get_assistant_events_getters(self):
        def get_calendar_events(start, end):
            res = []
            dict_working_hours_per_employee_calendar = {}
            end_domain = end
            now = fields.Datetime.now()
            if now.date() == start.date():
                end_domain = now
            declined_attendees = self.env["calendar.attendee"].search([
                ("partner_id", "=", self.env.user.partner_id.id),
                ("state", "=", "declined"),
                ("event_id.start", "<", end_domain),
                ("event_id.stop", ">=", start),
            ])
            declined_event_ids = declined_attendees.event_id.ids
            domain = [
                "|",
                    ("user_id", "=", self.env.user.id),
                    ("partner_ids", "in", [self.env.user.partner_id.id]),
                ("start", "<", end_domain),
                ("stop", ">=", start),
                ("show_as", "=", "busy"),
                ("res_model", "!=", "hr.leave"),
            ]
            if declined_event_ids:
                domain.append(("id", "not in", declined_event_ids))
            events = self.env["calendar.event"].search_read(
                domain=domain,
                fields=["name", "start", "stop", "duration", "partner_ids", "allday", "res_model", "res_id"],
                order="start",
            )
            user_partner_id = self.env.user.partner_id.id
            all_partner_ids = {
                pid for event in events
                for pid in event["partner_ids"]
                if pid != user_partner_id
                and not event["res_model"]
            }

            partner_recent_project_data = self._get_timesheeted_project_task_by_partner(self.env["res.partner"].browse(all_partner_ids))
            res_ids_by_model = defaultdict(set)
            for event in events:
                if event["res_model"] not in (False, "project.task", "project.project"):
                    res_ids_by_model[event["res_model"]].add(event["res_id"])

            resolve_models_project = (
                self._get_assistant_calendar_resolve_models_project(res_ids_by_model)
                if res_ids_by_model
                else {}
            )

            res = []
            for event in events:
                event["max_hours"] = 24
                if not self.env.user.employee_id.sudo()._is_flexible(fields.Date.to_date(start)):
                    empl_calendar = self.env.user.employee_resource_calendar_id
                    if empl_calendar not in dict_working_hours_per_employee_calendar:
                        dict_working_hours_per_employee_calendar[empl_calendar] = empl_calendar.get_work_hours_count(
                            start, end)
                    working_hours = dict_working_hours_per_employee_calendar[empl_calendar]
                    if not working_hours:
                        continue
                    event["max_hours"] = working_hours
                elif self.env.user.employee_id.resource_calendar_id.hours_per_day:
                    event["max_hours"] = self.env.user.employee_id.resource_calendar_id.hours_per_day

                res_project_id = None
                res_task_id = None
                if event["res_model"] == "project.task":
                    res_task_id = event["res_id"]
                elif event["res_model"] == "project.project":
                    res_project_id = event["res_id"]
                elif event["res_model"] in resolve_models_project:
                    res_project_id = resolve_models_project[event["res_model"]].get(event["res_id"])
                else:
                    event_partners = [pid for pid in event.pop("partner_ids") if pid != user_partner_id]

                    max_date = None
                    for pid in event_partners:
                        project_id, task_id, timesheet_date = partner_recent_project_data.get(pid, (None, None, None))
                        if timesheet_date:
                            if not max_date or timesheet_date > max_date:
                                max_date = timesheet_date
                                res_project_id = project_id
                                res_task_id = task_id
                        elif task_id and (not res_task_id or res_task_id < task_id):
                            res_task_id = task_id
                        elif project_id and (not res_project_id or res_project_id < project_id):
                            res_project_id = project_id

                event.update({
                    "side_activity": True,
                    "type": "meeting",
                    "res_model": "calendar.event",
                })
                if res_task_id:
                    event.update({
                        "_res_model": "project.task",
                        "_res_id": res_task_id,
                    })
                elif res_project_id:
                    event.update({
                        "_res_model": "project.project",
                        "_res_id": res_project_id,
                    })
                res.append(event)

            return res

        return [
            *super()._get_assistant_events_getters(),
            {
                "sequence": 10,
                "getter": get_calendar_events,
            },
        ]
