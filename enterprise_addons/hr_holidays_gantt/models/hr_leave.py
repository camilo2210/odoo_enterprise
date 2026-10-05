# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2005-2006 Axelor SARL. (http://www.axelor.com)

from collections import defaultdict
from datetime import timedelta, UTC
from itertools import groupby
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.addons.resource.models.utils import HOURS_PER_DAY
from odoo.fields import Domain
from odoo.tools import format_time
from odoo.tools.intervals import Intervals
from odoo.tools.misc import get_lang
from odoo.tools.date_utils import localized


def format_date(env, date):
    return date.strftime(get_lang(env).date_format)


def same_wall_clock(moment, tz_from, tz_to):
    """ The instant that tells ``tz_to`` the wall clock ``moment`` tells ``tz_from``. """
    return moment.astimezone(tz_from).replace(tzinfo=tz_to)


class HrLeave(models.Model):
    _inherit = "hr.leave"

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if self.env.context.get('default_employee_id'):
            employee = self.env['hr.employee'].browse(self.env.context['default_employee_id'])
            defaults['employee_id'] = employee.id
            defaults['user_id'] = employee.user_id.id if employee.user_id else False

        # Catch the initial load of the multi-day single-employee popover
        if self.env.context.get('is_multi_day_selection') and not self.env.context.get('default_is_multi_employee'):
            if defaults.get('work_entry_type_id'):
                wet = self.env['hr.work.entry.type'].browse(defaults['work_entry_type_id'])
                unit = wet.request_unit
                duration = defaults.get('request_duration', 'full')

                if unit == 'hour' or (unit == 'half_day' and duration in ['am', 'pm']):
                    single_date_to = self.env.context.get('gantt_single_request_date_to')
                    if single_date_to:
                        defaults['request_date_to'] = fields.Date.to_date(single_date_to)

                    # Force the hourly/partial split template to show a single template day initially
                    if 'number_of_days' in defaults:
                        defaults['number_of_days'] = 1
        return defaults

    display_code = fields.Char(
        related="work_entry_type_id.display_code",
        readonly=True,
        groups="hr_holidays.group_hr_holidays_user",
    )

    @api.depends_context('is_multi_day_selection', 'default_is_multi_employee')
    def _compute_allowed_request_durations(self):
        super()._compute_allowed_request_durations()

    # this one to distinguish between number_of_hours as total or per single day
    @api.onchange('work_entry_type_id', 'request_duration', 'request_date_from')
    def _onchange_work_entry_type_id_gantt_split(self):
        if self.env.context.get('is_multi_day_selection'):
            unit = self.work_entry_type_id.request_unit
            duration = self.request_duration
            if unit == 'hour' or (unit == 'half_day' and duration in ['am', 'pm']):
                single_date_to = self.env.context.get('gantt_single_request_date_to')
                if single_date_to:
                    self.request_date_to = fields.Date.to_date(single_date_to)
            else:
                full_date_to = self.env.context.get('gantt_full_request_date_to')
                if full_date_to:
                    self.request_date_to = fields.Date.to_date(full_date_to)

    def _get_allowed_request_durations(self):
        self.ensure_one()

        if self.env.context.get('is_multi_day_selection') and not self.env.context.get('default_is_multi_employee'):
            if self.work_entry_type_request_unit == "half_day":
                return ["full", "am", "pm"]
            if self.work_entry_type_request_unit == "hour":
                return ["full", "am", "pm", "specific"]

        return super()._get_allowed_request_durations()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            request_duration = vals.get("request_duration")
            if not request_duration or not vals.get("work_entry_type_id"):
                continue
            work_entry_type = self.env["hr.work.entry.type"].browse(vals["work_entry_type_id"])
            if work_entry_type.request_unit == "half_day":
                if request_duration == "full":
                    vals.setdefault("request_date_from_period", "am")
                    vals.setdefault("request_date_to_period", "pm")
                elif request_duration in ("am", "pm"):
                    vals["request_date_from_period"] = request_duration
                    vals["request_date_to_period"] = request_duration
            elif work_entry_type.request_unit == "hour" and request_duration in ("full", "am", "pm"):
                if not (vals.get("employee_id") and vals.get("request_date_from") and vals.get("request_date_to")):
                    continue
                employee = self.env["hr.employee"].browse(vals["employee_id"])
                request_date_from = fields.Date.to_date(vals["request_date_from"])
                request_date_to = fields.Date.to_date(vals["request_date_to"])
                if request_duration == "full":
                    hour_from, hour_to = employee._get_hours_for_date(request_date_from)
                else:
                    day_period = "morning" if request_duration == "am" else "afternoon"
                    hour_from, _ = employee._get_hours_for_date(request_date_from, day_period)
                    _, hour_to = employee._get_hours_for_date(request_date_to, day_period)
                if work_entry_type.count_as == "working_time" and hour_to - hour_from >= 24:
                    half_day = HOURS_PER_DAY / 2
                    hour_from, hour_to = 12.0 - half_day, 12.0 + half_day
                vals.setdefault("request_hour_from", hour_from)
                vals.setdefault("request_hour_to", hour_to)
        return super().create(vals_list)

    @api.model
    def _get_leave_interval(self, date_from, date_to, employee_ids):
        # Validated hr.leave create a resource.calendar.leaves
        calendar_leaves = self.env['resource.calendar.leaves'].search([
            ('count_as', '=', 'absence'),
            '|', ('company_id', 'in', employee_ids.mapped('company_id').ids),
                 ('company_id', '=', False),
            '|', ('resource_id', 'in', employee_ids.mapped('resource_id').ids),
                 ('resource_id', '=', False),
            ('date_from', '<', date_to),
            ('date_to', '>', date_from),
        ], order='date_from')

        leaves = defaultdict(list)
        for leave in calendar_leaves:
            for employee in employee_ids:
                if (not leave.company_id or leave.company_id == employee.company_id) and\
                   (not leave.resource_id or leave.resource_id == employee.resource_id) and\
                   (not leave.calendar_id or leave.calendar_id == employee.resource_calendar_id):
                    leaves[employee.id].append(leave)

        # Get non-validated time off
        leaves_query = self.env['hr.leave'].search([
            ('employee_id', 'in', employee_ids.ids),
            ('state', 'in', ['confirm', 'validate1']),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from)
        ], order='date_from')
        for leave in leaves_query:
            leaves[leave.employee_id.id].append(leave)
        return leaves

    def _get_leave_warning_parameters(self, leaves, employee, date_from, date_to):
        loc_cache = {}

        def localize(date):
            if date not in loc_cache:
                loc_cache[date] = date.replace(tzinfo=UTC).astimezone(ZoneInfo(self.env.user.tz or 'UTC')).replace(tzinfo=None)
            return loc_cache[date]

        periods = self._group_leaves(leaves, employee, date_from, date_to)
        periods_by_states = [list(b) for a, b in groupby(periods, key=lambda x: x['is_validated'])]
        res = {}
        for periods in periods_by_states:
            leaves_for_employee = {'name': employee.name, "leaves": []}
            for period in periods:
                dfrom = period['from']
                dto = period['to']
                number_of_days = period['number_of_days']
                if number_of_days == 1:
                    leaves_for_employee['leaves'].append({
                        "start_date": format_date(self.env, localize(dfrom)),
                    })
                elif number_of_days < 1:
                    leaves_for_employee['leaves'].append({
                        "start_date": format_date(self.env, localize(dfrom)),
                        "start_time": format_time(self.env, dfrom, time_format='short'),
                        "end_time": format_time(self.env, dto, time_format='short')
                    })
                else:
                    leaves_for_employee['leaves'].append({
                        "start_date": format_date(self.env, localize(dfrom)),
                        "end_date": format_date(self.env, localize(dto)),
                    })
            res["validated" if periods[0].get('is_validated') else "requested"] = leaves_for_employee
        return res

    def format_date_range_to_string(self, date_dict):
        if len(date_dict) == 3:
            return _('on %(start_date)s from %(start_time)s to %(end_time)s', **date_dict)
        elif len(date_dict) == 2:
            return _('from %(start_date)s to %(end_date)s', **date_dict)
        else:
            return _('on %(start_date)s', **date_dict)

    def _get_leave_warning(self, leaves, employee, date_from, date_to):
        leaves_parameters = self._get_leave_warning_parameters(leaves, employee, date_from, date_to)
        warning = ''
        for leave_type, leaves_for_employee in leaves_parameters.items():
            if not leaves_for_employee:
                continue
            if leave_type == "validated":
                warning += _(
                    '%(name)s is on time off %(leaves)s. \n',
                    name=leaves_for_employee["name"],
                    leaves=', '.join(map(self.format_date_range_to_string, leaves_for_employee["leaves"]))
                )
            else:
                warning += _(
                    '%(name)s requested time off %(leaves)s. \n',
                    name=leaves_for_employee["name"],
                    leaves=', '.join(map(self.format_date_range_to_string, leaves_for_employee["leaves"]))
                )
        return warning

    def _group_leaves(self, leaves, employee_id, date_from, date_to):
        """
            Returns all the leaves happening between `planned_date_begin` and `date_deadline`
        """
        work_times = {wk[0]: wk[1] for wk in employee_id._list_work_time_per_day(date_from, date_to)[employee_id.id]}

        def has_working_hours(start_dt, end_dt):
            """
                Returns `True` if there are any working days between `start_dt` and `end_dt`.
            """
            diff_days = (end_dt - start_dt).days
            all_dates = [start_dt.date() + timedelta(days=delta) for delta in range(diff_days + 1)]
            return any(d in work_times for d in all_dates)

        periods = []
        for leave in leaves:
            if leave.date_from > date_to or leave.date_to < date_from:
                continue

            # Can handle both hr.leave and resource.calendar.leaves
            number_of_days = 0
            is_validated = True
            if isinstance(leave, self.pool['hr.leave']):
                number_of_days = leave.number_of_days
                is_validated = False
            else:
                dt_delta = (leave.date_to - leave.date_from)
                if leave.holiday_id and leave.holiday_id.sudo().work_entry_type_request_unit not in ('half_day', 'hour'):
                    number_of_days = dt_delta.days + 1
                else:
                    number_of_days = dt_delta.days + ((dt_delta.seconds / 3600) / 24)
            # leaves are ordered by date_from and grouped by type. When go from the batch of validated time offs to the
            # requested ones, we need to bypass the second condition with the third one
            if not periods or has_working_hours(periods[-1]['from'], leave.date_to) or \
                    periods[-1]['is_validated'] != is_validated:
                periods.append({'is_validated': is_validated, 'from': leave.date_from, 'to': leave.date_to, 'number_of_days': number_of_days})
            else:
                periods[-1]['is_validated'] = is_validated
                if periods[-1]['to'] < leave.date_to:
                    periods[-1]['to'] = leave.date_to
                periods[-1]['number_of_days'] = periods[-1].get('number_of_days') or number_of_days
        return periods

    def _window_told_by(self, start, stop, tz):
        """ The window every gantt row shows, as ``tz`` tells it. """
        user_tz = self._reader_tz()
        return (same_wall_clock(localized(start), user_tz, tz),
                same_wall_clock(localized(stop), user_tz, tz))

    def _wall_clock_intervals(self, intervals, tz_from, tz_to):
        """ Restamp intervals on another clock, dropping those a change of offset empties. """
        empty = self.env['resource.calendar']
        return Intervals([
            (same_wall_clock(interval[0], tz_from, tz_to),
             same_wall_clock(interval[1], tz_from, tz_to),
             interval[2] if len(interval) > 2 else empty)
            for interval in intervals
        ])

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        if field != "employee_id":
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)

        employees = self.env['hr.employee'].browse(res_ids)
        return employees._get_employee_unavailable_intervals(start, stop)

    @api.model
    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if field != 'employee_id':
            return super()._gantt_progress_bar(field, res_ids, start, stop)
        if not self.env.user._is_internal():
            return {}

        employees = self.env['hr.employee'].browse(res_ids)
        # ask every employee about the same wall clock, told by their own
        worked_hours = {}
        flexible_windows = []
        for tz, group in employees.grouped(lambda employee: ZoneInfo(employee._get_tz())).items():
            window_start, window_stop = self._window_told_by(start, stop, tz)
            worked_hours.update(group._get_work_days_data_batch(
                window_start, window_stop, compute_leaves=True))

            if flexible_employees := group.filtered(lambda e: e.resource_id._is_flexible()):
                flexible_windows.append(Domain([
                    ('employee_id', 'in', flexible_employees.ids),
                    ('date_from', '<=', window_stop.astimezone(UTC).replace(tzinfo=None)),
                    ('date_to', '>=', window_start.astimezone(UTC).replace(tzinfo=None)),
                ]))

        # each timezone has its own window, asked for in one go
        flexible_leave_hours = {
            employee.id: hours
            for employee, hours in self.env['hr.leave']._read_group(
                Domain.OR(flexible_windows) & Domain('state', '=', 'validate'),
                groupby=['employee_id'],
                aggregates=['number_of_hours:sum'],
            )
        } if flexible_windows else {}

        return {
            employee.id: {
                'value': (
                    flexible_leave_hours.get(employee.id, 0.0) if employee.resource_id._is_flexible()
                    else worked_hours.get(employee.id, {}).get('hours', 0.0)
                ),
            }
            for employee in employees
        }

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

    @api.model
    def get_gantt_data(
        self, domain, groupby, read_specification, limit=None,
        offset=0, unavailability_fields=None, progress_bar_fields=None,
        start_date=None, stop_date=None, scale=None,
    ):
        """
        We want to add employees without leaves if the user's filter is empty,
        or only about the `employee_id` field.
        """
        domain = Domain(domain)
        # domain created from the user's filter input in the search bar
        user_domain = Domain(self.env.context.get('user_domain') or Domain.TRUE)

        if groupby == ['employee_id'] and self._is_entirely_employee_domain(user_domain):
            return self._get_gantt_data_with_empty(
                super(HrLeave, self.with_context(scale=scale)).get_gantt_data,
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
        return super().get_gantt_data(
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

    @api.onchange('request_hour_from', 'request_hour_to')
    def _onchange_hours_auto_specific(self):
        for leave in self:
            if (leave.work_entry_type_request_unit == 'hour'
                and leave.request_duration != 'specific'
                and self.env.context.get('update_duration')):
                leave.request_duration = 'specific'

    def gantt_split_leave(self, split_date):
        """ Split this time off in two at ``split_date`` (day granularity), the
        same way the planning gantt "scissors" splits a shift.

        The original time off is truncated so that it ends the day before
        ``split_date`` and a new time off, covering ``split_date`` up to the
        original end date, is created.

        :param str split_date: the first day (``YYYY-MM-DD``) of the second time off.
        :return: the data required to undo the split (see ``gantt_undo_split_leave``).
        :rtype: dict
        """
        self.ensure_one()
        split_date = fields.Date.to_date(split_date)
        undo_data = {
            'request_date_to': fields.Date.to_string(self.request_date_to),
            'request_date_to_period': self.request_date_to_period,
            'request_hour_to': self.request_hour_to,
        }
        new_leaves = self._split_leaves(split_date)
        undo_data['new_leave_ids'] = new_leaves.ids
        return undo_data

    def gantt_undo_split_leave(self, new_leave_ids, request_date_to, request_date_to_period, request_hour_to=None):
        """ Revert a split performed by ``gantt_split_leave``: remove the time off
        created for the second part and restore the original end date on ``self``.

        :return: whether the split could be undone.
        :rtype: bool
        """
        if not self.exists():
            return False
        new_leaves = self.browse(new_leave_ids).exists()
        if new_leaves:
            new_leaves.with_context(leave_skip_state_check=True).unlink()
        leaves_to_restore = self.with_context(leave_skip_state_check=True)
        leaves_to_restore.write({
            'request_date_to': fields.Date.to_date(request_date_to),
            'request_date_to_period': request_date_to_period,
            **({'request_hour_to': request_hour_to} if request_hour_to is not None else {}),
        })
        leaves_to_restore.flush_recordset(['date_from', 'date_to'])
        return True

def tag_employee_rows(rows):
    """
        Add `employee_id` key in rows and subsrows recursively if necessary
        :return: a set of ids with all concerned employees (subrows included)
    """
    employee_ids = set()
    for row in rows:
        group_bys = row.get('groupedBy')
        res_id = row.get('resId')
        if group_bys:
            # if employee_id is the first grouping attribute, we mark the row
            if group_bys[0] == 'employee_id' and res_id:
                employee_id = res_id
                employee_ids.add(employee_id)
                row['employee_id'] = employee_id
            # else we recursively traverse the rows where employee_id appears in the group_by
            elif 'employee_id' in group_bys:
                employee_ids.update(tag_employee_rows(row.get('rows')))
    return employee_ids

# function to recursively replace subrows with the ones returned by func
def traverse(func, row):
    new_row = dict(row)
    if new_row.get('employee_id'):
        for sub_row in new_row.get('rows'):
            sub_row['employee_id'] = new_row['employee_id']
    new_row['rows'] = [traverse(func, row) for row in new_row.get('rows')]
    return func(new_row)
