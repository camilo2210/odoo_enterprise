# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.date_utils import localized


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    has_active_contract = fields.Boolean(
        store=False,
        search="_search_has_active_contract",
        groups="hr_attendance.group_hr_attendance_officer",
    )
    show_contract_warning = fields.Boolean(compute="_compute_show_contract_warning", compute_sudo=True)

    @api.model
    def _search_has_active_contract(self, operator, value):
        if operator != 'in':
            return NotImplemented

        start = datetime.combine(fields.Date.context_today(self), datetime.min.time(), tzinfo=self.env.tz)
        active_contract_domain = self._get_active_contract_domain(start, start + timedelta(days=1))

        # sudo() is needed because attendance officers may not have access to contract versions.
        employee_query = self.env['hr.employee'].sudo()._search(active_contract_domain)
        return Domain('employee_id', 'in', employee_query)

    @api.depends('employee_id', 'date')
    def _compute_show_contract_warning(self):
        for attendance in self:
            if not attendance.employee_id or not attendance.date:
                # New blank form: do not show the warning yet.
                attendance.show_contract_warning = False
                continue
            attendance.show_contract_warning = not attendance.employee_id._is_in_contract(attendance.date)

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        """
        This function returns the data needed by the frontend when displaying
        the progress bar on the left side of the gantt view

        :return: dict of this format: {employee_id: {progress bar data}}
        """
        if field != 'employee_id':
            raise NotImplementedError(self.env._("Attendance's gantt progess bars only support the 'employee_id' field"))
        if not self.env.user._is_internal():
            return {}

        start, stop = start.replace(tzinfo=UTC), stop.replace(tzinfo=UTC)

        worked_hours_per_employee_id = {
            employee.id: worked_hours
            for employee, worked_hours in self._read_group(
                self._get_gantt_progress_bar_domain(res_ids, start, stop),
                groupby=['employee_id'],
                aggregates=['worked_hours:sum']
            )
        }

        employees = self.env['hr.employee'].sudo().browse(res_ids)
        return {
            employee.id: {
                'value': worked_hours_per_employee_id.get(employee.id, 0),
                'max_value': self._gantt_compute_max_work_hours_within_interval(employee, start, stop) or 0,
                'is_fully_flexible_hours': employee.resource_id._is_fully_flexible(),
                'attendance_based': employee.attendance_based,
            } for employee in employees
        }

    def _gantt_compute_max_work_hours_within_interval(self, employee, start, stop):
        """
        Compute the total work hours of the employee based on the intervals selected on the Gantt view.
        The calculation takes into account the working calendar (flexible or not).
        """
        if employee.sudo()._is_flexible(start.date()) and not employee.sudo()._is_fully_flexible(start.date()):
            total_days = (stop - start).days
            weeks = total_days // 7
            days = total_days % 7
            calendar = employee.resource_calendar_id
            return (
                weeks * calendar.hours_per_week + min(
                    (days * calendar.hours_per_day),
                    calendar.hours_per_week
                ))
        else:
            user_tz = ZoneInfo(self.env.user.tz or 'UTC')
            start = datetime.combine(start.astimezone(user_tz).date(), datetime.min.time(), tzinfo=UTC)
            stop = datetime.combine(stop.astimezone(user_tz).date(), datetime.min.time(), tzinfo=UTC)
            return self.env['resource.calendar']._get_attendance_intervals_days_data(employee._get_expected_attendances(start, stop))['hours']

    def _get_gantt_progress_bar_domain(self, res_ids, start, stop):
        return [
            ('employee_id', 'in', res_ids),
            ('check_in', '>=', start.replace(tzinfo=None)),
            ('check_out', '<=', stop.replace(tzinfo=None)),
        ]

    @api.model
    def _is_entirely_employee_domain(self, domain) -> bool:
        """
        Returns whether the given domain only filters on fields related to
        `self.employee_id`
        """
        domain = Domain(domain)
        return all(
            c.field_expr == 'employee_id'
            for c in domain.optimize_full(self).iter_conditions()
        )

    def _get_active_contract_domain(self, start_datetime, stop_datetime):
        start_date = localized(start_datetime).astimezone(self.env.tz).date()
        stop_date = localized(stop_datetime).astimezone(self.env.tz).date()
        return Domain('version_ids', 'any', [
            ('active', '=', True),
            ('contract_date_start', '<', stop_date),
            '|',
                ('contract_date_end', '>=', start_date),
                ('contract_date_end', '=', False),
        ])

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None,
        offset=0, unavailability_fields=None, progress_bar_fields=None,
        start_date=None, stop_date=None, scale=None,
    ):
        # domain created from the user's filter input in the search bar
        user_domain = Domain(self.env.context.get('user_domain') or Domain.TRUE)

        # we want to add employees without attendances if we only search
        # based on employee fields
        is_filter_only_on_employees = self._is_entirely_employee_domain(
            user_domain,
        )
        if groupby == ['employee_id'] and is_filter_only_on_employees:
            gantt_data = self._get_gantt_data_with_empty(
                super().get_gantt_data,
                domain=domain,
                groupby=groupby,
                read_specification=read_specification,
                limit=limit,
                offset=offset,
                unavailability_fields=unavailability_fields,
                progress_bar_fields=progress_bar_fields,
                start_date=start_date,
                stop_date=stop_date,
                scale=scale,
            )
        else:
            gantt_data = super().get_gantt_data(
                domain,
                groupby,
                read_specification,
                limit=limit,
                offset=offset,
                unavailability_fields=unavailability_fields,
                progress_bar_fields=progress_bar_fields,
                start_date=start_date,
                stop_date=stop_date,
                scale=scale,
            )

        if groupby == ['employee_id'] and gantt_data.get('groups'):
            page_employee_ids = [
                g['employee_id'][0] for g in gantt_data['groups'] if g.get('employee_id')
            ]
            active_contract_domain = self._get_active_contract_domain(
                fields.Datetime.to_datetime(start_date),
                fields.Datetime.to_datetime(stop_date),
            )
            # sudo() is needed because attendance officers may not have access to contract versions.
            gantt_data['employees_without_contract_ids'] = self.env['hr.employee'].sudo().search(
                ~active_contract_domain & Domain([('id', 'in', page_employee_ids)])
            ).ids

        return gantt_data

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        if field != "employee_id":
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)

        employees = self.env['hr.employee'].browse(res_ids)
        return employees._get_employee_unavailable_intervals(start, stop)

    @api.onchange('check_in')
    def _onchange_check_in(self):
        if 'scale' in self.env.context and self.env.context["scale"] != 'day':
            # sudo() is needed because attendance officers may not have access to employee versions.
            hours_per_day = self.employee_id.sudo().current_version_id.resource_calendar_id.hours_per_day
            self.check_out = self.check_in + timedelta(hours=hours_per_day)

    def action_open_details(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.attendance",
            "views": [[self.env.ref('hr_attendance.hr_attendance_view_form').id, "form"]],
            "res_id": self.id
        }
