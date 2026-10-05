import re
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, RedirectWarning, UserError, MissingError
from odoo.fields import Domain
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, format_date
from odoo.tools.date_utils import localized
from odoo.tools.func import deprecated
from odoo.addons.timer.utils.timer_utils import round_time_spent


class AccountAnalyticLine(models.Model):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'
    # As this model has his own data merge, avoid to enable the generic data_merge on that model.
    _disable_data_merge = True

    # reset amount on copy
    amount = fields.Monetary(copy=False)
    validated = fields.Boolean("Validated line", aggregator="bool_and", store=True, copy=False, readonly=True)
    validated_status = fields.Selection([('draft', 'Draft'), ('validated', 'Validated')], required=True,
        compute='_compute_validated_status')
    user_can_validate = fields.Boolean(compute='_compute_can_validate',
        help="Whether or not the current user can validate/reset to draft the record.")

    is_hatched = fields.Boolean(compute='_compute_is_hatched', export_string_translation=False)

    @api.model_create_multi
    def create(self, vals_list):
        if (
            not self.env.context.get('default_employee_id')
            and any("employee_id" not in vals and "project_id" in vals for vals in vals_list)
            and not self.env['hr.employee'].sudo().search_count([], limit=1)
        ):
            env_user_id = self.env.context.get('user_id', self.env.user.id)
            env_company_id = self.env.company.id
            users_ids = {env_user_id} | {vals["user_id"] for vals in vals_list if vals.get("user_id")}
            user_by_id = {user.id: user for user in self.env['res.users'].browse(users_ids)}
            employees_to_create = []
            created_employees_users = set()
            Employee = self.env['hr.employee'].sudo()
            default_user_id = self.env.context.get('default_user_id')
            default_company_id = self.env.context.get('default_company_id')
            odoo_bot_id = self.env.ref('base.user_root').id

            for vals in vals_list:
                if "employee_id" in vals:
                    continue

                user_id = vals.get("user_id", default_user_id or env_user_id)
                if user_id == odoo_bot_id:
                    continue

                company_id = vals.get("company_id", default_company_id or env_company_id)
                user = user_by_id[user_id]
                user_and_company = (user_id, company_id)
                if not user.employee_id and user_and_company not in created_employees_users:
                    employees_to_create.append({
                        'name': user.name,
                        'company_id': company_id,
                        'user_id': user_id,
                        **Employee._sync_user(user)
                    })
                    created_employees_users.add(user_and_company)

            if len(employees_to_create) == 1:
                Employee.create(employees_to_create)

        return super().create(vals_list)

    @api.constrains('unit_amount')
    def _check_timesheet_unit_amount(self):
        if any(abs(t.unit_amount) > 999999 for t in self if t.project_id):
            raise UserError(_("You can't encode numbers with more than six digits."))

    def _is_readonly(self):
        return super()._is_readonly() or self.validated

    @api.model
    def grid_unavailability(self, start_date, end_date, groupby='', res_ids=()):
        start_datetime = fields.Datetime.from_string(start_date)
        end_datetime = fields.Datetime.from_string(end_date) + relativedelta(hour=23, minute=59, second=59)
        unavailability_intervals_per_employee_id = {}
        # naive datetimes are made explicit in UTC
        from_datetime = localized(start_datetime)
        to_datetime = localized(end_datetime)
        # We need to display in grey the unavailable full days
        # We start by getting the availability intervals to avoid false positive with range outside the office hours

        def get_unavailable_dates(intervals):
            # get the dates where some work can be done in the interval. It returns a list of sets.
            available_dates = [{start.date(), end.date()} for start, end, dummy in intervals]
            # flatten the list of sets to get a simple list of dates and add it to the pile.
            availability_date_list = [date for dates in available_dates for date in dates]
            unavailable_days = []
            cur_day = from_datetime
            while cur_day <= to_datetime:
                if cur_day.date() not in availability_date_list:
                    unavailable_days.append(cur_day.date())
                cur_day = cur_day + timedelta(days=1)
            return list(set(unavailable_days))

        def get_company_unavailable_dates():
            return get_unavailable_dates(self.env.company.resource_calendar_id._work_intervals_batch(
                from_datetime, to_datetime,
                domain=[('count_as', '=', 'absence'), ('company_id', '=', self.env.company.id)],
            )[False])

        def get_current_user_unavailable_dates():
            resource = self.env.user.employee_id.resource_id
            if resource:
                resource_work_intervals, _ = resource._get_valid_work_intervals(
                    from_datetime, to_datetime
                )
                if resource.id in resource_work_intervals:
                    return get_unavailable_dates(resource_work_intervals[resource.id])
            return False

        if groupby == 'employee_id':
            employees = self.env['hr.employee'].browse(set(res_ids))
            availability_intervals_per_resource_id, calendar_work_intervals = employees.resource_id._get_valid_work_intervals(from_datetime, to_datetime)
            employee_id_per_resource_id = {emp.resource_id.id: emp.id for emp in employees}
            if not calendar_work_intervals:
                unavailability_intervals_per_employee_id[False] = get_company_unavailable_dates()
                return unavailability_intervals_per_employee_id
            company_unavailable_days = get_company_unavailable_dates()
            unavailability_intervals_per_employee_id = {
                employee_id:
                    []
                    if self.env['resource.resource'].browse(resource_id)._is_flexible()
                    else get_unavailable_dates(availability_intervals_per_resource_id[resource_id])
                    if resource_id in availability_intervals_per_resource_id
                    else company_unavailable_days
                for resource_id, employee_id in employee_id_per_resource_id.items()
            }
            unavailability_intervals_per_employee_id[False] = company_unavailable_days
        elif self.env.context.get('get_current_user_unavailable_dates', False):
            unavailability_intervals_per_employee_id[False] = get_current_user_unavailable_dates()
        else:
            resource = self.env.user.employee_id.resource_id
            if resource and resource._is_flexible() and not resource._is_fully_flexible():
                unavailability_intervals_per_employee_id[False] = []
            else:
                unavailability_intervals_per_employee_id[False] = get_company_unavailable_dates()
        return unavailability_intervals_per_employee_id

    def _compute_project_id(self):
        # override hr_timesheet to allow the check on field validated to only update the project_id on non validated timesheets.
        non_validated_timesheets = self.filtered(lambda t: not t.validated and t.task_id.project_id.allow_timesheets)
        super(AccountAnalyticLine, non_validated_timesheets)._compute_project_id()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        super()._onchange_project_id()
        if not (
            self.env.context.get('timesheet_timer_search')
            and self.project_id
            and not self.task_id
            and (employee := self.env.user.employee_id)
        ):
            return

        # Prefill the task of the most recent timesheet the user logged on this project in the
        # past month; if that timesheet has no task, prefill none.
        recent_task = self._get_recently_used_records('task_id', limit=1, domain=[
            ('employee_id', '=', employee.id),
            ('project_id', '=', self.project_id.id),
            ('date', '>=', fields.Date.context_today(self) - relativedelta(months=1)),
            '|',
                ('task_id', '=', False),
                ('task_id', 'any', [
                    ('active', '=', True),
                    ('project_id', '=', self.project_id.id),
                    ('has_template_ancestor', '=', False),
                ]),
        ])
        if recent_task:
            self.task_id = recent_task[0][0]

    @api.depends('validated')
    def _compute_validated_status(self):
        for line in self:
            if line.validated:
                line.validated_status = 'validated'
            else:
                line.validated_status = 'draft'

    @api.depends_context('uid')
    def _compute_can_validate(self):
        is_manager = self.env.user.has_group('hr_timesheet.group_timesheet_manager')
        is_approver = self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver')
        for line in self:
            if is_manager or (is_approver and (
                line.employee_id.timesheet_manager_id.id == self.env.user.id or
                line.employee_id.parent_id.user_id.id == self.env.user.id or
                line.project_id.user_id.id == self.env.user.id or
                line.user_id.id == self.env.user.id)):
                line.user_can_validate = True
            else:
                line.user_can_validate = False

    def _update_last_validated_timesheet_date(self):
        max_date_per_employee = {
            employee: employee.last_validated_timesheet_date
            for employee in self.employee_id.sudo()
        }
        for timesheet in self:
            max_date = max_date_per_employee[timesheet.employee_id]
            if not max_date or max_date < timesheet.date:
                max_date_per_employee[timesheet.employee_id] = timesheet.date

        employee_ids_per_date = defaultdict(list)
        for employee, max_date in max_date_per_employee.items():
            if not employee.last_validated_timesheet_date or (max_date and employee.last_validated_timesheet_date < max_date):
                employee_ids_per_date[max_date].append(employee.id)

        for date, employee_ids in employee_ids_per_date.items():
            self.env['hr.employee'].sudo().browse(employee_ids).write({'last_validated_timesheet_date': date})

    @api.model
    def _search_last_validated_timesheet_date(self, employee_ids):
        EmployeeSudo = self.env['hr.employee'].sudo()
        timesheet_read_group = self.env['account.analytic.line']._read_group(
            [
                ('validated', '=', True),
                ('project_id', '!=', False),
                ('employee_id', 'in', employee_ids),
            ],
            ['employee_id'],
            ['date:max'],
        )

        EmployeeSudo.browse(employee_ids).last_validated_timesheet_date = False
        for employee, date_max in timesheet_read_group:
            employee.sudo().last_validated_timesheet_date = date_max

    @api.depends('validated')
    def _compute_is_hatched(self):
        for line in self:
            line.is_hatched = not line.validated

    def action_validate_timesheet(self):
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': None,
                'type': None,  #types: success,warning,danger,info
                'sticky': False,  #True/False will display for few seconds if false
            },
        }
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
            notification['params'].update({
                'message': _("You can only validate the timesheets of employees of whom you are the manager or the timesheet approver."),
                'type': 'danger'
            })
            return notification

        # filter in sudo to access employee manager (in domain)
        # The rest of the method and calls are anyway sudoing analytic_lines everywhere so no real impact here.
        analytic_lines = self.sudo().filtered_domain(self._get_domain_for_validation_timesheets())
        if not analytic_lines:
            notification['params'].update({
                'message': _("You cannot validate the selected timesheets as they either belong to employees who are not part of your team or are not in a state that can be validated. This may be due to the fact that they are dated in the future."),
                'type': 'danger',
            })
            return notification

        analytic_lines.sudo().write({'validated': True})
        analytic_lines._update_last_validated_timesheet_date()
        if self.env.context.get('use_notification', True):
            notification['params'].update({
                'message': _("The timesheets have successfully been validated."),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            })
            return notification
        return True

    def action_invalidate_timesheet(self):
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': None,
                'type': None,
                'sticky': False,
            },
        }
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
            raise AccessError(_("You can only reset to draft the timesheets of employees of whom you are the manager or the timesheet approver."))
        #Use the same domain for validation but change validated = False to validated = True
        domain = self._get_domain_for_validation_timesheets(validated=True)
        analytic_lines = self.sudo().filtered_domain(domain)
        if not analytic_lines:
            notification['params'].update({
                'message': _('There are no timesheets to reset to draft or they have already been invoiced.'),
                'type': 'warning',
            })
            return notification

        analytic_lines.sudo().write({'validated': False})
        self.env['account.analytic.line']._search_last_validated_timesheet_date(analytic_lines.employee_id.ids)
        if self.env.context.get('use_notification', True):
            notification['params'].update({
                'message': _("The timesheets have successfully been reset to draft."),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            })
            return notification
        return True

    def check_if_allowed(self, vals=None, delete=False,):
        if not self.env.user.has_group('hr_timesheet.group_timesheet_manager') and not self.env.su:
            is_timesheet_approver = self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver')
            employees = self.env['hr.employee'].with_context(active_test=False).search([
                ('id', 'in', self.employee_id.ids),
                ('user_id', '!=', self.env.uid),
                '|', ('parent_id.user_id', '=', self.env.uid),
                '|', ('timesheet_manager_id', 'in', [False, self.env.uid]),
                '|', ('id', 'in', self.env.user.employee_id.subordinate_ids.ids),
                '&', ('parent_id', '=', False), ('timesheet_manager_id', '=', False),
            ])

            action = "delete" if delete else "modify" if vals is not None and "date" in vals else "create or edit"
            for line in self:
                show_access_error = False
                employee = line.employee_id
                company = line.company_id
                last_validated_timesheet_date = employee.sudo().last_validated_timesheet_date
                def is_wrong_date(date):
                    return date != fields.Date.context_today(line) and date <= last_validated_timesheet_date

                # When an user having this group tries to modify the timesheets of another user in his own team, we shouldn't raise any validation error
                if not is_timesheet_approver or employee not in employees:
                    if line.project_id and last_validated_timesheet_date:
                        if action == "modify" and is_wrong_date(fields.Date.to_date(str(vals['date']))):
                            show_access_error = True
                        elif is_wrong_date(line.date):
                            show_access_error = True

                if show_access_error:
                    last_validated_timesheet_date_str = format_date(self.env, last_validated_timesheet_date)
                    if delete:
                        error_message = _('Timesheets before the %(date)s (included) have been validated, and can no longer be deleted.', date=last_validated_timesheet_date_str)
                    else:
                        error_message = _('Timesheets before the %(date)s (included) have been validated, and can no longer be modified.', date=last_validated_timesheet_date_str)
                    raise AccessError(error_message)

    def _check_can_create(self):
        # Check if the user has the correct access to create timesheets
        if (
            not (self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver') or self.env.su)
            and any(line.project_id and line.user_id != self.env.user for line in self)
        ):
            raise AccessError(_("You cannot access timesheets that are not yours."))
        self.check_if_allowed()

        return super()._check_can_create()

    def _check_can_write(self, vals):
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
            if 'validated' in vals:
                raise AccessError(_('You can only validate the timesheets of employees of whom you are the manager or the timesheet approver.'))
            elif self.filtered(lambda r: r.project_id and r.validated):
                raise AccessError(_('Only a Timesheets Approver or Manager is allowed to modify a validated entry.'))

        self.check_if_allowed(vals)

        return super()._check_can_write(vals)

    def _get_timesheet_action(self, value):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Open Form'),
            'res_model': 'account.analytic.line',
            'views': [(self.env.ref('timesheet_grid.timesheet_view_form_user_grid').id, 'form')],
            'context': {
                **self.env.context,
                'default_unit_amount': value,
                'is_timesheet': True,
            },
        }

    @api.model
    def _get_timesheet_field_and_model_name(self):
        return 'task_id', 'project.task'

    @api.model
    def grid_update_cell(self, domain, measure_field_name, value):
        if value == 0:  # nothing to do
            return
        timesheets = self.search(domain, limit=2)

        # sudo in case of timesheeting a task belonging to a private project
        if timesheets.project_id and not all(timesheets.project_id.sudo().mapped("allow_timesheets")):
            raise UserError(_("You cannot adjust the time of the timesheet for a project with timesheets disabled."))

        non_validated_timesheets = timesheets.filtered(lambda timesheet: not timesheet.validated)
        if len(non_validated_timesheets) > 1 or (len(timesheets) == 1 and timesheets.validated):
            timesheets[0].copy({
                'name': self.env.context.get('default_name', '/'),
                measure_field_name: value,
            })
        elif len(non_validated_timesheets) == 1:
            non_validated_timesheets[measure_field_name] += value
        else:
            project_id = self.env.context.get('default_project_id', False)
            field_name, model_name = self._get_timesheet_field_and_model_name()
            field_value = self.env.context.get(f'default_{field_name}', False)
            if not project_id and field_value:
                project_id = self.env[model_name].browse(field_value).project_id.id
            if not project_id:
                warning_msg = _('Your timesheet entry is missing a project. Please either group the Grid view by project or enter your timesheets by adding a line via the Form view.')
                action = self._get_timesheet_action(value)
                raise RedirectWarning(warning_msg, action, _('Open Form'))

            if not self.env['project.project'].browse(project_id).sudo().allow_timesheets:
                raise UserError(_("You cannot adjust the time of the timesheet for a project with timesheets disabled."))

            self.create({
                'name': self.env.context.get('default_name', '/'),
                'project_id': project_id,
                field_name: field_value,
                measure_field_name: value,
            })

    @api.ondelete(at_uninstall=False)
    def _unlink_if_manager(self):
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver') and self.filtered(
                lambda r: r.project_id and r.validated):
            raise AccessError(_('You cannot delete a validated entry. Please contact your manager or your timesheet approver.'))

        self.check_if_allowed(delete=True)

    @api.model
    def _get_rounding_values(self):
        return {
            'minimum': self.env['ir.config_parameter'].sudo().get_int('timesheet_grid.timesheet_min_duration', 15),
            'rounding': self.env['ir.config_parameter'].sudo().get_int('timesheet_grid.timesheet_rounding', 15),
        }

    @api.model
    def _get_aw_timesheet_fields_specification(self):
        return {
            'id': {},
            'name': {},
            'date': {},
            'user_id': {
                'fields': {'display_name': {}},
            },
            'project_id': {
                'fields': {'display_name': {}},
            },
            'task_id': {
                'fields': {'display_name': {}},
            },
            'unit_amount': {},
            'company_id': {
                'fields': {'display_name': {}},
            },
        }

    @api.model
    def get_aw_timesheet_data(self, date):
        date = fields.Date.from_string(date)
        specification = self._get_aw_timesheet_fields_specification()
        employee = self.env.user.employee_id
        if not employee:
            return {'specification': specification, 'timesheets': [], 'working_hours': False}

        domain = [('date', '=', date), ('user_id', '=', self.env.user.id), ('project_id', '!=', False)]
        timesheets = self.web_search_read(domain, specification)

        if not employee.sudo()._is_fully_flexible(date):
            tz = ZoneInfo(self.env.context.get('tz') or 'UTC')
            start = datetime.combine(date, time.min).replace(tzinfo=tz)
            end = datetime.combine(date, time.max).replace(tzinfo=tz)
            working_hours = employee._get_work_days_data_batch(start, end, False)[employee.id]['hours']
        else:
            working_hours = None
        return {'specification': specification, 'timesheets': timesheets, 'working_hours': working_hours}

    @api.model
    def _get_assistant_events_getters(self):
        """
        Intended to be overridden in other modules to add methods that provide
        events to send to the timesheets assistant.

        Each event must be a dictionary containing the following keys:

        - ``start`` (:class:`datetime.datetime`): Event start datetime.
        - ``stop`` (:class:`datetime.datetime`): Event end datetime.
        - ``duration`` (:class:`float`, optional): Event duration.
                If not passed, it will be computed from `start` and `stop`.
        - ``name`` (:class:`str`): Translated label displayed in the assistant.
        - ``type`` (:class:`str`): Classification string. Must be one of the values
        defined in ``aw.rule.type``.

        It is assumed that events are sorted by increasing start time.
        It is however not assumed that they don't overlap.

        :returns: A dictionary of the form ``{"sequence": int, "getter": function}``
                containing the event getters. Events from getters with a lower sequence
                will have higher precedence.
        :rtype: dict
        """
        return []

    @api.model
    def _normalize_events(self, events):
        """
        Normalize a list of events by removing overlaps. When two events overlap,
        the earlier event takes priority and the later one is clipped so that no
        overlap remains. Events fully covered by a previous one are discarded.

        The input list is expected to be ordered by increasing ``start`` time.

        :param events: List of event dictionaries. Each event must contain at
            least ``start`` and ``stop`` datetime values.
        :type events: list[dict]
        :returns: A new list of events, ordered and guaranteed to have no
            overlapping time ranges.
        :rtype: list[dict]
        """
        if not events:
            return []
        res = [events[0]]
        for event in events[1:]:
            prev = res[-1]
            if event['start'] >= prev['stop']:
                res.append(event)
            elif event['stop'] > prev['stop']:
                clipped = event.copy()
                clipped['start'] = prev['stop']
                if 'duration' in clipped:
                    clipped['duration'] = (clipped['stop'] - clipped['start']).total_seconds() / 3600.0
                res.append(clipped)

        return res

    def get_assistant_events(self, day):
        def merge(ranges, intervals_to_include):
            if len(intervals_to_include) == 0:
                return ranges

            size = len(ranges)
            if size == 0:
                return intervals_to_include

            gaps = []
            if intervals_to_include[0]['start'] < ranges[0]['start']:
                gaps.append((intervals_to_include[0]['start'], ranges[0]['start']))

            for i in range(size - 1):
                if ranges[i]['stop'] < ranges[i + 1]['start']:
                    gaps.append((ranges[i]['stop'], ranges[i + 1]['start']))

            if intervals_to_include[-1]['stop'] > ranges[-1]['stop']:
                gaps.append((ranges[-1]['stop'], intervals_to_include[-1]['stop']))

            j = 0
            res = ranges
            for gap in gaps:
                # advance if ranges not intersecting with gap
                while j < len(intervals_to_include) and intervals_to_include[j]['stop'] <= gap[0]:
                    j += 1

                # move to next gap if no ranges intersecting with the gap
                while j < len(intervals_to_include) and intervals_to_include[j]['start'] < gap[1]:
                    interval = deepcopy(intervals_to_include[j])
                    interval['start'] = max(gap[0], interval['start'])
                    interval['stop'] = min(gap[1], interval['stop'])
                    if 'duration' in interval:
                        interval['duration'] = (interval['stop'] - interval['start']).total_seconds() / 3600.0
                    res.append(interval)
                    j += 1

            return sorted(res, key=lambda r: r['start'])

        start = datetime.strptime(day, DEFAULT_SERVER_DATE_FORMAT)
        end = (start + relativedelta(days=1))
        ranges = []
        event_getters = self._get_assistant_events_getters()
        for event_getter in (g['getter'] for g in sorted(event_getters, key=lambda g: g['sequence'])):
            events = event_getter(start, end)
            ranges = merge(ranges, self._normalize_events(events))

        return ranges

    @api.model
    def _get_url_regex_for_models(self, model_names):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url')
        # Base users may not have access
        actions = self.env['ir.actions.act_window'].sudo().search([
            ('res_model', 'in', model_names),
            ('path', '!=', False),
        ])

        model_paths = defaultdict(set)
        for action in actions:
            model_paths[action.res_model].add(action.path)

        regexes = {}
        for model in model_names:
            parts = list(map(re.escape, model_paths[model]))
            parts.append(re.escape(model))
            regexes[model] = rf"{re.escape(base_url)}/odoo/(?:[^/?#]+/)*(?:{'|'.join(parts)})/(\d+)(?:\?|$)"

        return regexes

    @api.model
    def _get_assistant_odoo_models(self):
        return {
            'project.task': {
                'label': self.env._('Task'),
                'template': self.env._('Working on $1'),
                'target': {
                    'type': 'self',
                },
            },
            'project.project': {
                'label': self.env._('Project'),
                'template': self.env._('Working on $1'),
                'target': {
                    'type': 'self',
                },
            },
        }

    @api.model
    @api.ormcache('self.env.lang')
    def _get_app_lookup_dictionary(self):
        """
        Build a lookup dictionary mapping action IDs, models, and action paths
        to the name of an application module (Sales, Project, etc.).
        """
        action_dict = self._map_actions_from_menus()
        module_to_app = self._map_modules_to_apps()
        valid_modules = list(module_to_app.keys())
        model_dict = self._map_models_to_apps()
        action_dict = self._map_fallback_actions(action_dict, module_to_app, valid_modules)

        path_dict = {}
        final_action_dict = {}

        if action_ids := [int(k) for k in action_dict]:
            actions = self.env['ir.actions.act_window'].sudo().search_read(
                [('id', 'in', action_ids)],
                ['id', 'res_model', 'path']
            )

            for action in actions:
                action_id_str = str(action['id'])
                app_name = action_dict.get(action_id_str)
                res_model = action.get('res_model')
                path = action.get('path')

                if app_name:
                    final_action_dict[action_id_str] = {
                        'app_name': app_name,
                        'res_model': res_model
                    }

                    if path:
                        path_dict[path] = {
                            'app_name': app_name,
                            'res_model': res_model
                        }

        path_dict['spreadsheet'] = {'app_name': self.env._("Spreadsheet"), 'res_model': 'documents.document'}
        return {
            'actions': final_action_dict,
            'models': model_dict,
            'paths': path_dict
        }

    @api.model
    def _map_actions_from_menus(self):
        """Map actions to the source application through the menu hierarchy."""
        menus = self.env['ir.ui.menu'].sudo().search_read(
            [], ['id', 'parent_id', 'action', 'name']
        )
        menu_dict = {m['id']: m for m in menus}

        def get_root_menu_name(menu_id):
            current = menu_dict.get(menu_id)
            while current and current.get('parent_id'):
                current = menu_dict.get(current['parent_id'][0])
            return current['name'] if current else None

        action_dict = {}
        for m in menus:
            if m.get('action') and m['action'].startswith('ir.actions.act_window,'):
                action_id = m['action'].split(',')[1]
                root_name = get_root_menu_name(m['id'])
                if root_name:
                    action_dict[action_id] = root_name

        return action_dict

    @api.model
    # We can cache this because if installed modules change, the cache is wiped
    # Caching also ensures the mapping is deterministic (which it probably will be regardless, but better be safe)
    # Keyed on lang since shortdesc (used as the app display name) is a translated field.
    @api.ormcache('self.env.lang')
    def _map_modules_to_apps(self):
        """
        Map modules to their first ancestor module we can find that is an application.
        Note that this is a bit naive since we stop at the first found application, which may
        or may not be the application that additions of the module actually appear in.
        In practice, cases where this causes inaccuracies should be pretty rare.
        """
        modules = self.env['ir.module.module'].sudo().search_fetch(
            [('state', '=', 'installed')], ['name', 'shortdesc', 'application']
        )
        deps = self.env['ir.module.module.dependency'].sudo().search_fetch(
            [('module_id', 'in', modules.ids)], ['module_id', 'name']
        )

        name_to_id = {m.name: m.id for m in modules}
        deps_map = {}
        for d in deps:
            deps_map.setdefault(d.module_id.id, []).append(d.name)

        apps = {m.name: m.shortdesc for m in modules if m.application}

        def resolve_app(mod_name, visited=None):
            if visited is None:
                visited = set()
            if mod_name in visited:
                return None
            visited.add(mod_name)
            if mod_name in apps:
                return apps[mod_name]
            mod_id = name_to_id.get(mod_name)
            if mod_id:
                for dep_name in deps_map.get(mod_id, []):
                    app_name = resolve_app(dep_name, visited)
                    if app_name:
                        return app_name
            return None

        module_to_app = {}
        for m in modules:
            resolved = resolve_app(m.name)
            if resolved:
                module_to_app[m.name] = resolved

        return module_to_app

    @api.model
    @api.ormcache('self.env.lang')
    def _map_models_to_apps(self):
        """Map models to an application based on the module -> app mapping."""
        module_to_app = self._map_modules_to_apps()
        valid_modules = list(module_to_app.keys())

        models_read = self.env['ir.model'].sudo().search_read([], ['id', 'model'])
        model_id_to_name = {m['id']: m['model'] for m in models_read}

        data = self.env['ir.model.data'].sudo().search_read(
            [
                ('model', '=', 'ir.model'),
                ('module', 'in', valid_modules)
            ],
            ['res_id', 'module']
        )

        model_dict = {}
        for d in data:
            res_id = d.get('res_id')
            if not res_id:
                continue
            if res_id in model_id_to_name:
                model_name = model_id_to_name[res_id]
                if model_name not in model_dict:
                    model_dict[model_name] = module_to_app[d['module']]

        return model_dict

    @api.model
    def _map_fallback_actions(self, action_dict, module_to_app, valid_modules):
        """Map actions we can't link to a menu to an application based on the module -> app mapping."""
        data = self.env['ir.model.data'].sudo().search_read(
            [
                ('model', '=', 'ir.actions.act_window'),
                ('module', 'in', valid_modules)
            ],
            ['res_id', 'module']
        )

        for d in data:
            res_id = d.get('res_id')
            if not res_id:
                continue
            action_id = str(res_id)
            if action_id not in action_dict:
                action_dict[action_id] = module_to_app[d['module']]

        return action_dict

    @deprecated("_get_app_lookup_dictionary now does this")
    @api.model
    def _extract_action_paths(self, action_dict):
        """
        Extract the paths of actions that have one into their own dict
        """
        action_ids = [int(k) for k in action_dict]
        path_actions = self.env['ir.actions.act_window'].sudo().search_read(
            [('id', 'in', action_ids), ('path', '!=', False)],
            ['id', 'path']
        )
        path_dict = {
            pa['path']: action_dict[str(pa['id'])]
            for pa in path_actions if pa.get('path')
        }

        return path_dict

    @api.model
    def _get_assistant_odoo_models_data(self):
        models = self._get_assistant_odoo_models()
        url_regexes = self._get_url_regex_for_models(list(models.keys()))
        return [{
            'model': model_name,
            'label': values['label'],
            'url_regex': url_regexes[model_name],
            'type': 'odoo',
            'template': values.get('template', self.env._('Working on $1')),
        } for model_name, values in models.items()]

    @api.model
    def resolve_assistant_models_targets(self, ids_per_model):
        models_data = self._get_assistant_odoo_models()

        results = {}
        records_per_model = {}

        for model_name, ids in ids_per_model.items():
            rule = models_data.get(model_name, {}).get('target')
            if not rule:
                continue

            records = self.env[model_name].browse(ids).exists()
            records_per_model[model_name] = records

        task_ids = set()
        project_ids = set()
        for model_name, records in records_per_model.items():
            rule = models_data[model_name]['target']

            for rec in records:
                if rule['type'] == 'self':
                    if model_name == 'project.task':
                        task_ids.add(rec.id)
                        if rec.project_id:
                            project_ids.add(rec.project_id.id)
                    elif model_name == 'project.project':
                        project_ids.add(rec.id)

                elif rule['type'] == 'field':
                    target = rec[rule['field']]
                    if target:
                        if rule['target_model'] == 'project.task':
                            task_ids.add(target.id)
                            if target.project_id:
                                project_ids.add(target.project_id.id)
                        elif rule['target_model'] == 'project.project':
                            project_ids.add(target.id)

        task_data = {t.id: t for t in self.env['project.task'].browse(task_ids)}
        project_data = {p.id: p for p in self.env['project.project'].browse(project_ids)}

        for model_name, records in records_per_model.items():
            rule = models_data[model_name]['target']
            results[model_name] = {}
            for rec in records:
                target = {'task_id': None, 'task_name': None, 'project_id': None, 'project_name': None, 'allow_timesheets': True}

                if rule['type'] == 'self':
                    if model_name == 'project.task':
                        target.update({
                            'task_id': rec.id,
                            'task_name': rec.name,
                            'project_id': rec.project_id.id if rec.project_id else None,
                            'project_name': rec.project_id.name if rec.project_id else None,
                            'allow_timesheets': rec.project_id.allow_timesheets if rec.project_id else True,
                        })
                    elif model_name == 'project.project':
                        target.update({
                            'project_id': rec.id,
                            'project_name': rec.name,
                            'allow_timesheets': rec.allow_timesheets,
                        })
                elif rule['type'] == 'field':
                    target_rec = rec[rule['field']]
                    if target_rec:
                        if rule['target_model'] == 'project.task':
                            t = task_data[target_rec.id]
                            target.update({
                                'task_id': t.id,
                                'task_name': t.name,
                                'project_id': t.project_id.id if t.project_id else None,
                                'project_name': t.project_id.name if t.project_id else None,
                                'allow_timesheets': t.project_id.allow_timesheets if t.project_id else True,
                            })
                        elif rule['target_model'] == 'project.project':
                            p = project_data[target_rec.id]
                            target.update({
                                'project_id': p.id,
                                'project_name': p.name,
                                'allow_timesheets': p.allow_timesheets,
                            })
                    target['source_record_name'] = rec.display_name

                results[model_name][rec.id] = target

        return results

    @api.model
    def _get_timesheeted_project_task_by_partner(self, partners):
        if not partners:
            return {}

        timesheet_groups = self.env['account.analytic.line']._read_group(
            domain=[
                ('user_id', '=', self.env.user.id),
                ('partner_id.commercial_partner_id', 'in', partners.commercial_partner_id.ids),
                ("project_id", "!=", False),
                ('project_id.allow_timesheets', '=', True),
            ],
            groupby=['partner_id', 'project_id', 'task_id'],
            aggregates=['date:max'],
            order='date:max desc',
        )

        project_task_by_tree = {}
        for partner, project, task, date_max in timesheet_groups:
            root = partner.commercial_partner_id.id
            if root not in project_task_by_tree:
                project_task_by_tree[root] = (project.id, task.id, date_max)

        if missing_partners := partners.filtered(lambda partner: partner.commercial_partner_id.id not in project_task_by_tree):
            fallback_tasks = self.env['project.task'].search_fetch(
                domain=[
                    ('partner_id.commercial_partner_id', 'in', missing_partners.commercial_partner_id.ids),
                    ('project_id', '!=', False),
                    ('allow_timesheets', '=', True),
                ],
                field_names=['partner_id', 'project_id'],
                order='id desc',
            )

            for task in fallback_tasks:
                root = task.partner_id.commercial_partner_id.id
                if root not in project_task_by_tree or project_task_by_tree[root][1] < task.id:
                    project_task_by_tree[root] = (task.project_id.id, task.id, None)

            if missing_partners := missing_partners.filtered(lambda partner: partner.commercial_partner_id.id not in project_task_by_tree):
                for project in self.env['project.project'].search_fetch(
                    domain=[
                        ('partner_id.commercial_partner_id', 'in', missing_partners.commercial_partner_id.ids),
                        ('allow_timesheets', '=', True),
                    ],
                    field_names=['partner_id'],
                    order='id desc',
                ):
                    root = project.partner_id.commercial_partner_id.id
                    if root not in project_task_by_tree or project_task_by_tree[root][0] < project.id:
                        project_task_by_tree[root] = (project.id, None, None)

        return {
            partner.id: project_task_by_tree.get(partner.commercial_partner_id.id, (None, None, None))
            for partner in partners
        }

    @api.model
    def resolve_gmail_partners(self, emails):
        if not emails:
            return {}

        partner_by_email = {}
        Partner = self.env['res.partner']
        partners = Partner
        for partner in Partner.search([
            ('email', 'in', list(emails)),
            ('id', '!=', self.env.user.partner_id.id),
        ]):
            if not (currentPartner := partner_by_email.get(partner.email)):
                partner_by_email[partner.email] = partner
                partners |= partner
            elif partner.email in partner.user_ids.mapped('login'):
                partner_by_email[partner.email] = partner
                partners -= currentPartner
                partners |= partner

        resolved = self._get_timesheeted_project_task_by_partner(partners)
        partner_email_to_data = {}
        for partner in partners:
            project_id, task_id, _ = resolved.get(partner.id, (False, False, None))
            partner_email_to_data[partner.email] = {
                'partner_name': partner.name,
                'project_id': project_id,
                'task_id': task_id,
            }

        return partner_email_to_data

    @api.model
    def get_assistant_data(self):
        return {
            'rounding_values': self._get_rounding_values(),
            'odoo_models_data': self._get_assistant_odoo_models_data(),
        }

    @api.model
    def get_aw_app_from_urls(self, urls):
        """
        Receive a list of Odoo URLs from the assistant, and try to match them
        to the corresponding Odoo application name and record name.
        """
        if not urls:
            return {}

        app_dictionary = self._get_app_lookup_dictionary()
        resolved_urls = {}

        def get_app_and_model_from_segment(seg):
            """Checks if a URL segment matches a model, path, or action."""
            if seg in app_dictionary['models']:
                return app_dictionary['models'][seg], seg

            if seg in app_dictionary['paths']:
                return app_dictionary['paths'][seg]['app_name'], app_dictionary['paths'][seg]['res_model']

            action_match = re.match(r'^action-(\d+)$', seg)
            if action_match:
                action_id = action_match.group(1)
                if action_id in app_dictionary['actions']:
                    return app_dictionary['actions'][action_id]['app_name'], app_dictionary['actions'][action_id]['res_model']

            return None, None

        for url in urls:
            parsed_url = urlsplit(url)
            path_segments = [s for s in parsed_url.path.split('/') if s]

            fallback_app_name = None
            found_model = None
            record_id = None

            for i in range(len(path_segments) - 1, -1, -1):
                segment = path_segments[i]

                if segment.isdigit() and i > 0:
                    app, model = get_app_and_model_from_segment(path_segments[i - 1])
                    if app:
                        fallback_app_name = app
                        found_model = model
                        record_id = int(segment)
                        break

                app, model = get_app_and_model_from_segment(segment)
                if app:
                    fallback_app_name = app
                    found_model = model
                    break

            record_name = False
            if fallback_app_name:
                if found_model and record_id is not None:
                    try:
                        if found_model in self.env:
                            record = self.env[found_model].browse(record_id)
                            if record:
                                record_name = record.display_name
                    except (AccessError, MissingError):
                        pass

                resolved_urls[url] = {
                    'app_name': fallback_app_name,
                    'record_name': record_name
                }

        return resolved_urls

    def action_round_timesheet_time(self):
        """ Save timesheet inside systray and round time spent

            :return: return the timesheet data saved
        """
        self.unit_amount = round_time_spent(self.unit_amount * 60, **self._get_rounding_values()) / 60
        return self.unit_amount

    def change_description(self, description):
        if not self.exists():
            return
        self.write({'name': description})

    def _get_domain_for_validation_timesheets(self, validated=False):
        """ Get the domain to check if the user can validate/invalidate which timesheets

            2 access rights give access to validate timesheets:

            1. Approver: in this access right, the user can't validate all timesheets,
            he can validate the timesheets where he is the manager or timesheet responsible of the
            employee who is assigned to this timesheets or the user is the owner of the project.
            The user cannot validate his own timesheets.

            2. Manager (Administrator): with this access right, the user can validate all timesheets.

            3. Employee: with this access right, the user can only validate their own timesheets.
        """
        domain = Domain('project_id', '!=', False) & Domain('validated', '=', validated)
        if not validated:
            domain &= Domain("date", "<=", 'today')

        if not self.env.user.has_group('hr_timesheet.group_timesheet_manager'):
            domain = Domain.AND([
                domain,
                Domain('user_id', '!=', self.env.uid),
                [
                    '|', ('employee_id.timesheet_manager_id', 'in', [False, self.env.uid]),
                    '|', ('employee_id', 'in', self.env.user.employee_id.subordinate_ids.ids),
                    '|', ('employee_id.parent_id.user_id', '=', self.env.uid),
                    '&', ('employee_id.timesheet_manager_id', '=', False), ('employee_id.parent_id', '=', False),
                ],
            ])

        if self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
            domain |= Domain('user_id', '=', self.env.uid) & Domain([
                '|',
                ('employee_id.timesheet_manager_id', '=', self.env.uid),
                ('employee_id.parent_id.user_id', '=', self.env.uid)
            ])

        return domain

    def _get_timesheets_to_merge(self):
        return self.filtered(lambda l: l.project_id and not l.validated)

    def action_merge_timesheets(self):
        to_merge = self._get_timesheets_to_merge()

        if len(to_merge) <= 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('There are no timesheets to merge.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'name': _('Merge Timesheets'),
            'view_mode': 'form',
            'res_model': 'hr_timesheet.merge.wizard',
            'views': [(self.env.ref('timesheet_grid.timesheet_merge_wizard_view_form').id, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': dict(self.env.context, active_ids=to_merge.ids),
        }

    @api.model
    def _get_recently_used_records(self, groupby_field, domain=None, limit=8):
        grouped_data = self._read_group(
            domain=domain or [],
            groupby=[groupby_field],
            aggregates=['write_date:max'],
            order='write_date:max desc',
            limit=limit,
        )
        return [(record.id, record.display_name) for record, _write_date in grouped_data if record]
