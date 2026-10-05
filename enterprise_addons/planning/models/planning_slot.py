# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone, UTC
from math import modf
from random import shuffle
from zoneinfo import ZoneInfoNotFoundError, ZoneInfo

from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Datetime, Domain
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, SQL, LazyTranslate, float_utils, format_datetime, get_lang, babel_locale_parse, format_time, format_date, format_list
from odoo.tools.date_utils import float_to_time, get_timedelta, sum_intervals, weeknumber
from odoo.tools.intervals import Intervals

from odoo.addons.resource.models.utils import filter_map_domain, get_light_color

_lt = LazyTranslate(__name__)


def days_span(start_datetime, end_datetime):
    if not isinstance(start_datetime, datetime):
        raise TypeError
    if not isinstance(end_datetime, datetime):
        raise TypeError
    end = datetime.combine(end_datetime, datetime.min.time())
    start = datetime.combine(start_datetime, datetime.min.time())
    duration = end - start
    return duration.days + 1


class PlanningSlot(models.Model):
    _name = 'planning.slot'
    _description = 'Planning Shift'
    _order = 'start_datetime desc, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    def _default_start_datetime(self):
        return datetime.combine(fields.Date.context_today(self), time.min)

    def _default_end_datetime(self):
        return datetime.combine(fields.Date.context_today(self), time.max)

    name = fields.Text('Note')
    resource_ids = fields.Many2many('resource.resource', string='Resources', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", group_expand='_group_expand_resource_ids', inverse='_inverse_resource_ids', falsy_value_label=_lt('Open Shifts'))
    resource_roles = fields.Many2many(related='resource_ids.role_ids', string="Resource Roles")
    employee_ids = fields.Many2many('hr.employee', 'Employees', compute='_compute_employee_ids', search='_search_employee_ids', compute_sudo=True)
    employee_public_ids = fields.Many2many('hr.employee.public', compute='_compute_employee_ids', search='_search_employee_ids', compute_sudo=True, export_string_translation=False)
    department_id = fields.Many2one('hr.department', string='Departments', compute='_compute_department_id', store=True, falsy_value_label=_lt('Open Shifts'))
    user_ids = fields.Many2many('res.users', string="Users", compute='_compute_user_ids', search='_search_user_ids')
    manager_id = fields.Many2one('hr.employee', string="Manager", compute='_compute_manager_id', store=True, falsy_value_label=_lt('Open Shifts'))
    company_id = fields.Many2one('res.company', string="Company", required=True, index=True, compute="_compute_planning_slot_company_id", store=True, readonly=False)
    role_id = fields.Many2one('planning.role', string="Role", compute="_compute_role_id", store=True, index='btree_not_null', readonly=False, copy=True, group_expand='_read_group_role_id',
        help="Define the roles your resources will perform (e.g. Chef, Bartender, Waiter). Create open shifts based on the roles needed for a mission, then assign those shifts to available resources.")
    color = fields.Integer("Color", related='role_id.color')
    was_copied = fields.Boolean("This Shift Was Copied From Previous Week", default=False, readonly=True)
    access_token = fields.Char(default=lambda self: str(uuid.uuid4()), required=True, copy=False, readonly=True, export_string_translation=False, init_storage='_init_column_access_token')

    start_datetime = fields.Datetime(
        "Start Date", compute='_compute_datetime', store=True, readonly=False,
        copy=True)
    end_datetime = fields.Datetime(
        "End Date", compute='_compute_datetime', store=True, readonly=False,
        copy=True)
    # UI fields and warnings
    allow_self_unassign = fields.Boolean('Let Employee Unassign Themselves', compute='_compute_allow_self_unassign')
    self_unassign_days_before = fields.Integer(
        "Days before shift for unassignment",
        related="company_id.planning_self_unassign_days_before",
    )
    unassign_deadline = fields.Datetime('Deadline for unassignment', compute="_compute_unassign_deadline", export_string_translation=False)
    is_unassign_deadline_passed = fields.Boolean(compute="_compute_is_unassign_deadline_passed", export_string_translation=False)
    conflicting_slot_ids = fields.Many2many('planning.slot', compute='_compute_overlap_slot_count', export_string_translation=False)
    overlap_slot_count = fields.Integer(compute='_compute_overlap_slot_count', search='_search_overlap_slot_count', export_string_translation=False)
    is_past = fields.Boolean('Is This Shift In The Past?', compute='_compute_past_shift', export_string_translation=False)
    is_users_role = fields.Boolean('Is the shifts role one of the current user roles', compute='_compute_is_users_role', search='_search_is_users_role', export_string_translation=False)
    switch_employee_ids = fields.Many2many('hr.employee', 'planning_slot_switch_hr_employee_rel', copy=False, export_string_translation=False)
    request_to_switch = fields.Boolean(compute="_compute_request_to_switch_msg", compute_sudo=True, export_string_translation=False)
    is_user_switching = fields.Boolean(compute='_compute_request_to_switch_msg', compute_sudo=True, export_string_translation=False)
    request_to_switch_msg = fields.Char(compute="_compute_request_to_switch_msg", compute_sudo=True, export_string_translation=False)
    resources_without_correct_role = fields.Char('What resource has not the right role', compute="_compute_resources_without_correct_role", export_string_translation=False)
    resources_without_correct_role_count = fields.Integer('Number of resources that do not have the right role', compute="_compute_resources_without_correct_role")
    # time allocation
    allocation_type = fields.Selection([
        ('planning', 'Planning'),
        ('forecast', 'Forecast'),
    ], compute='_compute_allocation_type')
    allocated_hours = fields.Float("Allocated Time", compute='_compute_allocated_hours', store=True, readonly=False)
    allocated_percentage = fields.Float("Allocated Time %", default=100,
        compute='_compute_allocated_percentage', store=True, readonly=False,
        aggregator="avg")
    duration = fields.Float("Duration", compute="_compute_slot_duration")

    # publication and sending
    publication_warning = fields.Boolean(
        "Modified Since Last Publication", default=False, compute='_compute_publication_warning',
        store=True, readonly=True, copy=False,
        help="If checked, it means that the shift contains has changed since its last publish.")
    state = fields.Selection([
            ('1_draft', 'Draft'),
            ('2_published', 'Scheduled'),
    ], string='Status', default='1_draft', copy=False)
    # template dummy fields (only for UI purpose)
    template_creation = fields.Boolean("Save as Template", store=False, inverse='_inverse_template_creation')
    template_autocomplete_ids = fields.Many2many('planning.slot.template', store=False, compute='_compute_template_autocomplete_ids', export_string_translation=False)
    template_id = fields.Many2one('planning.slot.template', string='Shift Templates', compute='_compute_template_id', readonly=False, store=True, index='btree_not_null')
    template_reset = fields.Boolean(export_string_translation=False)
    previous_template_id = fields.Many2one('planning.slot.template', export_string_translation=False)
    allow_template_creation = fields.Boolean(string='Allow Template Creation', compute='_compute_allow_template_creation', export_string_translation=False)

    # Recurring (`repeat_` fields are none stored, only used for UI purpose)
    recurrency_id = fields.Many2one('planning.recurrency', readonly=True, index=True, ondelete="set null", copy=False, export_string_translation=False)
    repeat = fields.Boolean("Repeat", compute='_compute_repeat', inverse='_inverse_repeat',
        help="To avoid polluting your database and performance issues, shifts are only created for the next 6 months. They are then gradually created as time passes by in order to always get shifts 6 months ahead. This value can be modified from the settings of Planning, in debug mode.")
    repeat_interval = fields.Integer("Repeat every", default=1, compute='_compute_repeat_interval', inverse='_inverse_repeat')
    repeat_unit = fields.Selection([
        ('day', 'Days'),
        ('week', 'Weeks'),
        ('month', 'Months'),
        ('year', 'Years'),
    ], default='week', compute='_compute_repeat_unit', inverse='_inverse_repeat', required=True)
    repeat_type = fields.Selection([('forever', 'Forever'), ('until', 'Until'), ('x_times', 'Number of Occurrences')],
        string='Repeat Type', default='forever', compute='_compute_repeat_type', inverse='_inverse_repeat')
    repeat_until = fields.Date("Repeat Until", compute='_compute_repeat_until', inverse='_inverse_repeat')
    repeat_number = fields.Integer("Repetitions", default=1, compute='_compute_repeat_number', inverse='_inverse_repeat')
    recurrence_update = fields.Selection([
        ('this', 'This shift'),
        ('subsequent', 'This and following shifts'),
        ('all', 'All shifts'),
    ], default='this', store=False)
    confirm_delete = fields.Boolean(compute='_compute_confirm_delete', export_string_translation=False)
    can_edit = fields.Boolean(compute='_compute_can_edit', export_string_translation=False)

    is_hatched = fields.Boolean(compute='_compute_is_hatched', export_string_translation=False)

    slot_properties = fields.Properties('Properties', definition='role_id.slot_properties_definition', precompute=False)

    _check_start_date_lower_end_date = models.Constraint(
        'CHECK(end_datetime > start_datetime)',
        "The end date of a shift should be after its start date.",
    )
    _check_allocated_hours_positive = models.Constraint(
        'CHECK(allocated_hours >= 0)',
        "Allocated hours and allocated time percentage cannot be negative.",
    )

    def _inverse_resource_ids(self):
        for slot in self:
            if slot.state == '1_draft' and slot.resource_ids and not slot.employee_public_ids:
                slot.state = '2_published'
            if slot.env.context.get('add_materials_assigned_to_employees'):
                materials_to_add = slot.resource_ids.get_materials_assigned_to_human_resources()
                slot.with_context(add_materials_assigned_to_employees=False).resource_ids |= materials_to_add

    @api.depends('resource_ids')
    def _compute_employee_ids(self):
        for slot in self:
            slot.employee_ids = slot.resource_ids.filtered(lambda r: r.resource_type == 'user').employee_id
            slot.employee_public_ids = self.env['hr.employee.public'].browse(slot.employee_ids.ids)

    def _search_employee_ids(self, operator, value):
        return [('resource_ids', 'any', [('employee_id', operator, value), ('resource_type', '=', 'user')])]

    @api.depends('resource_ids')
    def _compute_user_ids(self):
        for slot in self:
            slot.user_ids = slot.resource_ids.user_id

    def _search_user_ids(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        return [('resource_ids.user_id', operator, value)]

    @api.depends('resource_ids')
    def _compute_department_id(self):
        for slot in self:
            max_employees_count = 0
            selected_department = False
            for department, employees in slot.employee_ids.grouped('department_id').items():
                if max_employees_count < len(employees):
                    selected_department = department
                    max_employees_count = len(employees)
            slot.department_id = selected_department

    @api.depends('resource_ids')
    def _compute_manager_id(self):
        for slot in self:
            max_employees_count = 0
            selected_manager = False
            for manager, employees in slot.employee_ids.grouped('parent_id').items():
                if max_employees_count < len(employees):
                    selected_manager = manager
                    max_employees_count = len(employees)
            slot.manager_id = selected_manager

    @api.depends('repeat_until')
    def _compute_confirm_delete(self):
        for slot in self:
            if slot.recurrency_id and slot.repeat_until:
                slot.confirm_delete = fields.Date.to_date(slot.recurrency_id.slot_ids.sorted('end_datetime')[-1].end_datetime) > slot.repeat_until
            else:
                slot.confirm_delete = False

    @api.depends_context('uid')
    def _compute_can_edit(self):
        self.can_edit = self.env.user.has_group('planning.group_planning_manager')

    @api.constrains('repeat_until')
    def _check_repeat_until(self):
        if any(slot.repeat_until and slot.repeat_until < slot.start_datetime.date() for slot in self):
            raise UserError(self.env._(
                "Uh-oh! Let's keep things in the right order: the recurrence end date should always "
                "come after the shift start date. It's like trying to eat your breakfast before waking up - not possible!"
            ))

    @api.onchange('repeat_until')
    def _onchange_repeat_until(self):
        self._check_repeat_until()

    @api.depends('resource_ids.company_id')
    def _compute_planning_slot_company_id(self):
        for slot in self:
            company = slot.company_id or slot.env.company
            if len(slot.resource_ids.company_id) == 1:
                company = slot.resource_ids.company_id
            slot.company_id = company

    @api.depends('end_datetime')
    def _compute_past_shift(self):
        now = fields.Datetime.now()
        for slot in self:
            if slot.end_datetime:
                if slot.end_datetime < now:
                    slot.is_past = True
                else:
                    slot.is_past = False
            else:
                slot.is_past = False

    @api.depends('resource_ids', 'template_id')
    def _compute_role_id(self):
        for slot in self:
            if not slot.role_id and slot.resource_ids:
                max_count = 0
                selected_role = False
                for role, resources in slot.resource_ids.grouped('default_role_id').items():
                    if max_count < len(resources):
                        max_count = len(resources)
                        selected_role = role
                slot.role_id = selected_role

            if slot.template_id:
                slot.previous_template_id = slot.template_id
                if slot.template_id.role_id:
                    slot.role_id = slot.template_id.role_id
            elif slot.previous_template_id and not slot.template_id and slot.previous_template_id.role_id == slot.role_id:
                slot.role_id = False

    @api.depends_context('uid', 'lang')
    @api.depends('switch_employee_ids')
    def _compute_request_to_switch_msg(self):
        for slot in self:
            message = ""
            is_user_switching = False
            if slot.switch_employee_ids:
                is_user_switching = bool(slot.switch_employee_ids & self.env.user.all_employee_ids)
                employees_to_switch = slot.switch_employee_ids
                if len(employees_to_switch) == 1:
                    message = self.env._("%s is looking for a replacement", employees_to_switch.name)
                elif employees_to_switch:
                    message = self.env._("%s are looking for a replacement", employees_to_switch.mapped('name'))
            slot.request_to_switch_msg = message
            slot.is_user_switching = is_user_switching
            slot.request_to_switch = bool(slot.switch_employee_ids)

    @api.depends('state')
    def _compute_is_hatched(self):
        for slot in self:
            slot.is_hatched = slot.state == '1_draft'

    @api.depends('role_id')
    def _compute_is_users_role(self):
        user_resource_roles = self.env['resource.resource'].search([('user_id', '=', self.env.user.id)]).role_ids
        for slot in self:
            slot.is_users_role = (slot.role_id in user_resource_roles) or not user_resource_roles or not slot.role_id

    def _search_is_users_role(self, operator, value):
        if operator != 'in':
            return NotImplemented
        user_resource_roles = self.env['resource.resource'].search([('user_id', '=', self.env.user.id)]).role_ids
        if not user_resource_roles:
            return [(1, '=', 1)]
        return ['|', ('role_id', 'in', user_resource_roles.ids), ('role_id', '=', False)]

    @api.depends('start_datetime', 'end_datetime')
    def _compute_allocation_type(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime and slot._get_slot_duration() < 24:
                slot.allocation_type = 'planning'
            else:
                slot.allocation_type = 'forecast'

    @api.depends('allocated_hours')
    def _compute_allocated_percentage(self):
        # [TW:Cyclic dependency] allocated_hours,allocated_percentage
        # As allocated_hours and allocated percentage have some common dependencies, and are dependant one from another, we have to make sure
        # they are computed in the right order to get rid of undeterministic computation.
        #
        # Allocated percentage must only be recomputed if allocated_hours has been modified by the user and not in any other cases.
        # If allocated hours have to be recomputed, the allocated percentage have to keep its current value.
        # Hence, we stop the computation of allocated percentage if allocated hours have to be recomputed.
        allocated_hours_field = self._fields['allocated_hours']
        slots = self.filtered(lambda slot: not self.env.is_to_compute(allocated_hours_field, slot) and slot.start_datetime and slot.end_datetime and slot.start_datetime != slot.end_datetime)
        if not slots:
            return

        working_hours_per_slot = slots._get_working_hours()
        for slot in slots:
            slot.allocated_percentage = 100 * slot.allocated_hours / working_hours_per_slot[slot.id] if working_hours_per_slot[slot.id] else 100

    def _get_working_hours(self):
        start_utc = min(self.mapped('start_datetime')).replace(tzinfo=UTC)
        end_utc = max(self.mapped('end_datetime')).replace(tzinfo=UTC)
        resources = self.resource_ids
        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources

        resource_work_intervals, calendar_work_intervals = regular_resources._get_valid_work_intervals(start_utc, end_utc, calendars=self.company_id.resource_calendar_id)
        flexible_resources_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(start_utc, end_utc)
        resource_work_intervals.update(flexible_resources_work_intervals)

        working_hours_per_slot = {}
        for slot in self:
            if not slot.resource_ids and slot.allocation_type == 'planning':
                working_hours_per_slot[slot.id] = slot._calculate_slot_duration()
            else:
                working_hours_per_slot[slot.id] = slot._get_working_hours_over_period(start_utc, end_utc, resource_work_intervals, calendar_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week)
        return working_hours_per_slot

    @api.depends(
        'start_datetime', 'end_datetime', 'resource_ids.calendar_id',
        'company_id.resource_calendar_id', 'allocated_percentage')
    def _compute_allocated_hours(self):
        percentage_field = self._fields['allocated_percentage']
        self.env.remove_to_compute(percentage_field, self)
        open_slots = self.filtered(
            lambda s: (s.allocation_type == 'planning' or not s.company_id) and not s.resource_ids
        )
        assigned_slots = self - open_slots
        for slot in open_slots:
            # for each planning slot, compute the duration
            ratio = slot.allocated_percentage / 100.0
            slot.allocated_hours = slot._calculate_slot_duration() * ratio
        if assigned_slots:
            # for forecasted slots, compute the conjunction of the slot resource's work intervals and the slot.
            unplanned_assigned_slots = assigned_slots.filtered_domain([
                '|', ('start_datetime', "=", False), ('end_datetime', "=", False),
            ])
            # Unplanned slots will have allocated hours set to 0.0 as there are no enough information
            # to compute the allocated hours (start or end datetime are mandatory for this computation)
            for slot in unplanned_assigned_slots:
                slot.allocated_hours = 0.0
            planned_assigned_slots = assigned_slots - unplanned_assigned_slots
            if not planned_assigned_slots:
                return
            # if there are at least one slot having start or end date, call the _get_valid_work_intervals
            start_utc = min(planned_assigned_slots.mapped('start_datetime')).replace(tzinfo=UTC)
            end_utc = max(planned_assigned_slots.mapped('end_datetime')).replace(tzinfo=UTC)

            resources = assigned_slots.resource_ids
            flexible_resources = resources.filtered(lambda r: r._is_flexible())
            regular_resources = resources - flexible_resources

            # work intervals per resource are retrieved with a batch
            resource_work_intervals, calendar_work_intervals = regular_resources._get_valid_work_intervals(
                start_utc, end_utc, calendars=assigned_slots.company_id.resource_calendar_id
            )

            flexible_resources_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(start_utc, end_utc)
            resource_work_intervals.update(flexible_resources_work_intervals)

            slots_by_allocated_hours = defaultdict(lambda: self.env['planning.slot'])
            for slot in planned_assigned_slots:
                allocated_hour = slot._get_duration_over_period(
                    slot.start_datetime.replace(tzinfo=UTC), slot.end_datetime.replace(tzinfo=UTC),
                    resource_work_intervals, calendar_work_intervals,
                    flexible_resources_hours_per_day, flexible_resources_hours_per_week,
                    has_allocated_hours=False,
                )
                slots_by_allocated_hours[allocated_hour] |= slot
            for allocated_hours, slots in slots_by_allocated_hours.items():
                slots.allocated_hours = allocated_hours

    @api.depends('start_datetime', 'end_datetime', 'resource_ids')
    def _compute_overlap_slot_count(self):
        planning_manager = self.env.user.has_group('planning.group_planning_manager')
        if all(self._ids):
            self.flush_model(['start_datetime', 'end_datetime', 'resource_ids'])
            query = """
                SELECT S1.id, ARRAY_AGG(DISTINCT S2.id) AS conflict_ids
                  FROM planning_slot S1
                  JOIN planning_slot S2
                    ON S1.id != S2.id
                   AND (S1.start_datetime::TIMESTAMP, S1.end_datetime) OVERLAPS (S2.start_datetime::TIMESTAMP, S2.end_datetime)
             LEFT JOIN planning_slot_resource_resource_rel R1
                    ON R1.planning_slot_id = S1.id
             LEFT JOIN planning_slot_resource_resource_rel R2
                    ON R2.planning_slot_id = S2.id
                 WHERE R1.resource_resource_id = R2.resource_resource_id
                   AND S1.allocated_percentage + S2.allocated_percentage > 100
                   AND S1.id in %s
                   AND (%s or S2.state != '1_draft')
                   AND S1.company_id IN %s
                   AND S2.company_id IN %s
              GROUP BY S1.id
            """
            self.env.cr.execute(
                query,
                (
                    tuple(self.ids),
                    planning_manager,
                    tuple(self.env.companies.ids),
                    tuple(self.env.companies.ids),
                ),
            )
            overlap_mapping = dict(self.env.cr.fetchall())
            for slot in self:
                slot_result = overlap_mapping.get(slot.id, [])
                slot.overlap_slot_count = len(slot_result)
                slot.conflicting_slot_ids = [(6, 0, slot_result)] if planning_manager else False
        else:
            # Allow fetching overlap without id if there is only one record
            # This is to allow displaying the warning when creating a new record without having an ID yet
            if len(self) == 1 and self.resource_ids and self.start_datetime and self.end_datetime:
                query = """
                    SELECT ARRAY_AGG(s.id) as conflict_ids
                      FROM planning_slot s
                      JOIN planning_slot_resource_resource_rel r
                        ON r.planning_slot_id = s.id
                     WHERE r.resource_resource_id in %s
                       AND s.start_datetime < %s
                       AND s.end_datetime > %s
                       AND s.allocated_percentage + %s > 100
                       AND (%s or s.state != '1_draft')
                       AND s.company_id in %s
                """
                self.env.cr.execute(
                    query,
                    (
                        tuple(self.resource_ids.ids),
                        self.end_datetime,
                        self.start_datetime,
                        self.allocated_percentage,
                        planning_manager,
                        tuple(self.env.companies.ids),
                    ),
                )
                overlaps = self.env.cr.dictfetchall()
                conflict_slot_ids = overlaps[0]['conflict_ids']
                if conflict_slot_ids:
                    if self._origin:
                        conflict_slot_ids = [slot_id for slot_id in conflict_slot_ids if slot_id != self._origin.id]
                    self.overlap_slot_count = len(conflict_slot_ids)
                    self.conflicting_slot_ids = [(6, 0, conflict_slot_ids)] if planning_manager else False
                else:
                    self.overlap_slot_count = False
                    self.conflicting_slot_ids = False
            else:
                self.overlap_slot_count = False
                self.conflicting_slot_ids = False

    @api.depends("resource_ids.resource_type", "role_id")
    def _compute_resources_without_correct_role(self):
        if not self.env.user.has_group('planning.group_planning_manager'):
            self.resources_without_correct_role = ""
            self.resources_without_correct_role_count = 0
            return

        for shift in self:
            if not shift.role_id:
                shift.resources_without_correct_role = ""
                shift.resources_without_correct_role_count = 0
                continue

            resource_names = []
            for resource in shift.resource_ids.filtered(lambda r: r.resource_type == 'user'):
                if (resource.role_ids and shift.role_id.id not in resource.role_ids.ids):
                    resource_names.append(resource.name)
            shift.resources_without_correct_role = format_list(self.env, resource_names)
            shift.resources_without_correct_role_count = len(resource_names)

    @api.model
    def _search_overlap_slot_count(self, operator, value):
        if operator == 'in':
            return Domain.OR(self._search_overlap_slot_count('=', v) for v in value)
        if operator not in ['=', '>'] or not isinstance(value, int) or value != 0:
            raise NotImplementedError(self.env._('Operation not supported, you should always compare overlap_slot_count to 0 value with = or > operator.'))

        sql = SQL("""(
            SELECT S1.id
            FROM planning_slot S1
            JOIN planning_slot_resource_resource_rel R1
              ON S1.id = R1.planning_slot_id
            WHERE EXISTS (
                SELECT 1
                  FROM planning_slot S2
                JOIN planning_slot_resource_resource_rel R2
                  ON S2.id = R2.planning_slot_id
                 WHERE S1.id <> S2.id
                   AND R1.resource_resource_id = R2.resource_resource_id
                   AND S1.start_datetime < S2.end_datetime
                   AND S1.end_datetime > S2.start_datetime
                   AND S1.allocated_percentage + S2.allocated_percentage > 100
            )
        )""")
        operator_new = "in" if operator == ">" else "not in"
        return [('id', operator_new, sql)]

    @api.depends('start_datetime', 'end_datetime')
    def _compute_slot_duration(self):
        for slot in self:
            slot.duration = slot._get_slot_duration()

    def _get_slot_duration(self):
        """Return the slot (effective) duration expressed in hours.
        """
        self.ensure_one()
        resources = self.resource_ids
        if not self.start_datetime or not self.end_datetime:
            return False
        if not resources:
            return (self.end_datetime - self.start_datetime).total_seconds() / 3600.0

        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        fixed_resources = resources - flexible_resources
        period_per_tz = {
            resource.tz: (
                self.start_datetime.replace(tzinfo=UTC).astimezone(ZoneInfo(resource.tz)),
                self.end_datetime.replace(tzinfo=UTC).astimezone(ZoneInfo(resource.tz)),
            )
            for resource in resources
        }

        effective_duration = 0.0
        if flexible_resources:
            for resource in flexible_resources:
                start, end = period_per_tz[resource.tz]
                work_intervals, hours_per_day, hours_per_week = resource._get_flexible_resource_valid_work_intervals(start, end)
                effective_duration += resource._get_flexible_resource_work_hours(work_intervals[resource.id], hours_per_day[resource.id], hours_per_week[resource.id])
        if fixed_resources:
            for resource in fixed_resources:
                start, end = period_per_tz[resource.tz]
                work_intervals, _dummy = resource._get_valid_work_intervals(start, end)
                effective_duration += sum_intervals(work_intervals[resource.id])
        return effective_duration

    def _get_domain_template_slots(self):
        domain = [('company_id', 'in', [self.company_id.id, False])]
        roles = self.resource_ids.role_ids
        if self.role_id:
            roles |= self.role_id
        if roles:
            domain += ['|', ('role_id', 'in', roles.ids), ('role_id', '=', False)]
        return domain

    @api.depends('role_id', 'resource_ids', 'company_id')
    def _compute_template_autocomplete_ids(self):
        for slot in self:
            domain = slot._get_domain_template_slots()
            templates = self.env['planning.slot.template'].search(domain, order='start_time', limit=10)
            slot.template_autocomplete_ids = templates + slot.template_id

    @api.depends('resource_ids', 'role_id', 'start_datetime', 'end_datetime', 'company_id')
    def _compute_template_id(self):
        for slot in self.filtered(lambda s: s.template_id):
            slot.previous_template_id = slot.template_id
            slot.template_reset = False
            if slot._different_than_template():
                slot.template_id = False
                slot.previous_template_id = False
                slot.template_reset = True

    def _different_than_template(self, check_empty=True):
        self.ensure_one()
        if not (self.start_datetime and self.end_datetime):
            return True
        template_fields = self._get_template_fields().items()
        for template_field, slot_field in template_fields:
            if self.template_id[template_field] or not check_empty:
                if template_field in ('start_time', 'end_time'):
                    h = int(self.template_id[template_field])
                    m = round(modf(self.template_id[template_field])[0] * 60.0)
                    slot_time = self[slot_field].astimezone(ZoneInfo(self._get_tz()))
                    if slot_time.hour != h or slot_time.minute != m:
                        return True
                elif template_field == 'duration_days':
                    if self.start_datetime and self.end_datetime and \
                            days_span(self.start_datetime, self.end_datetime) != self.template_id[template_field]:
                        return True
                elif self[slot_field] != self.template_id[template_field]:
                    return True

        return False

    @api.depends('template_id', 'role_id', 'allocated_hours', 'start_datetime', 'end_datetime')
    def _compute_allow_template_creation(self):
        for slot in self:
            if not (slot.start_datetime and slot.end_datetime):
                slot.allow_template_creation = False
                continue

            values = slot._prepare_template_values()
            domain = [(x, '=', values[x]) for x in values]
            existing_templates = self.env['planning.slot.template'].search(domain, limit=1)
            slot.allow_template_creation = not existing_templates and slot._different_than_template(check_empty=False)

    @api.depends('recurrency_id')
    def _compute_repeat(self):
        for slot in self:
            if slot.recurrency_id:
                slot.repeat = True
            else:
                slot.repeat = False

    @api.depends('recurrency_id.repeat_interval')
    def _compute_repeat_interval(self):
        recurrency_slots = self.filtered('recurrency_id')
        for slot in recurrency_slots:
            if slot.recurrency_id:
                slot.repeat_interval = slot.recurrency_id.repeat_interval
        (self - recurrency_slots).update(self.default_get(['repeat_interval']))

    @api.depends('recurrency_id.repeat_until', 'repeat', 'repeat_type')
    def _compute_repeat_until(self):
        for slot in self:
            repeat_until = False
            if slot.repeat and slot.repeat_type == 'until':
                if slot.recurrency_id and slot.recurrency_id.repeat_until:
                    repeat_until = slot.recurrency_id.repeat_until
                elif slot.start_datetime:
                    repeat_until = slot.start_datetime + relativedelta(weeks=1)
            slot.repeat_until = repeat_until

    @api.depends('recurrency_id.repeat_number', 'repeat_type')
    def _compute_repeat_number(self):
        recurrency_slots = self.filtered('recurrency_id')
        for slot in recurrency_slots:
            slot.repeat_number = slot.recurrency_id.repeat_number
        (self - recurrency_slots).update(self.env['planning.slot'].default_get(['repeat_number']))

    @api.depends('recurrency_id.repeat_unit')
    def _compute_repeat_unit(self):
        non_recurrent_slots = self.env['planning.slot']
        for slot in self:
            if slot.recurrency_id:
                slot.repeat_unit = slot.recurrency_id.repeat_unit
            else:
                non_recurrent_slots += slot
        non_recurrent_slots.update(self.default_get(['repeat_unit']))

    @api.depends('recurrency_id.repeat_type')
    def _compute_repeat_type(self):
        recurrency_slots = self.filtered('recurrency_id')
        for slot in recurrency_slots:
            if slot.recurrency_id:
                slot.repeat_type = slot.recurrency_id.repeat_type
        (self - recurrency_slots).update(self.default_get(['repeat_type']))

    def _inverse_repeat(self):
        for slot in self:
            if slot.repeat and not slot.recurrency_id.id:  # create the recurrence
                repeat_until = False
                repeat_number = 0
                if slot.repeat_type == "until":
                    repeat_until = datetime.combine(fields.Date.to_date(slot.repeat_until), datetime.max.time())
                    repeat_until = repeat_until.replace(tzinfo=ZoneInfo(slot.company_id.tz or 'UTC')).astimezone(UTC).replace(tzinfo=None)
                if slot.repeat_type == 'x_times':
                    repeat_number = slot.repeat_number
                recurrency_values = {
                    'repeat_interval': slot.repeat_interval,
                    'repeat_unit': slot.repeat_unit,
                    'repeat_until': repeat_until,
                    'repeat_number': repeat_number,
                    'repeat_type': slot.repeat_type,
                    'company_id': slot.company_id.id,
                }
                recurrence = self.env['planning.recurrency'].create(recurrency_values)
                slot.recurrency_id = recurrence
                slot.recurrency_id._repeat_slot()
            # user wants to delete the recurrence
            # here we also check that we don't delete by mistake a slot of which the repeat parameters have been changed
            elif not slot.repeat and slot.recurrency_id.id:
                slot.recurrency_id._delete_slot(slot.end_datetime)
                slot.recurrency_id.unlink()  # will set recurrency_id to NULL

    def _inverse_template_creation(self):
        PlanningTemplate = self.env['planning.slot.template']
        for slot in self.filtered(lambda s: s.template_creation):
            values = slot._prepare_template_values()
            domain = [(x, '=', values[x]) for x in values]
            existing_templates = PlanningTemplate.search(domain, limit=1)
            if not existing_templates:
                template = PlanningTemplate.create(values)
                slot.write({'template_id': template.id, 'previous_template_id': template.id})
            else:
                slot.write({'template_id': existing_templates.id})

    def _get_non_working_days_bounds(self, start_datetime, end_datetime, resource=False):
        resource = resource or self.env.user.employee_id.resource_id
        user_tz = ZoneInfo(self.env.user.tz
            or (resource.employee_id and resource.employee_id.tz)
            or resource.tz
            or self.env.context.get('tz')
            or self.env.user.company_id.tz
            or 'UTC'
        )
        start_date_in_user_tz = start_datetime.astimezone(user_tz)
        offset = start_date_in_user_tz.utcoffset().total_seconds() / 3600
        return (
            (start_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None) + timedelta(hours=8 - offset)),
            (end_datetime.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None) + timedelta(hours=17 - offset))
        )

    @api.model
    def _calculate_start_end_dates(self,
                                 start_datetime,
                                 end_datetime,
                                 resource_ids,
                                 template_id,
                                 previous_template_id,
                                 template_reset):
        """
        Calculate the start and end dates for a given planning slot based on various parameters.

        Returns: A tuple containing the calculated start and end datetime values in UTC without timezone.
        """
        def convert_datetime_timezone(dt, tz):
            return dt and dt.replace(tzinfo=UTC).astimezone(tz)

        resource = next(iter(resource_ids), self.env.user.employee_id.resource_id)
        employee = resource.employee_id if resource_ids.filtered(lambda r: r.resource_type == 'user') else False
        user_tz = ZoneInfo(self.env.user.tz
                                or (employee and employee.tz)
                                or resource.tz
                                or self.env.context.get('tz')
                                or self.env.user.company_id.tz
                                or 'UTC')

        # start_datetime and end_datetime are from 00:00 to 23:59 in user timezone
        # Converted in UTC, it gives an offset for any other timezone, _convert_datetime_timezone removes the offset
        # If start_datetime and end_datetime are None, the resource should follow the company's working calendar and return the work intervals based on the time zone and the company's working calendar.
        intervals = []
        start = convert_datetime_timezone(start_datetime, UTC) if start_datetime else self._default_start_datetime().replace(tzinfo=UTC)
        end = convert_datetime_timezone(end_datetime, UTC) if end_datetime else self._default_end_datetime().replace(tzinfo=UTC)

        if not template_id:
            # Transform the current column's start/end_datetime to the user's timezone from UTC
            # Look at the work intervals to examine whether the current start/end_datetimes are inside working hours
            calendars = resource.calendar_id
            resources_per_tz = resource._get_resources_per_tz()
            work_interval = calendars._work_intervals_batch(start, end, resources_per_tz=resources_per_tz)[False]
            intervals = [(date_start, date_stop) for date_start, date_stop, attendance in work_interval]
            if not intervals and not self.env.context.get('planning_keep_default_datetime', False):
                # If we are outside working hours, we do not edit the start/end_datetime
                # Return the start/end times back at UTC and remove the tzinfo from the object
                return self._get_non_working_days_bounds(start, end, resource)

        # start_datetime and end_datetime are from 00:00 to 23:59 in user timezone
        # Converted in UTC, it gives an offset for any other timezone, _convert_datetime_timezone removes the offset
        start = convert_datetime_timezone(start_datetime, user_tz) if start_datetime else self._default_start_datetime().replace(tzinfo=user_tz)
        end = convert_datetime_timezone(end_datetime, user_tz) if end_datetime else self._default_end_datetime().replace(tzinfo=user_tz)

        # Get start and end in resource timezone so that it begins/ends at the same hour of the day as it would be in the user timezone
        # This is needed because _adjust_to_calendar takes start as datetime for the start of the day and end as end time for the end of the day
        # This can lead to different results depending on the timezone difference between the current user and the resource.
        # Example:
        # The user is in Europe/Brussels timezone (CET, UTC+1)
        # The resource is Asia/Krasnoyarsk timezone (IST, UTC+7)
        # The resource has two shifts during the day:
        #       - Morning shift: 8 to 12
        #       - Afternoon shift: 13 to 17
        # When the user selects a day to plan a shift for the resource, he expects to have the shift scheduled according to the resource's calendar given a search range between 00:00 and 23:59
        # The datetime received from the frontend is in the user's timezone meaning that the search interval will be between 23:00 and 22:59 in UTC
        # If the datetime is not adjusted to the resource's calendar beforehand, _adjust_to_calendar and _get_closest_work_time will shift the time to the resource's timezone.
        # The datetime given to _get_closest_work_time will be 6 AM once shifted in the resource's timezone. This will properly find the start of the morning shift at 8AM
        # For the afternoon shift, _get_closest_work_time will search the end of the shift that is close to 6AM the day after.
        # The closest shift found based on the end datetime will be the morning shift meaning that the work_interval_end will be the end of the morning shift the following day.
        # Determine the start and end dates from _work_intervals_batch and convert them to the resource's time zone.
        if resource and intervals:
            start = intervals[0][0].replace(tzinfo=ZoneInfo(resource.tz))
            end = intervals[-1][-1].replace(tzinfo=ZoneInfo(resource.tz))

        if not previous_template_id and not template_reset:
            start = start.astimezone(UTC).replace(tzinfo=None)
            end = end.astimezone(UTC).replace(tzinfo=None)

        if template_id and start_datetime:
            h = int(template_id.start_time)
            m = round(modf(template_id.start_time)[0] * 60.0)
            start = start_datetime.replace(tzinfo=UTC).astimezone(ZoneInfo(resource.tz) if resource else user_tz)
            start = start.replace(hour=int(h), minute=int(m))

            h = int(template_id.end_time)
            m = round(modf(template_id.end_time)[0] * 60.0)
            end = (start + relativedelta(days=(template_id.duration_days - 1), hour=0, minute=0, second=0))
            if template_id.duration_days > 1 and resource.calendar_id:
                end = resource.calendar_id.plan_days(template_id.duration_days, start.replace(hour=0, minute=0), compute_leaves=True) or end
            end = end.replace(hour=int(h), minute=int(m), second=0, microsecond=0)

        # Need to remove the tzinfo in start and end as without these it leads to a traceback
        # when the start time is empty
        start = start.astimezone(UTC).replace(tzinfo=None) if start.tzinfo else start
        end = end.astimezone(UTC).replace(tzinfo=None) if end.tzinfo else end
        return (start, end)

    @api.depends('template_id')
    def _compute_datetime(self):
        for slot in self.filtered(lambda s: s.template_id):
            slot.start_datetime, slot.end_datetime = self._calculate_start_end_dates(slot.start_datetime,
                                                                                     slot.end_datetime,
                                                                                     slot.resource_ids,
                                                                                     slot.template_id,
                                                                                     slot.previous_template_id,
                                                                                     slot.template_reset)

    @api.depends(lambda self: self._get_fields_breaking_publication())
    def _compute_publication_warning(self):
        for slot in self:
            slot.publication_warning = slot.employee_ids and slot.state == '2_published'

    def _company_working_hours(self, start, end):
        company = self.company_id or self.env.company
        work_interval = company.resource_calendar_id._work_intervals_batch(start, end)[False]
        intervals = [(date_start, date_stop) for date_start, date_stop, attendance in work_interval]

        if not intervals:
            return ()

        start_datetime, end_datetime = (start, end)
        if intervals and (end_datetime - start_datetime).days == 0:  # Then we want the first working day and keep the end hours of this day
            start_datetime = intervals[0][0]
            end_datetime = [stop for start, stop in intervals if stop.date() == start_datetime.date()][-1]
        elif intervals and (end_datetime - start_datetime).days > 0:
            start_datetime = intervals[0][0]
            end_datetime = intervals[-1][1]

        return (start_datetime.replace(tzinfo=ZoneInfo(company.tz)), end_datetime.replace(tzinfo=ZoneInfo(company.tz)))

    def _compute_allow_self_unassign(self):
        allow_self_unassign_planning = self.filtered(lambda p: p.company_id.planning_employee_unavailabilities == 'unassign')
        allow_self_unassign_planning.allow_self_unassign = True
        (self - allow_self_unassign_planning).allow_self_unassign = False

    @api.depends('self_unassign_days_before', 'start_datetime')
    def _compute_unassign_deadline(self):
        slots_with_date = self.filtered('start_datetime')
        (self - slots_with_date).unassign_deadline = False
        for slot in slots_with_date:
            slot.unassign_deadline = fields.Datetime.subtract(slot.start_datetime, days=slot.self_unassign_days_before)

    @api.depends('unassign_deadline')
    def _compute_is_unassign_deadline_passed(self):
        slots_with_date = self.filtered('unassign_deadline')
        (self - slots_with_date).is_unassign_deadline_passed = False
        for slot in slots_with_date:
            slot.is_unassign_deadline_passed = slot.unassign_deadline < fields.Datetime.now()

    # ----------------------------------------------------
    # ORM overrides
    # ----------------------------------------------------

    @api.model
    def _read_group_fields_nullify(self):
        return []

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
        res = super().formatted_read_group(domain, groupby, aggregates, having, offset, limit, order)
        for aggregate_nullify in self._read_group_fields_nullify():
            if aggregate_nullify not in aggregates:
                continue
            for row in res:
                if row[aggregate_nullify] == 0:
                    row[aggregate_nullify] = False
        return res

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        resources = self.env['resource.resource']
        if 'resource_ids' in fields and self.env.context.get('my_planning_action') and self.env.user.employee_id.resource_id:
            res.setdefault('resource_ids', []).append(Command.link(self.env.user.employee_id.resource_id.id))
        if res.get('resource_ids'):
            resource_ids = self.env['planning.slot']._convert_resource_ids_vals(res.get('resource_ids'))
            resources = self.env['resource.resource'].browse(resource_ids)
            res['resource_ids'] += [Command.link(r) for r in resources.get_materials_assigned_to_human_resources().ids]
        if resources:
            template_id, previous_template_id = [res.get(key) for key in ['template_id', 'previous_template_id']]
            template_id = template_id and self.env['planning.slot.template'].browse(template_id)
            previous_template_id = template_id and self.env['planning.slot.template'].browse(previous_template_id)
            res['start_datetime'], res['end_datetime'] = self._calculate_start_end_dates(res.get('start_datetime'),
                                                                                       res.get('end_datetime'),
                                                                                       resources,
                                                                                       template_id,
                                                                                       previous_template_id,
                                                                                       res.get('template_reset'))
        else:
            if 'start_datetime' in fields and not self.env.context.get('planning_keep_default_datetime', False):
                start_datetime = Datetime.to_datetime(res.get('start_datetime')) if res.get('start_datetime') else self._default_start_datetime()
                end_datetime = Datetime.to_datetime(res.get('end_datetime')) if res.get('end_datetime') else self._default_end_datetime()
                start = start_datetime.replace(tzinfo=UTC)
                end = end_datetime.replace(tzinfo=UTC) if end_datetime else self._default_end_datetime()
                opening_hours = self._company_working_hours(start, end)
                if opening_hours:
                    user_tz = ZoneInfo(self._get_tz())
                    res['start_datetime'] = opening_hours[0].replace(tzinfo=user_tz).astimezone(UTC).replace(tzinfo=None)
                    if 'end_datetime' in fields:
                        res['end_datetime'] = opening_hours[1].replace(tzinfo=user_tz).astimezone(UTC).replace(tzinfo=None)
                else:
                    res['start_datetime'], end_datetime = self._get_non_working_days_bounds(start_datetime, end_datetime)
                    if 'end_datetime' in fields:
                        res['end_datetime'] = end_datetime

        return res

    def _init_column_access_token(self):
        self.env.execute_query(SQL("""
            UPDATE %(table_name)s
            SET access_token = md5(md5(random()::varchar || id::varchar) || clock_timestamp()::varchar)::uuid::varchar
            WHERE access_token IS NULL
        """, table_name=SQL.identifier(self._table)))

    def _get_field_display_name(self, fname):
        return self._fields[fname].convert_to_display_name(self[fname], self)

    def _get_display_name(self, field_list=None):
        if field_list is None:
            field_list = self._display_name_fields()
        name_values = [
            self._get_field_display_name(fname)
            for fname in field_list
            if self[fname]
        ][:4]  # limit to 4 labels
        name = ' - '.join(name_values)

        # add unicode bubble to tell there is a note
        if self.name:
            name = f'{name} \U0001F4AC'
        if not (name or self.env.context.get('hide_planned_dates')):
            if self.start_datetime and self.end_datetime:
                dt_format = 'short'
                lang_code = get_lang(self.env).code
                start_datetime_str = format_datetime(self.env, self.start_datetime, dt_format=dt_format, lang_code=lang_code)
                if self.start_datetime.date() == self.end_datetime.date():
                    end_datetime_str = format_time(self.env, self.end_datetime, time_format='short', lang_code=lang_code)
                else:
                    end_datetime_str = format_datetime(self.env, self.end_datetime, dt_format=dt_format, lang_code=lang_code)
                name = f'{start_datetime_str} - {end_datetime_str}'
            elif not (self.start_datetime or self.end_datetime):
                name = self.env._('Unscheduled Shift')
        return name

    @api.depends(lambda self: self._display_name_fields())
    @api.depends_context('group_by')
    def _compute_display_name(self):
        group_by = self.env.context.get('group_by', [])
        field_list = [fname for fname in self._display_name_fields() if fname not in group_by]

        # Sudo as a planning manager is not able to read private project if he is not project manager.
        self = self.sudo()  # noqa: PLW0642
        for slot in self.with_context(hide_partner_ref=True):
            name = slot._get_display_name(field_list)
            slot.display_name = name or ''

    @api.model_create_multi
    def create(self, vals_list):
        Resource = self.env['resource.resource']
        Slot = self.env['planning.slot']
        for vals in vals_list:
            if vals.get('resource_ids'):
                resource_ids = Slot._convert_resource_ids_vals(vals.get('resource_ids'))
                resources = Resource.browse(resource_ids)
                if not vals.get('company_id') and len(resources.company_id) == 1:
                    vals['company_id'] = resources.company_id.id
                if all(resource.resource_type == 'material' for resource in resources):
                    vals['state'] = '2_published'
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
            if vals.get('start_datetime') is False and vals.get('end_datetime') is False:
                vals['repeat'] = False  # If the slot is unscheduled, then it cannot be recurrent
        if self.env.context.get("multi_create"):
            user_tz = ZoneInfo(self._get_tz())
            min_datetime = fields.Datetime.from_string(vals_list[0]['start_datetime']).astimezone(user_tz)
            max_datetime = fields.Datetime.from_string(vals_list[-1]['end_datetime']).astimezone(user_tz)
            resource_ids = {
                resource_id
                for vals in vals_list
                for resource_id in Slot._convert_resource_ids_vals(vals.get('resource_ids'))
            }
            schedule, _ = Resource.browse(resource_ids)._get_valid_work_intervals(min_datetime, max_datetime)
            vals_list_updated = []
            for vals in vals_list:
                if vals.get('resource_ids'):
                    valid_resource_ids = []
                    resource_ids = Slot._convert_resource_ids_vals(vals.get('resource_ids'))
                    shift_interval = Intervals([(
                        fields.Datetime.from_string(vals.get('start_datetime')).astimezone(user_tz),
                        fields.Datetime.from_string(vals.get('end_datetime')).astimezone(user_tz),
                        self.env['resource.calendar.attendance'],
                    )])
                    for resource_id in resource_ids:
                        if shift_interval & schedule[resource_id]:
                            valid_resource_ids.append(resource_id)
                    if valid_resource_ids:
                        vals['resource_ids'] = valid_resource_ids
                        vals_list_updated.append(vals)
                else:
                    vals_list_updated.append(vals)
            vals_list = vals_list_updated
        return super().create(vals_list)

    @api.model
    def create_batch_from_calendar(self, vals_list):
        if not len(vals_list):
            return
        template_id = self.env['planning.slot.template'].browse(vals_list[0]['template_id'])

        min_datetime = datetime.strptime(vals_list[0]['start_datetime'], '%Y-%m-%d %H:%M:%S')
        max_datetime = datetime.strptime(vals_list[-1]['end_datetime'], '%Y-%m-%d %H:%M:%S')
        if template_id.duration_days > 1:
            max_datetime = max_datetime + relativedelta(months=2)

        Slot = self.env['planning.slot']
        resource_ids = {
            resource_id
            for vals in vals_list
            for resource_id in Slot._convert_resource_ids_vals(vals.get('resource_ids', []))
        }
        resources = self.env['resource.resource'].browse(resource_ids)

        user_tz = ZoneInfo(self._get_tz())
        schedule, _ = resources._get_valid_work_intervals(min_datetime.astimezone(user_tz),
                                                          max_datetime.astimezone(user_tz))
        vals_list_updated_slots = []
        default_intervals = Intervals([(min_datetime.astimezone(user_tz), max_datetime.astimezone(user_tz), self.env['planning.slot'])])
        if template_id.duration_days > 1:
            for vals in vals_list:
                if resource_ids := Slot._convert_resource_ids_vals(vals.get('resource_ids', [])):
                    end_datetime = datetime.strptime(vals['end_datetime'], '%Y-%m-%d %H:%M:%S')
                    current_end_datetime = end_datetime - relativedelta(days=template_id.duration_days)
                    current_start_datetime = datetime.strptime(vals['start_datetime'], '%Y-%m-%d %H:%M:%S') - relativedelta(days=1)
                    working_days_to_assign = template_id.duration_days
                    resources_intervals = None
                    for resource_id in resource_ids:
                        if resources_intervals is None:
                            resources_intervals = schedule[resource_id] & default_intervals
                        else:
                            resources_intervals |= schedule[resource_id] & default_intervals
                    while working_days_to_assign > 0 and current_end_datetime < max_datetime:

                        current_start_datetime += relativedelta(days=1)
                        current_end_datetime += relativedelta(days=1)
                        shift_interval = Intervals([(
                            current_start_datetime.astimezone(user_tz),
                            current_end_datetime.astimezone(user_tz),
                            self.env['resource.calendar.attendance'],
                        )])
                        if shift_interval & resources_intervals:
                            working_days_to_assign -= 1

                    vals['end_datetime'] = current_end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    vals_list_updated_slots.append(vals)
                else:
                    vals_list_updated_slots = vals_list
                    break
        else:
            for vals in vals_list:
                if resource_ids := Slot._convert_resource_ids_vals(vals.get('resource_ids', [])):
                    resources_intervals = None
                    for resource_id in resource_ids:
                        if resources_intervals is None:
                            resources_intervals = schedule[resource_id] & default_intervals
                        else:
                            resources_intervals |= schedule[resource_id] & default_intervals
                    shift_interval = Intervals([(
                        datetime.strptime(vals['start_datetime'], '%Y-%m-%d %H:%M:%S').astimezone(user_tz),
                        datetime.strptime(vals['end_datetime'], '%Y-%m-%d %H:%M:%S').astimezone(user_tz),
                        self.env['resource.calendar.attendance'],
                    )])
                    if shift_interval & resources_intervals:
                        vals_list_updated_slots.append(vals)
                else:
                    vals_list_updated_slots.append(vals)

        return self.with_context(add_materials_assigned_to_employees=True).create(vals_list_updated_slots)

    def write(self, vals):
        values = vals
        shifts_to_update = self
        for slot in shifts_to_update:
            new_resources = None
            if 'resource_ids' in vals and (slot.state == '2_published' or slot.request_to_switch):
                new_resource_ids = slot._convert_resource_ids_vals(vals.get('resource_ids', []))
                new_resources = self.env['resource.resource'].browse(new_resource_ids)
                if (
                    slot.state == '2_published'
                    and (human_resources := new_resources.filtered(lambda r: r.resource_type == 'user'))
                    and any(r.resource_type == 'user' and r not in human_resources for r in slot.resource_ids)
                ):
                    # if the resource_ids is changed while the shift has already been published and the resource is human, that means that the shift has been re-assigned
                    # and thus we should send the email about the shift re-assignment
                    slot._send_shift_assigned(human_resources)
            if slot.request_to_switch and (
                ('start_datetime' in values and slot.start_datetime != values['start_datetime'])
                or ('end_datetime' in values and slot.end_datetime != values['end_datetime'])
            ):
                values['switch_employee_ids'] = False

        # If the slot is unscheduled, then we remove its recurrency
        if values.get('start_datetime') is False and values.get('end_datetime') is False:
            values['repeat'] = False
            values['recurrency_id'] = False

        recurrence_update = values.pop('recurrence_update', 'this')
        # `self` has no recurrence when we just set it, in which case there's no other slot to update
        if shifts_to_update.recurrency_id and recurrence_update != 'this':
            # Updating "all" or "subsequent" slots is only possible on one record at a time
            shifts_to_update.ensure_one()
            datetime_keys = values.keys() & {'start_datetime', 'end_datetime'}
            if recurrence_update == 'subsequent':
                subsequent_slots = self.search([
                    '&',
                        ('recurrency_id', '=', shifts_to_update.recurrency_id.id),
                        ('start_datetime', '>', shifts_to_update.start_datetime),
                ])
                if datetime_keys:
                    values["repeat_type"] = self.repeat_type
                    values["repeat_number"] = 1 + len(subsequent_slots)
                    (shifts_to_update.recurrency_id.slot_ids - subsequent_slots - shifts_to_update).recurrency_id = False
                    subsequent_slots.unlink()
                else:
                    shifts_to_update |= subsequent_slots
            else:
                all_slots = shifts_to_update.recurrency_id.slot_ids.sorted('start_datetime')
                if datetime_keys:
                    first_slot = all_slots[0]
                    values.update({
                        datetime_key: fields.Datetime.from_string(values[datetime_key]) - (self[datetime_key] - first_slot[datetime_key])
                        for datetime_key in datetime_keys
                    })
                    values["repeat_type"] = first_slot.repeat_type    # this is to ensure that the subsequent slots are recreated
                    (all_slots - first_slot).unlink()
                    shifts_to_update = first_slot
                else:
                    shifts_to_update |= all_slots

        result = super(PlanningSlot, shifts_to_update).write(values)

        if 'resource_ids' in values:
            for slot in shifts_to_update:
                if departed := slot.switch_employee_ids - slot.employee_ids:
                    slot.switch_employee_ids = [Command.unlink(employee.id) for employee in departed]

        # recurrence
        if any(key in ('repeat', 'repeat_unit', 'repeat_type', 'repeat_until', 'repeat_interval', 'repeat_number') for key in values):
            # User is trying to change this record's recurrence so we delete future slots belonging to recurrence A
            # and we create recurrence B from now on w/ the new parameters
            for slot in shifts_to_update:
                recurrence = slot.recurrency_id
                if recurrence and values.get('repeat') is None:
                    repeat_type = values.get('repeat_type') or recurrence.repeat_type
                    repeat_until = values.get('repeat_until') or recurrence.repeat_until
                    repeat_number = values.get('repeat_number', 0) or slot.repeat_number
                    if repeat_type == 'until':
                        repeat_until = datetime.combine(fields.Date.to_date(repeat_until), datetime.max.time())
                        repeat_until = repeat_until.replace(tzinfo=ZoneInfo(slot.company_id.tz or 'UTC')).astimezone(UTC).replace(tzinfo=None)
                    recurrency_values = {
                        'repeat_interval': values.get('repeat_interval') or recurrence.repeat_interval,
                        'repeat_unit': values.get('repeat_unit') or recurrence.repeat_unit,
                        'repeat_until': repeat_until if repeat_type == 'until' else False,
                        'repeat_number': repeat_number,
                        'repeat_type': repeat_type,
                        'company_id': slot.company_id.id,
                    }
                    recurrence.write(recurrency_values)
                    if slot.repeat_type == 'x_times':
                        final_slot = min(repeat_number, len(recurrence.slot_ids))
                        recurrency_values['repeat_until'] = recurrence.slot_ids.sorted('end_datetime')[final_slot - 1].end_datetime
                    end_datetime = slot.end_datetime if values.get('repeat_unit') else recurrency_values.get('repeat_until')
                    recurrence._delete_slot(end_datetime)
                    recurrence._repeat_slot()
        return result

    def assign_slot(self, vals):
        assert vals.get('start_datetime')
        assert self.env.context.get('default_end_datetime')
        assert all(not (slot.start_datetime or slot.end_datetime) for slot in self)

        PlanningShift = self.env['planning.slot']
        slots_to_schedule_vals = {}
        slots_to_create_vals = []
        slot_vals_list_per_resource = defaultdict(list)

        for slot in self:
            # Update the resource_ids of the slot with the following logic:
            # Let's say the shift to be scheduled is assigned to resources A and B
            # If dragged and dropped into "Open Shifts" -> leave it assigned to A and B
            # If dragged and dropped into resource A -> leave it assigned to A and B
            # If dragged and dropped into resource C -> unassign A and B, and assign to C
            if 'resource_ids' in vals:
                new_resource_ids = PlanningShift._convert_resource_ids_vals(vals['resource_ids'])
                if self.env.context.get('my_planning_action') and not new_resource_ids:
                    vals['resource_ids'] = (slot.resource_ids | slot.env.user.employee_id.resource_id).ids
                elif (not new_resource_ids and slot.resource_ids) or (set(slot.resource_ids.ids) & set(new_resource_ids)):
                    vals['resource_ids'] = slot.resource_ids.ids

            # This method will generate the planning slots for the given resources and following the numbers of hours still to plan for the given slot.
            new_vals, tmp_slots_to_plan, resources, schedule_type = slot._get_slots_to_plan(vals, slot_vals_list_per_resource)
            if new_vals:
                slots_to_schedule_vals[slot] = new_vals[0]
                slots_to_create_vals += tmp_slots_to_plan
                for resource in resources:
                    slot_vals_list_per_resource[resource] += new_vals + tmp_slots_to_plan

        undo_vals = {}
        for slot, new_vals in slots_to_schedule_vals.items():
            undo_vals[slot.id] = {
                f: slot[f].ids if slot._fields[f].type == 'many2many'
                else slot[f].id if slot._fields[f].type == 'many2one'
                else slot[f]
                for f in new_vals
            }

        slots_written = PlanningShift
        for slot, new_vals in slots_to_schedule_vals.items():
            slot.with_context(from_slot_scheduling=True).write(new_vals)
            slots_written += slot

        slots_created = PlanningShift
        if slots_to_create_vals:
            slots_created = self.with_context(from_slot_scheduling=True).create(slots_to_create_vals)

        return {
            'slots_assigned_ids': (slots_written | slots_created).ids,
            'schedule_type': schedule_type if len(self) == 1 else False,
            'undo_data': {
                'slots_created_ids': slots_created.ids,
                'undo_vals': undo_vals,
            },
        }

    def undo_assign_slot(self, slots_created_ids, undo_vals):
        self.env['planning.slot'].browse(slots_created_ids).unlink()
        for slot in self:
            if original_data := undo_vals.get(str(slot.id), {}):
                for field in original_data:
                    if slot._fields[field].type == 'many2many':
                        original_data[field] = [Command.set(original_data[field])]
                slot.write(original_data)

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        active_resources_per_slot = {}
        planning_split_tool = self.env.context.get('planning_split_tool')
        check_resource_active = not ((default and 'resource_ids' in default) or planning_split_tool)
        if check_resource_active:
            active_resources_per_slot = {
                slot: slot.resource_ids.filtered('active')
                for slot in self.with_context(active_test=False)
            }
        for planning, vals in zip(self, vals_list):
            if planning_split_tool:
                vals['state'] = planning.state
            if check_resource_active and (resources := active_resources_per_slot.get(planning)):
                vals['resource_ids'] = resources.ids
        return vals_list

    def copy(self, default=None):
        result = super().copy(default=default)
        # force recompute of stored computed fields depending on start_datetime and resource_ids
        if default and {'start_datetime', 'resource_ids'} & default.keys():
            result._compute_allocated_hours()
        return result

    def split_pill(self, values):
        """
            Split the slot in two parts
            1. Copy the pill and modify the start time (second pill)
            2. Modify the original pill and modify the end time (first pill)

            values expected:
            :start_datetime: the start datetime of the second pill
            :end_datetime: the end datetime of the first pill
        """

        # Important Note: When you change this method logic, change it also in _split_fake_pill
        # in the same file, they should be identical
        result = self.copy({'start_datetime': values.get('start_datetime')})
        self.write({'end_datetime': values.get('end_datetime')})
        return result.id

    def _get_slot_to_allocate_value(self):
        self.ensure_one()
        allocated_hours = self.allocated_hours
        # If the slot has no allocated hours, we fall back on some default values based on the scale of the gantt/calendar view
        if not allocated_hours and 'scale' in self.env.context:
            if self.env.context['scale'] == 'day':
                allocated_hours = 1
            else:
                allocated_hours = 8
        return allocated_hours

    def _get_unplanned_slot_values(self):
        self.ensure_one()
        return {
            'start_datetime': False,
            'end_datetime': False,
            'role_id': self.role_id.id,
            'allocated_hours': 0,
            'allocated_percentage': 100,
            'company_id': self.company_id.id,
            'resource_ids': self.resource_ids.ids,
            'name': self.name,
        }

    def _get_slots_to_plan(self, vals, slot_vals_list_per_resource):
        """
            Returns the vals which will be used to update self, a vals_list of the slots
            to create for the related slots with the resources.

            :param vals: the vals passed to the write orm method.
            :param slot_vals_list_per_resource: a dict of vals list of slots to be created, sorted per resource
                This dict is used to be aware of the slots which will be created and are not in the database yet.
        """
        # Gets work interval in order to know if the employee can work or not
        # Gets its slots which are partially allocated (allocated_percentage < 100) in order to avoid planning slots in conflict.
        self.ensure_one()
        to_allocate = self._get_slot_to_allocate_value()
        if to_allocate < 0.0:
            return [], [], None, False
        work_intervals, unforecastable_intervals, resources, partial_interval_slots = self.sudo().with_context(
            default_end_datetime=self.env.context.get('default_end_datetime')
        )._get_resource_work_info(vals, slot_vals_list_per_resource)
        following_slots_vals_list = []
        if work_intervals:
            following_slots_vals_list = self._get_slots_values(
                vals, work_intervals, partial_interval_slots, unforecastable_intervals, to_allocate=to_allocate, resources=resources
            )
            if following_slots_vals_list:
                # Trailing unplanned slot (start_datetime=False) means hours remain after exhausting work intervals
                schedule_type = 'partial' if not following_slots_vals_list[-1]['start_datetime'] else 'full'
                # In order to have slots on multiple days, the slots filling the resources's work intervals must be
                # merged. The consequence is that it will be forecasted slots (regarding `allocation_type`) rather than short planning slots
                following_slots_vals_list = self._merge_slots_values(following_slots_vals_list, unforecastable_intervals)
                return following_slots_vals_list[:1], following_slots_vals_list[1:], resources, schedule_type
        return [], [], resources, False

    def _get_slots_values(self, vals, work_intervals, partial_interval_slots, unforecastable_intervals, to_allocate, resources):
        """
            This method returns the generated slots values related to self for the given resources.

            Params :
                - `vals` : the vals sent in the write/reschedule call;
                - `work_intervals`: Intervals during which resources works/is available
                - `partial_interval_slots`: Intervals during which the resources have slots partially planned (`allocated_percentage` < 100)
                - `unforecastable_intervals`: Intervals during which the resources cannot have a slot with `allocation_type` == 'forecast'
                                          (see _merge_slots_values for further explanation)
                - `to_allocate`: The number of hours there is still to allocate for this shift (self)
                - `resources`: The recordset of the resources for whom the information are given and who will be assigned to the slots
                                 If None, the information is the one of the company.

            Algorithm :
                - General principle :
                    - For each work interval, a planning slot is assigned to the resources, until there are no more hours to allocate
                - Details :
                    - If the interval is in conflict with a partial_interval_slots, the algorithm must find each time the sum of allocated_percentage increases/decreases:
                        - The algorithm retrieve this information by building a dict where the keys are the datetime where the allocated_percentage changes :
                            - The algorithm adds start and end of the interval in the dict with 0 as value to increase/decrease
                            - For each slot conflicting with the work_interval:
                                - allocated_percentage is added with start_datetime as a key,
                                - allocated_percentage is substracted with end_datetime as a key
                            - For each datetime where the allocated_percentage changes:
                                - if there are no allocated percentage change (sum = 0) in the next allocated percentage change:
                                    - It will create a merged slot and not divide it in small parts
                                - the allocable percentage (default=100) is decreased by the value in the dict for the previous datetime (which will be the start datetime of the slot)
                                - if there are still time to allocate
                                    - Otherwise, it continues with the next datetime with allocated percentage change.
                                - if the datetimes are contained in the interval
                                    - Otherwise, it continues with the next datetime with allocated percentage change.
                                - The slot is build with the previous datetime with allocated percentage change and the actual datetime.
                    - Otherwise,
                        - Take the start of the interval as the start_datetime of the slot
                        - Take the min value between the end of the interval and the sum of the interval start and to_allocate hours.
                - Generate an unplanned slot if there are still hours to allocate.

            Returns :
                - A vals_list with slots to create :
                    NB : The first item of the list will be used to update the current slot.
        """
        self.ensure_one()
        following_slots_vals_list = []
        for interval in work_intervals:
            if float_utils.float_compare(to_allocate, 0.0, precision_digits=2) < 1:
                break
            start_interval = interval[0].astimezone(UTC).replace(tzinfo=None)
            end_interval = interval[1].astimezone(UTC).replace(tzinfo=None)
            if partial_interval_slots[interval]:
                # here we'll create slots with partially allocated hours - which is not trivial btw - read above the full explanation
                # 1. Create a dict with a datetime as `key`, which represent the total *increment* of allocated time, starting from time: `key`
                #    So for each slot, the increment is increased with allocated percentage at start datetime and decrease it at end datetime
                # 2. Create a list with all the start and end dates (allocated_dict keys), which will be sorted in order to have all the intervals.
                # 3. Allocable percentage are tracked by decreasing previous allocable percentage with the *increment* of allocated time.
                allocated_dict = defaultdict(float)
                allocated_dict.update({
                    start_interval: 0,
                    end_interval: 0,
                })
                for slot in partial_interval_slots[interval]:
                    allocated_dict[slot['start_datetime']] += float_utils.float_round(slot['allocated_percentage'], precision_digits=1)
                    allocated_dict[slot['end_datetime']] += float_utils.float_round(-slot['allocated_percentage'], precision_digits=1)
                datetime_list = list(allocated_dict.keys())
                datetime_list.sort()
                allocable = 100.0
                for i in range(1, len(datetime_list)):
                    start_dt = datetime_list[i - 1]
                    end_dt = datetime_list[i]
                    if i != len(datetime_list) - 1 and float_utils.float_is_zero(allocated_dict[datetime_list[i]], precision_digits=2):
                        # there is no increment so we will build a single slot with the same allocated_percentage
                        datetime_list[i] = datetime_list[i - 1]
                        continue
                    allocable -= float_utils.float_round(allocated_dict[datetime_list[i - 1]], precision_digits=1)
                    if float_utils.float_compare(allocable, 0.0, precision_digits=2) < 1:
                        unforecastable_intervals |= Intervals([(
                            start_dt.replace(tzinfo=UTC),
                            end_dt.replace(tzinfo=UTC),
                            self.env['resource.calendar.leaves'])])
                        continue
                    if end_dt <= start_interval or start_dt >= end_interval:
                        continue
                    start_dt = max(start_dt, start_interval)
                    end_dt = min(end_dt, end_interval)
                    end_dt = min(end_dt, start_dt + timedelta(hours=to_allocate * (100.0 / allocable)))
                    to_allocate -= ((end_dt - start_dt).total_seconds() / 3600.0) * (allocable / 100.0)
                    self._add_slot_to_list(vals, start_dt, end_dt, resources, following_slots_vals_list, allocable=allocable)
            else:
                end_dt = min(start_interval + timedelta(hours=to_allocate), end_interval)
                to_allocate -= (end_dt - start_interval).total_seconds() / 3600.0
                self._add_slot_to_list(vals, start_interval, end_dt, resources, following_slots_vals_list)

        if float_utils.float_compare(to_allocate, 0.0, precision_digits=2) == 1 and following_slots_vals_list and self.allocated_hours:
            planning_slot_values = self._get_unplanned_slot_values()
            planning_slot_values.update(allocated_hours=to_allocate)
            following_slots_vals_list.append(planning_slot_values)

        return following_slots_vals_list

    def _add_slot_to_list(self, vals, start_datetime, end_datetime, resources, following_slots_vals_list, allocable=100.0):
        if end_datetime <= start_datetime:
            return
        # In a week and month scale, if we schedule a slot with no allocated hours, we don't create slots if the start and end datetime are not on the same day as the targeted one.
        tz = self._get_tz()
        end_datetime_from_vals = fields.Datetime.from_string(vals.get('end_datetime'))
        if (
            not self.allocated_hours
            and self.env.context.get('scale') in ['week', 'month']
            and end_datetime_from_vals
            and (
                end_datetime_from_vals.date() != start_datetime.astimezone(ZoneInfo(tz)).date()
                or end_datetime_from_vals.date() != end_datetime.astimezone(ZoneInfo(tz)).date()
            )
        ):
            return
        allocated_hours = ((end_datetime - start_datetime).total_seconds() / 3600.0) * (allocable / 100.0)
        following_slots_vals_list.append({
            **self._get_unplanned_slot_values(),
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'allocated_percentage': allocable,
            'allocated_hours': allocated_hours,
            'resource_ids': resources.ids,
        })

    def _get_resource_work_info(self, vals, slot_vals_list_per_resource):
        """
            This method returns the resources work intervals and a dict representing
            the work_intervals which has conflicting partial slots (slot with allocated percentage < 100.0).

            It retrieves the work intervals and removes the intervals where a complete
            slot exists (allocated_percentage == 100.0).
            It takes into account the slots already added to the vals list.

            :param vals: the vals dict passed to the write method
            :param slot_vals_list_per_resource: a dict with the vals list that will be passed to the create method - sorted per key:resource_ids
        """
        self.ensure_one()
        assert self.env.context.get('default_end_datetime')
        if isinstance(vals['start_datetime'], str):
            start_dt = datetime.strptime(vals['start_datetime'], DEFAULT_SERVER_DATETIME_FORMAT).replace(tzinfo=UTC)
        else:
            start_dt = vals['start_datetime'].replace(tzinfo=UTC)
        end_dt = datetime.strptime(self.env.context['default_end_datetime'], DEFAULT_SERVER_DATETIME_FORMAT).replace(tzinfo=UTC)

        # retrieve the resources and their calendar validity intervals
        resources = self.resource_ids
        if 'resource_ids' in vals:
            resources = self.env['resource.resource'].browse(vals.get('resource_ids'))

        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources

        common_attendance_intervals = None
        total_unavailability_intervals = Intervals()
        default_calendar = self.company_id.resource_calendar_id or self.env.company.resource_calendar_id  # If there are no resources, fallback on the current slot/current company 's calendar
        resource_work_intervals, calendar_work_intervals = regular_resources._get_valid_work_intervals(start_dt, end_dt, calendars=[default_calendar], compute_leaves=False)

        if flexible_resources:
            flex_work_intervals, flex_hours_per_day, _dummy = flexible_resources._get_flexible_resource_valid_work_intervals(start_dt, end_dt)
            locale = babel_locale_parse(get_lang(self.env).code)
            for resource in flexible_resources:
                raw_intervals = flex_work_intervals.get(resource.id, Intervals())
                if resource._is_fully_flexible():
                    resource_work_intervals[resource.id] = raw_intervals
                    continue
                # trim each interval to respect hours_per_day and hours_per_week
                trimmed = []
                hours_per_day_map = flex_hours_per_day.get(resource.id, {})
                weekly_remaining = {}
                tz = ZoneInfo(resource.tz or self.env.user.tz)
                for interval_start, interval_end, meta in raw_intervals:
                    day = interval_start.astimezone(tz).date()
                    if resource.hours_per_day:
                        max_day = hours_per_day_map.get(day, 0.0)
                        if not max_day:
                            continue
                        interval_end = min(interval_end, interval_start + timedelta(hours=max_day))
                    if resource.hours_per_week:
                        week = weeknumber(locale, day)
                        if week not in weekly_remaining:
                            weekly_remaining[week] = resource.hours_per_week
                        rem = weekly_remaining[week]
                        if rem <= 0:
                            continue
                        interval_end = min(interval_end, interval_start + timedelta(hours=rem))
                        weekly_remaining[week] = max(0.0, rem - (interval_end - interval_start).total_seconds() / 3600)
                    trimmed.append((interval_start, interval_end, meta))
                resource_work_intervals[resource.id] = Intervals(trimmed)

        if resources:
            for resource_id, work_intervals in resource_work_intervals.items():
                # Intersect so we only schedule when all resources are working together
                if common_attendance_intervals is None:
                    common_attendance_intervals = work_intervals
                else:
                    common_attendance_intervals &= work_intervals
                resource = self.env['resource.resource'].browse(resource_id)
                if resource._is_flexible():
                    continue
                leaves = resource.calendar_id._leave_intervals_batch(start_dt, end_dt, resources_per_tz=resource._get_resources_per_tz())[resource_id]
                total_unavailability_intervals |= leaves & work_intervals
        else:
            common_attendance_intervals = calendar_work_intervals[default_calendar.id]
        # Fallback if no attendance intervals could be retrieved
        if common_attendance_intervals is None:
            common_attendance_intervals = Intervals()

        partial_slots = []
        partial_interval_slots = defaultdict(list)
        if resources:
            # gets slots which exists in the period [start_dt;end_dt]
            slots = self.search_read([
                ('resource_ids', 'in', resources.ids),
                ('start_datetime', '<', end_dt.replace(tzinfo=None)),
                ('end_datetime', '>', start_dt.replace(tzinfo=None)),
            ], ['start_datetime', 'end_datetime', 'allocated_percentage'])
            for resource in resources:
                # add the vals list of the resources (slots that will be created at the end of the write method)
                slots += slot_vals_list_per_resource[resource]
            planning_slots_intervals = Intervals()
            # generate partial intervals and complete intervals
            for slot in slots:
                if not slot['start_datetime']:
                    # this slot is a future unscheduled slots coming from the slot_vals_list_per_resource[resource]
                    continue
                if float_utils.float_compare(slot['allocated_percentage'], 100.0, precision_digits=0) < 0:
                    partial_slots.append(slot)
                else:
                    interval = Intervals([(
                        slot['start_datetime'].replace(tzinfo=UTC),
                        slot['end_datetime'].replace(tzinfo=UTC),
                        self.env['resource.calendar.leaves']
                    )])
                    planning_slots_intervals |= interval
            # adds the full planning_slots to the unavailibility intervals
            total_unavailability_intervals |= planning_slots_intervals
            work_intervals = common_attendance_intervals - total_unavailability_intervals
            if partial_slots:
                # for the partial slots, add it to a list with key = interval, value = list of slots which exists during the interval (at least during a while)
                for interval in work_intervals:
                    # for each interval, add partial slots that conflict
                    for slot in partial_slots:
                        if slot['start_datetime'].replace(tzinfo=UTC) < interval[1] and slot['end_datetime'].replace(tzinfo=UTC) > interval[0]:
                            partial_interval_slots[interval].append(slot)
        else:
            work_intervals = common_attendance_intervals - total_unavailability_intervals

        return work_intervals, total_unavailability_intervals, resources, partial_interval_slots

    # ----------------------------------------------------
    # Actions
    # ----------------------------------------------------

    def action_address_recurrency(self, recurrence_update):
        """ :param recurrence_update: the occurences to be targetted (this, subsequent, all)
        """
        if recurrence_update == 'this':
            return
        domain = Domain('id', 'not in', self.ids)
        if recurrence_update == 'all':
            domain &= Domain('recurrency_id', 'in', self.recurrency_id.ids)
        elif recurrence_update == 'subsequent':
            start_date_per_recurrency_id = {}
            for shift in self:
                if shift.recurrency_id.id not in start_date_per_recurrency_id\
                    or shift.start_datetime < start_date_per_recurrency_id[shift.recurrency_id.id]:
                    start_date_per_recurrency_id[shift.recurrency_id.id] = shift.start_datetime
            domain &= Domain.OR(
                Domain('recurrency_id', '=', recurrency_id) & Domain('start_datetime', '>', start_datetime)
                for recurrency_id, start_datetime in start_date_per_recurrency_id.items()
            )
        sibling_slots = self.env['planning.slot'].search(domain)
        self.recurrency_id.unlink()
        sibling_slots.unlink()

    def action_unlink(self):
        self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def action_see_overlaping_slots(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'planning.slot',
            'name': self.env._('Shifts in Conflict'),
            'views': [[False, "gantt"], [False, "list"], [False, "form"]],
            'context': {
                'initialDate': min(self.mapped('start_datetime')),
                'search_default_needs_attention': True,
                'search_default_resource_ids': self.resource_ids.ids
            }
        }

    def action_self_assign(self):
        """ Allow planning user to self assign open shift. """
        self.ensure_one()
        # user must at least 'read' the shift to self assign (Prevent any user in the system (portal, ...) to assign themselves)
        if not self.has_access('read'):
            raise AccessError(self.env._("You don't have the right to assign yourself to shifts."))
        if self.employee_ids and not self.request_to_switch:
            raise UserError(self.env._("You can not assign yourself to an already assigned shift."))
        if self.is_past:
            if self.request_to_switch:
                self.sudo().write({'switch_employee_ids': False})
            raise UserError(self.env._("You cannot assign yourself to a shift in the past."))
        if self.company_id in self.env.user.employee_ids.mapped('company_id'):
            resource = self.env.user.employee_ids.filtered(lambda e: e.company_id == self.company_id)[0].resource_id
        elif len(self.env.user.employee_ids) == 1:
            resource = self.env.user.employee_ids.resource_id
        else:
            raise UserError(self.env._("You cannot assign yourself to a shift belonging to another company."))
        requesters = self.sudo().switch_employee_ids.resource_id
        resources_to_switch = requesters.sorted(lambda r: len(r.role_ids & resource.role_ids), reverse=True)[:1]
        resources_to_switch |= resources_to_switch.get_materials_assigned_to_human_resources()
        assigned_materials = resource.get_materials_assigned_to_human_resources()
        resources = (self.resource_ids - resources_to_switch) | resource | assigned_materials
        return self.sudo().write({'resource_ids': resources})

    def action_self_unassign(self):
        """ Allow planning user to self unassign from a shift, if the feature is activated """
        self.ensure_one()
        # The following condition will check the read access on planning.slot, and that user must at least 'read' the
        # shift to self unassign. Prevent any user in the system (portal, ...) to unassign any shift.
        if not self.allow_self_unassign:
            raise UserError(self.env._("The company does not allow you to unassign yourself from shifts."))
        if self.is_unassign_deadline_passed:
            raise UserError(self.env._("The deadline for unassignment has passed."))
        resource_to_unassign = self.resource_ids.filtered(lambda r: r.resource_type == 'user' and r.user_id == self.env.user)
        if not resource_to_unassign:
            raise UserError(self.env._("You can not unassign another employee than yourself."))
        if self.is_past:
            raise UserError(self.env._("You cannot unassign yourself from a shift in the past."))
        assigned_materials = resource_to_unassign.get_materials_assigned_to_human_resources()
        return self.sudo().write({'resource_ids': [Command.unlink(r.id) for r in resource_to_unassign | assigned_materials]})

    def action_switch_shift(self):
        """ Allow planning user to make shift available for other people to assign themselves to. """
        self.ensure_one()
        # same as with self-assign, a user must be able to 'read' the shift in order to request a switch
        if not self.has_access('read'):
            raise AccessError(self.env._("You don't have the right to switch shifts."))
        current_resource = self.resource_ids.filtered(lambda r: r.resource_type == 'user' and r.user_id == self.env.user)
        if not current_resource:
            raise UserError(self.env._("You cannot request to switch a shift that is assigned to another user."))
        if self.is_past:
            raise UserError(self.env._("You cannot switch a shift that is in the past."))
        employees_to_switch = current_resource.sudo().employee_id
        return self.sudo().write({
            'switch_employee_ids': [Command.link(employee.id) for employee in employees_to_switch],
        })

    def action_cancel_switch(self):
        """ Allows the planning user to cancel the shift switch if they change their mind at a later date """
        self.ensure_one()
        # same as above, the user rights are checked in order for the operation to be completed
        if not self.has_access('read'):
            raise AccessError(self.env._("You don't have the right to cancel a request to switch."))
        current_resource = self.resource_ids.filtered(lambda r: r.resource_type == 'user' and r.user_id == self.env.user)
        if not current_resource:
            raise UserError(self.env._("You cannot cancel a request to switch made by another user."))
        if self.is_past:
            raise UserError(self.env._("You cannot cancel a request to switch that is in the past."))
        employees_to_cancel = current_resource.sudo().employee_id
        return self.sudo().write({
            'switch_employee_ids': [Command.unlink(employee.id) for employee in employees_to_cancel],
        })

    def action_plan_shift(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("planning.planning_action_schedule_by_resource")
        action.update({
            "display_name": self.env._("Plan Shift"),
            "context": {
                "filter_resource_ids": self.role_id.resource_ids.ids,
                "search_default_role_id": self.role_id.id,
                "default_role_id": self.role_id.id,
            },
        })
        return action

    def _get_needs_attention_domain(self):
        now = fields.Datetime.now()
        return Domain('overlap_slot_count', '>', 0) | (
            Domain('switch_employee_ids', '!=', False) & Domain('end_datetime', '>', now)
        )

    @api.model
    def get_needs_attention_slot_ids(self):
        return self.search(self._get_needs_attention_domain()).ids

    def _get_ics_file(self, calendar, employee_tz):
        def ics_datetime(idate):
            tz_info = employee_tz or self.env.user.tz or 'UTC'
            return idate and idate.astimezone(ZoneInfo(tz_info))

        for slot in self:
            event = calendar.add('vevent')
            if not slot.start_datetime or not slot.end_datetime:
                raise UserError(self.env._("First you have to specify the date of the invitation."))
            event.add('created').value = ics_datetime(fields.Datetime.now())
            event.add('dtstart').value = ics_datetime(slot.start_datetime)
            event.add('dtend').value = ics_datetime(slot.end_datetime)
            event.add('summary').value = slot.display_name
            ics_description_data = {
                'shift': slot._get_ics_description_data(),
                'is_google_url': False,
            }
            event.add('description').value = self.env['ir.qweb']._render('planning.planning_shift_ics_description', ics_description_data)
        return calendar

    def _get_ics_description_data(self):
        return {
            'name': self.name,
            'allocated_hours': self.allocated_hours,
            'allocated_percentage': self.allocated_percentage,
            'role': self.role_id.name,
        }

    def auto_plan_id(self):
        """ Used in the form view to auto plan a single shift.
        """
        self.ensure_one()
        if self.resource_ids:
            return self._get_notification_action("danger", self.env._("This shift is already assigned."))
        if not self.with_context(planning_slot_id=self.id, add_materials_assigned_to_employees=True).auto_plan_ids([('id', '=', self.id)])['open_shift_assigned']:
            return self._get_notification_action("danger", self.env._("There are no resources available for this open shift."))
        return None

    def _auto_plan_group_by(self):
        return ['start_datetime:day']

    def _auto_plan_order_by(self):
        return 'start_datetime:day'

    def _get_open_shifts_resources(self):
        # Get all resources that have the role set on those shifts as default role or in their roles.
        # open_shifts.role_id.ids wouldn't include False, yet we need this information
        open_shift_role_ids = [shift.role_id.id for shift in self]
        resources = self.env['resource.resource'].search(['|', ('default_role_id', 'in', open_shift_role_ids), ('role_ids', 'in', self.role_id.ids)])
        # And make two dictionnaries out of it (default roles and roles). We will prioritize default roles.
        resource_ids_per_role = defaultdict(list)
        resource_ids_per_default_role = defaultdict(list)
        for resource in resources:
            resource_ids_per_default_role[resource.default_role_id].append(resource.id)
            for role in resource.role_ids:
                if role != resource.default_role_id:
                    resource_ids_per_role[role].append(resource.id)

        roles_without_resource = self.role_id.filtered(lambda r: not r.resource_ids and r not in resource_ids_per_role)
        if roles_without_resource:
            resources = self.env['resource.resource'].search([('role_ids', '!=', False), ('resource_type', '=', 'user')])
            for role in roles_without_resource:
                resource_ids_available = resource_ids_per_role[role]
                for resource in resources:
                    if resource.id not in resource_ids_available:
                        resource_ids_available.append(resource.id)
        return resources, [resource_ids_per_default_role, resource_ids_per_role]

    def _get_resources_dict_values(self, resource_dict):
        self.ensure_one()
        resource_ids = resource_dict.get(self.role_id, [])
        shuffle(resource_ids)
        return resource_ids

    @api.model
    def auto_plan_ids(self, view_domain):
        # We need to make sure we have a specified either one shift in particular or a period to look into.
        assert self.env.context.get('planning_slot_id') or (
            self.env.context.get('default_start_datetime') and self.env.context.get('default_end_datetime')
        ), "`default_start_datetime` and `default_end_datetime` attributes should be in the context"

        auto_plan_data = self._prepare_auto_plan_data(view_domain)
        open_shifts = auto_plan_data['open_shifts']
        if not open_shifts:
            return {"open_shift_assigned": []}

        assigned_shifts = open_shifts.filtered(lambda shift: self._auto_plan_assign_resource(shift, auto_plan_data))
        return self._auto_plan_result(assigned_shifts, auto_plan_data)

    @api.model
    def _auto_plan_result(self, assigned_shifts, auto_plan_data):
        return {"open_shift_assigned": assigned_shifts.ids}

    @api.model
    def _auto_plan_get_requested_period(self):
        start = self.env.context.get('default_start_datetime')
        end = self.env.context.get('default_end_datetime')
        if not start or not end:
            return None
        return fields.Datetime.from_string(start), fields.Datetime.from_string(end)

    @api.model
    def _auto_plan_get_period_boundaries(self, open_shifts, groups):
        starts, ends = [], []
        if groups:
            starts.append(min(group.get('start_datetime:min') for group in groups).replace(tzinfo=UTC))
            ends.append(max(group.get('end_datetime:max') for group in groups).replace(tzinfo=UTC))

        requested_period = self._auto_plan_get_requested_period()
        if requested_period:
            period_start, period_end = requested_period
            starts.append(period_start.replace(tzinfo=UTC))
            ends.append(period_end.replace(tzinfo=UTC))

        user_tz = ZoneInfo(self.env.user.tz or 'UTC')
        min_start = min(starts).astimezone(user_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        max_end = max(ends).astimezone(user_tz).replace(hour=0, minute=0, second=0, microsecond=0) + relativedelta(days=1)
        return min_start.astimezone(UTC), max_end.astimezone(UTC)

    @api.model
    def _auto_plan_search_open_shifts(self, view_domain):
        groups = self.formatted_read_group(
            domain=Domain.AND([
                view_domain,
                [('resource_ids', '=', False), ('start_datetime', '!=', False), ('end_datetime', '!=', False)],
            ]),
            groupby=self._auto_plan_group_by(),
            aggregates=['id:recordset', 'start_datetime:min', 'end_datetime:max'],
            order=self._auto_plan_order_by(),
        )
        open_shifts = self.browse([
            shift_id
            for group in groups
            for shift_id in group.get('id:array_agg', [])
        ])
        return groups, open_shifts

    @api.model
    def _get_schedule_intervals_per_resource_id(self, resources, start, end):
        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources
        schedule_intervals_per_resource_id, _dummy = regular_resources._get_valid_work_intervals(start, end)

        # we assume that if the employee has currently a flexible contract, all other contracts are also flexible
        flexible_resource_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = \
            flexible_resources._get_flexible_resource_valid_work_intervals(start, end)
        schedule_intervals_per_resource_id.update(flexible_resource_work_intervals)

        return (
            flexible_resources,
            schedule_intervals_per_resource_id,
            flexible_resources_hours_per_day,
            flexible_resources_hours_per_week,
        )

    @api.model
    def _prepare_auto_plan_data(self, view_domain):
        groups, open_shifts = self._auto_plan_search_open_shifts(view_domain)
        if not open_shifts:
            return {'open_shifts': open_shifts}

        min_start, max_end = self._auto_plan_get_period_boundaries(open_shifts, groups)
        locale = babel_locale_parse(get_lang(self.env).code)

        resources, resources_dicts = open_shifts._get_open_shifts_resources()
        resources_and_materials = resources | resources.get_materials_assigned_to_human_resources()

        # Get the schedule of each resource in the period.
        user_tz = ZoneInfo(self.env.user.tz or 'UTC')
        min_start_user_tz, max_end_user_tz = min_start.astimezone(user_tz), max_end.astimezone(user_tz)
        flexible_resources, schedule_intervals_per_resource_id, flexible_resources_hours_per_day, flexible_resources_hours_per_week = self._get_schedule_intervals_per_resource_id(resources, min_start_user_tz, max_end_user_tz)

        # Now let's get the assigned shifts and count the worked hours per day for each resource
        same_days_shifts = self.search([
            ('resource_ids', 'in', resources_and_materials.ids),
            ('end_datetime', '>', min_start.replace(tzinfo=None)),
            ('start_datetime', '<', max_end.replace(tzinfo=None)),
        ])
        remaining_hours_per_day = deepcopy(flexible_resources_hours_per_day)
        remaining_hours_per_week = deepcopy(flexible_resources_hours_per_week)
        timeline_and_worked_hours_per_resource_id = self._shift_records_to_timeline_per_resource_id(same_days_shifts, flexible_resources, min_start_user_tz, max_end_user_tz, remaining_hours_per_day, remaining_hours_per_week, locale)

        # Create an "empty timeline" with midnight for each day in the period
        delta_days = (max_end - min_start).days
        empty_timeline = [
            ((min_start + relativedelta(days=i + 1)).replace(tzinfo=None), 0)
            for i in range(delta_days)
        ]

        return {
            'open_shifts': open_shifts,
            'same_days_shifts': same_days_shifts,
            'resources': resources,
            'resources_dicts': resources_dicts,
            'resources_and_materials': resources_and_materials,
            'schedule_intervals_per_resource_id': schedule_intervals_per_resource_id,
            'flexible_resources_hours_per_day': flexible_resources_hours_per_day,
            'flexible_resources_hours_per_week': flexible_resources_hours_per_week,
            'remaining_hours_per_day': remaining_hours_per_day,
            'remaining_hours_per_week': remaining_hours_per_week,
            'timeline_and_worked_hours_per_resource_id': timeline_and_worked_hours_per_resource_id,
            'empty_timeline': empty_timeline,
            'locale': locale,
            'user_tz': user_tz,
            'requested_period': self._auto_plan_get_requested_period(),
        }

    def _auto_plan_assign_resource(self, shift, auto_plan_data):
        """ Try to find and assign a fitting resource for `shift` among the candidates prepared in `auto_plan_data`.
            :return: True if a resource was assigned to the shift, False otherwise.
        """
        resources_dicts = auto_plan_data['resources_dicts']
        schedule_intervals_per_resource_id = auto_plan_data['schedule_intervals_per_resource_id']
        timeline_and_worked_hours_per_resource_id = auto_plan_data['timeline_and_worked_hours_per_resource_id']
        empty_timeline = auto_plan_data['empty_timeline']

        shift_intervals = Intervals([(
            shift.start_datetime.replace(tzinfo=UTC),
            shift.end_datetime.replace(tzinfo=UTC),
            self.env['planning.slot'],
        )])
        for resources_dict in resources_dicts:
            resource_ids = shift._get_resources_dict_values(resources_dict)
            for resource in self.env['resource.resource'].browse(resource_ids):
                split_shift_intervals = shift_intervals & schedule_intervals_per_resource_id[resource.id]
                # If the shift is out of resource's schedule, skip it.
                if not split_shift_intervals:
                    continue
                is_flex_resource = resource._is_flexible()
                if is_flex_resource:
                    rate, is_overloaded = self._auto_plan_get_flexible_resource_load(resource, shift, split_shift_intervals, auto_plan_data)
                    if is_overloaded:
                        continue
                else:
                    rate = shift.allocated_hours * 3600 / round(
                        sum(
                            (end - start).total_seconds()
                            for start, end, rec in split_shift_intervals
                        )
                    )
                # Try to add the shift to the timeline.
                timeline = self._get_new_timeline_if_fits_in(
                    split_shift_intervals,
                    rate,
                    resource.calendar_id.hours_per_day if resource.calendar_id else resource.company_id.resource_calendar_id.hours_per_day,
                    timeline_and_worked_hours_per_resource_id[resource.id].copy(),
                    empty_timeline,
                )
                # If we got a timeline, it means the shift fits for the resource (i.e., no overload, no "occupation rate" > 100%).
                # If it fits, assign the shift to the resource and update the timeline.
                # If a timeline is found, the resource can work the allocated_hours set on the shift.
                # so the allocated_percentage is recomputed based on the working calendar of the
                # resource and the allocated_hours set on the shift.
                if timeline:
                    original_allocated_hours = shift.allocated_hours
                    shift.resource_ids |= resource
                    shift._compute_allocated_hours()
                    timeline_and_worked_hours_per_resource_id[resource.id] = timeline
                    self._auto_plan_register_assignment(shift, resource, original_allocated_hours, auto_plan_data)
                    return True

        return False

    def _auto_plan_get_flexible_resource_load(self, resource, shift, split_shift_intervals, auto_plan_data):
        locale = auto_plan_data['locale']
        remaining_hours_per_day = auto_plan_data['remaining_hours_per_day']
        remaining_hours_per_week = auto_plan_data['remaining_hours_per_week']

        work_hours_per_day = defaultdict(float)
        working_hours = resource._get_flexible_resource_work_hours(
            split_shift_intervals,
            auto_plan_data['flexible_resources_hours_per_day'][resource.id],
            auto_plan_data['flexible_resources_hours_per_week'][resource.id],
            work_hours_per_day,
        )
        rate = shift.allocated_hours / working_hours if working_hours > 0.0 else float('inf')
        for day, hours in work_hours_per_day.items():
            hours_to_work = hours * rate
            if (hours_to_work > remaining_hours_per_day[resource.id].get(day, 0.0) or hours_to_work > remaining_hours_per_week[resource.id].get(weeknumber(locale, day), 0.0)):
                return rate, True
        return rate, False

    def _auto_plan_register_assignment(self, shift, resource, original_allocated_hours, auto_plan_data):
        """ Book the load `shift` puts on `resource`, now that it has been assigned to it,
            and recompute the shift's `allocated_percentage` against the hours the resource
            will actually work over the shift's period.

            `original_allocated_hours` is the shift's `allocated_hours` from before the
            assignment, which recomputes them.
        """
        locale = auto_plan_data['locale']
        remaining_hours_per_day = auto_plan_data['remaining_hours_per_day']
        remaining_hours_per_week = auto_plan_data['remaining_hours_per_week']

        start_utc = shift.start_datetime.replace(tzinfo=UTC)
        end_utc = shift.end_datetime.replace(tzinfo=UTC)
        if resource._is_flexible():
            user_tz = auto_plan_data['user_tz']
            resource_work_intervals, resource_hours_per_day, resource_hours_per_week = resource._get_flexible_resource_valid_work_intervals(start_utc.astimezone(user_tz), end_utc.astimezone(user_tz))
            hours_needed_to_plan_by_day = defaultdict(float)
            work_hours = resource._get_flexible_resource_work_hours(
                resource_work_intervals[resource.id],
                resource_hours_per_day[resource.id],
                resource_hours_per_week[resource.id],
                hours_needed_to_plan_by_day,
            )
            if work_hours > 0.0:
                rate = original_allocated_hours / work_hours
                for day, hours in hours_needed_to_plan_by_day.items():
                    remaining_hours_per_day[resource.id][day] -= hours * rate
                    remaining_hours_per_week[resource.id][weeknumber(locale, day)] -= hours * rate
        else:
            resource_work_intervals, calendar_work_intervals = shift.resource_ids._get_valid_work_intervals(start_utc, end_utc, calendars=shift.company_id.resource_calendar_id)
            work_hours = shift._get_working_hours_over_period(start_utc, end_utc, resource_work_intervals, calendar_work_intervals)

        shift.allocated_percentage = 100 * original_allocated_hours / work_hours if work_hours else 100

# A. Represent the resoures shifts and the open shift on a timeline
#   Legend
#   ┏━━ : open shift                    ┌─────────────────── 2023/01/02 ────────────────┬─────────────────── 2023/01/03 ────────────────┐
#   ┌── : resource's shifts             0 ───────────── 8 ~~~~~~~~~~~~~ 16 ──────────── 0 ───────────── 8 ~~~~~~~~~~~~~ 16 ──────────── 0
#   ~~~ : resource's schedule           ├───────────────┼───────────────┼───────────────┼───────────────┼───────────────┼───────────────┤

# a/ Allocated Hours (ah) :                             ┏━━ 3h ━┓                                               ┌────── 8h ─────┐
#                                                       ┡━━━━━━━┹────────────────────── 7h ─────────────────────┴───────┬───────┘
#                                                       └───────────────────────────────────────────────────────────────┘

# b/ Rates [ah / (end - start)] :                       ┏━━ 75% ┓                                               ┌───── 100% ────┐
#                                                       ┡━━━━━━━┹───────────────────── 25% ─────────────────────┴───────┬───────┘
#                                                       └───────────────────────────────────────────────────────────────┘

# c/ Increments Timeline :                             ┌↑75%
#   Visual :                                           └↑25%    ↓75%                                            ↑100%   ↓25%    ↓100%
#   Array :                                             ┗━━━━━━━┹───────────────────────────────────────────────┴───────┴───────┘
# [
#    (dt(2023, 1, 2,  8, 0), +1.00),
#    (dt(2023, 1, 2, 12, 0), -0.75),
#    (dt(2023, 1, 3, 12, 0), +1.00),
#    (dt(2023, 1, 3, 16, 0), -0.25),
#    (dt(2023, 1, 3, 20, 0), -1.00),
# ]

# d/ Values Timeline :
#   Visual :                                            |100%   |25%                                            |125%   |100%   |0%
#   Array :                                             ┗━━━━━━━┹───────────────────────────────────────────────┴───────┴───────┘
# [
#    (dt(2023, 1, 2,  8, 0),  1.00),
#    (dt(2023, 1, 2, 12, 0),  0.25),
#    (dt(2023, 1, 3, 12, 0),  1.25),
#    (dt(2023, 1, 3, 16, 0),  1.00),
#    (dt(2023, 1, 3, 20, 0),  0.00),
# ]

# B. Try to assign each open shift to a resource

# 1) Check that the shift fits in the resource's schedule
#   We just get the schedule intervals of the resource, convert the shift to intervals, and check the difference.

# 2) Check that the resource would not be overloaded this day
#   Delimit days with ghost events at 0:00. Then compute the total time worked per day and compare it to the resource's max load.
#   We do so considering that every resource have the same time zone (the user's one).

# 3) ...and that it would not conflict with the resource's other shifts (sum of rates > 100%)
#   Visual :                            |0%             |100%   |25%                    |25%                    |125%   |100%   |0%     |0%
#   Array :                             └────── A ──────┗━━ B ━━┹────────── C ──────────┴───────────────────────┴───────┴───────┴───────┘
# [                                     ^                                               ^                                               ^
#    (dt(2023, 1, 2,  0, 0),  0.00), <
#    (dt(2023, 1, 2,  8, 0),  1.25),                         2) Worked Hours on 2023/01/02
#    (dt(2023, 1, 2, 12, 0),  0.25),                            = 8h * 0% (A) + 4h * 125% (B) + 12h * 25% (C)
#    (dt(2023, 1, 3,  0, 0),  0.25), <                          = 0h          + 5h            + 3h
#    (dt(2023, 1, 3, 12, 0),  1.00),                            = 8h => OK
#    (dt(2023, 1, 3, 16, 0),  0.75),
#    (dt(2023, 1, 3, 20, 0),  0.00),                         3) rate(B) = 100% => OK
#    (dt(2023, 1, 4,  0, 0),  0.00), <
# ]

    @api.model
    def _shift_records_to_timeline_per_resource_id(self, records, flexible_resources, min_start, max_end, remaining_hours_per_day, remaining_hours_per_week, locale):
        timeline_and_worked_hours_per_resource_id = defaultdict(list)
        flexible_resource_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(min_start, max_end)

        for record in records:
            start, end = record.start_datetime, record.end_datetime
            resource = record.resource_ids[:1]
            resource_id = resource.id
            allocated_hours = record.allocated_hours

            if resource_id not in flexible_resources.ids:
                rate = allocated_hours * 3600 / (end - start).total_seconds() / 3600
            else:
                record_intervals = Intervals([(start.replace(tzinfo=UTC), end.replace(tzinfo=UTC), set())]) & flexible_resource_work_intervals[resource_id]
                work_hours_per_day = defaultdict(float)

                work_hours = resource._get_flexible_resource_work_hours(record_intervals, flexible_resources_hours_per_day[resource_id], flexible_resources_hours_per_week[resource_id], work_hours_per_day)
                rate = allocated_hours / work_hours if work_hours > 0.0 else float('inf')

                for day, hours in work_hours_per_day.items():
                    remaining_hours_per_day[resource_id][day] -= rate * hours
                    remaining_hours_per_week[resource_id][weeknumber(locale, day)] -= rate * hours

            timeline_and_worked_hours_per_resource_id[resource_id].extend([
                (start, rate), (end, -rate)
            ])
        for resource_id, timeline in timeline_and_worked_hours_per_resource_id.items():
            timeline_and_worked_hours_per_resource_id[resource_id] = self._increments_to_values(timeline)
        return timeline_and_worked_hours_per_resource_id

    @api.model
    def _get_new_timeline_if_fits_in(self, split_shift_intervals, rate, resource_hours_per_day, timeline, empty_timeline):
        if rate > 1:
            return False
        add_midnights = True
        for split_shift_start, split_shift_end, _ in split_shift_intervals:
            start = split_shift_start.astimezone(UTC).replace(tzinfo=None)
            end = split_shift_end.astimezone(UTC).replace(tzinfo=None)
            increments = self._values_to_increments(timeline) + [(start, rate), (end, -rate)]
            if add_midnights:
                # Add ghost events at 0:00 to delimit days. This condition prevents from adding ghost events on each iteration.
                increments += empty_timeline
                add_midnights = False
            timeline = self._increments_to_values(increments, check=(start, end, resource_hours_per_day))
            if not timeline:
                return False
        return timeline

    @api.model
    def _increments_to_values(self, increments, check=False):
        """ Transform a timeline of increments into a timeline of values by accumulating the increments.
            If check is a tuple (start, end, resource_hours_per_day), the timeline is checked to ensure
            that the resource would not be overloaded this day or have an "occupation rate" > 100% between start and end.

            :param increments: List of tuples (instant, increment).
            :param check: False or a tuple (start, end, resource_hours_per_day).
            :return: List of tuples (instant, value) if check is False or the timeline is valid, else False.
        """
        if not increments:
            return []
        if check:
            start, end, _dummy = check

        values = []
        # Sum and sort increments by instant.
        increments_sum_per_instant = defaultdict(float)
        for instant, increment in increments:
            increments_sum_per_instant[instant] += increment
        increments = list(increments_sum_per_instant.items())
        increments.sort(key=lambda increment: increment[0])
        last_instant, last_value = increments[0][0], 0.0
        for increment in increments:
            last_value += increment[1]
            last_instant = increment[0]
            # Check if the occupation rate exceeds 100%.
            if check and last_value > 1 and start <= last_instant <= end:
                return False
            values.append((last_instant, last_value))
        return values

    @api.model
    def _values_to_increments(self, values):
        """ Transform a timeline of values into a timeline of increments by subtracting the values.

            :param values: List of tuples (instant, value).
            :return: List of tuples (instant, increment).
        """
        increments = []
        last_value = 0
        for value in values:
            increments.append((value[0], value[1] - last_value))
            last_value = value[1]
        return increments

    @api.model
    def action_rollback_auto_plan_ids(self, shifts_data):
        open_shift_assigned = shifts_data["open_shift_assigned"]
        shifts = self.browse(open_shift_assigned)
        with self.env.protecting([self._fields['allocated_hours']], shifts):
            shifts.write({'resource_ids': False})

    def action_unschedule(self):
        return self.with_context(from_slot_unscheduling=True).write({
            'start_datetime': False,
            'end_datetime': False,
            'resource_ids': False,
        })

    # ----------------------------------------------------
    # Gantt - Calendar view
    # ----------------------------------------------------

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        result = super(PlanningSlot, self.with_context(scale=scale)).get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
        if "resource_ids" in groupby:
            resource_ids = [group["resource_ids"][0] for group in result["groups"] if group["resource_ids"]]
            employees = self.env["resource.resource"].browse(resource_ids).mapped("employee_id")
            result["working_periods"] = employees._get_working_periods_by_field(start_date, stop_date, 'resource_id')
        planning_data = self._get_gantt_planning_data(domain, start_date, stop_date)
        result.update({"planning_data": planning_data})

        progress_bars = result.get('progress_bars')

        if not progress_bars:
            return result

        last_group_by = progress_bar_fields[-1]
        # __default reference the total progress bar
        progress_bars['__default'] = {
            False: {
                "value": 0,
                "max_value": 0,
            }
        }

        for value in progress_bars[last_group_by].values():
            if not isinstance(value, dict):
                continue

            progress_bars['__default'][False]["value"] += value.get("value", 0)
            progress_bars['__default'][False]["max_value"] += value.get("max_value", 0)

        return result

    def _get_gantt_planning_data(self, domain, start_date, stop_date):
        resources = self.search_fetch(domain).mapped('resource_ids')

        work_interval_per_resource = defaultdict(list)
        flexible_per_resource = {False: False}
        avg_hours_per_resource = {False: 0}

        if resources:
            start_datetime, end_datetime = fields.Datetime.from_string(start_date).replace(tzinfo=UTC), fields.Datetime.from_string(stop_date).replace(tzinfo=UTC)
            work_intervals_per_resource, _dummy = resources._get_valid_work_intervals(start_datetime, end_datetime)

            # Export work intervals in UTC
            for resource_id, resource_work_intervals_per_resource in work_intervals_per_resource.items():
                for resource_work_interval in resource_work_intervals_per_resource:
                    work_interval_per_resource[resource_id].append((resource_work_interval[0].astimezone(UTC), resource_work_interval[1].astimezone(UTC)))

            # Add the flexible status per resource and the average daily work hours per resource calendar to the output
            for resource in set(resources):
                flexible_per_resource[resource.id] = resource._is_flexible()
                avg_hours_per_resource[resource.id] = 24 if resource._is_fully_flexible() else (resource.calendar_id or self.env.company.resource_calendar_id).hours_per_day

        return {
            "work_intervals": work_interval_per_resource,
            "is_flexible": flexible_per_resource,
            "avg_hours": avg_hours_per_resource,
        }

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        if field != "resource_ids":
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)

        resources = self.env['resource.resource'].browse(res_ids)
        leaves_mapping = resources._get_unavailable_intervals(start, stop)
        company_leaves = self.env.company.resource_calendar_id._unavailable_intervals(start.replace(tzinfo=UTC), stop.replace(tzinfo=UTC))
        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        result = {False: []}
        for resource in resources:
            # return no unavailability if the resource is fully flexible hours (both material and employee).
            if ((resource.id not in res_ids)
                or (resource and resource._is_fully_flexible())
                or (resource and resource.id not in leaves_mapping and resource._is_flexible())):
                continue
            calendar = leaves_mapping.get(resource.id, company_leaves)
            # remove intervals smaller than a cell, as they will cause half a cell to turn grey
            # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
            # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
            notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, calendar)
            result[resource.id] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]

        if not any(resource._is_flexible() for resource in resources):
            calendar = leaves_mapping.get(False, company_leaves)
            notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, calendar)
            result[False] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]

        return result

    @api.model
    def get_unusual_days(self, date_from, date_to=None):
        return self.env.user.employee_id._get_unusual_days(date_from, date_to)

    # ----------------------------------------------------
    # Period Duplication
    # ----------------------------------------------------

    @api.model
    def action_copy_previous_week(self, date_start_week, view_domain):
        date_end_copy = datetime.strptime(date_start_week, DEFAULT_SERVER_DATETIME_FORMAT)
        date_start_copy = date_end_copy - relativedelta(days=7)
        domain = [
            ('recurrency_id', '=', False),
            ('was_copied', '=', False)
        ]
        for dom in view_domain:
            if dom in ['|', '&', '!']:
                domain.append(dom)
            elif dom[0] == 'start_datetime':
                domain.append(('start_datetime', '>=', date_start_copy))
            elif dom[0] == 'end_datetime':
                domain.append(('end_datetime', '<=', date_end_copy))
            else:
                domain.append(tuple(dom))
        slots_to_copy = self.search(domain)

        new_slot_values = []
        new_slot_values = slots_to_copy._copy_slots(date_start_copy, date_end_copy, relativedelta(days=7))
        slots_to_copy.write({'was_copied': True})
        if new_slot_values:
            return [self.create(new_slot_values).ids, slots_to_copy.ids]
        return False

    def action_rollback_copy_previous_week(self, copied_slot_ids):
        self.browse(copied_slot_ids).was_copied = False
        self.exists().unlink()

    # ----------------------------------------------------
    # Sending Shifts
    # ----------------------------------------------------

    def get_employees_with_missing_data(self):
        """ Check if the employees to send the slot have a work email set.

            This method is used in a rpc call.

            :returns: a dictionnary containing the all needed information to continue the process.
                Returns None, if no employee or all employees have an email set.
        """
        self.ensure_one()
        if not self.employee_ids.has_access('write'):
            return None
        employees = self.employee_ids or self._get_employees_to_send_slot()
        employee_ids_without_contact_info = employees.filtered(lambda employee: not employee[self._get_employee_contact_field()]).ids
        if not employee_ids_without_contact_info:
            return None
        context = dict(self.env.context)
        context['force_email'] = True
        context['form_view_ref'] = self._get_employee_contact_missing_fields_form_view_ref()
        return {
            'relation': 'hr.employee',
            'res_ids': employee_ids_without_contact_info,
            'context': context,
        }

    def _get_employee_contact_missing_fields_form_view_ref(self):
        return 'planning.hr_employee_view_form_email'

    def _get_employee_contact_field(self):
        return 'work_email'

    def _get_employees_to_send_slot(self):
        self.ensure_one()
        employees_with_email = self.employee_ids.filtered(self._get_employee_contact_field())
        if not self.employee_public_ids or not employees_with_email:
            domain = Domain('company_id', '=', self.company_id.id) & Domain(self._get_employee_contact_field(), '!=', False)
            if self.role_id:
                domain &= Domain('planning_role_ids', '=', False) | Domain('planning_role_ids', 'in', self.role_id.id)
            return self.env['hr.employee'].sudo().search(domain)
        return employees_with_email

    def _get_notification_action(self, notif_type, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notif_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_planning_publish_and_send(self):
        start_time_vals, end_time_vals = self.mapped('start_datetime'), self.mapped('end_datetime')
        if False in start_time_vals or False in end_time_vals:
            raise UserError(self.env._("Please set a start and end date on the shift before sending it."))
        notif_type = "success"
        start, end = min(start_time_vals), max(end_time_vals)
        if all(shift.state == '2_published' for shift in self) or not start or not end:
            notif_type = "warning"
            message = self.env._('There are no shifts to publish and send.')
        else:
            planning = self.env['planning.planning'].create({
                'start_datetime': start,
                'end_datetime': end,
            })
            planning._send_planning(slots=self, employees=self.sudo().employee_ids)
            message = self.env._('The shifts have successfully been published and sent.')
        return self._get_notification_action(notif_type, message)

    def action_send(self):
        self.ensure_one()
        if not self.start_datetime or not self.end_datetime:
            raise UserError(self.env._("Please set a start and end date on the shift before sending it."))

        if self.state == '1_draft' and not (self.employee_public_ids and all(self.employee_public_ids.mapped(self._get_employee_contact_field()))):
            self.state = '2_published'
        employee_ids = self._get_employees_to_send_slot()
        self._send_slot(employee_ids, self.start_datetime, self.end_datetime)
        message = self.env._("Shift sent")
        return self._get_notification_action('success', message)

    def action_save_template(self):
        """ Used to save template of a shift."""
        self.ensure_one()
        if not (self.start_datetime or self.end_datetime):
            return self._get_notification_action('danger', self.env._('Schedule this shift to save it as a template'))
        if self.template_id:
            return self._get_notification_action('danger', self.env._('A template for this shift already exists'))
        if self.allow_template_creation:
            self.template_creation = True

    def action_unpublish(self):
        if not self.env.user.has_group('planning.group_planning_manager'):
            raise AccessError(self.env._('You are not allowed to reset shifts to draft.'))
        published_shifts = self.filtered(lambda shift: shift.state == '2_published' and shift.employee_ids)
        if published_shifts:
            published_shifts.write({'state': '1_draft', 'publication_warning': False})
            notif_type = "success"
            message = self.env._('Shifts reset to draft')
        else:
            notif_type = "warning"
            message = self.env._('There are no shifts to reset to draft.')
        return self._get_notification_action(notif_type, message)

    # ----------------------------------------------------
    # Print planning
    # ----------------------------------------------------
    def _print_planning_get_fields_to_copy(self):
        return ['employee_ids', 'company_id', 'allocated_percentage', 'allocated_hours', 'resource_ids', 'start_datetime', 'end_datetime', 'role_id']

    def _print_planning_get_slot_title(self, slot_start, slot_end, tz_info, group_by):
        def print_planning_format_time(date, tz_info):
            return format_time(self.env, date.time(), tz_info, 'short')

        allocated_hours_formatted = ""
        if self.allocated_percentage != 100:
            time_str = float_to_time(self.allocated_hours).strftime('%Hh%M')
            hours, minutes = time_str.split('h')
            # Converting to int removes the leading zero (e.g., '08' -> 8)
            hours = str(int(hours))

            if minutes == '00':
                allocated_hours_str = f"{hours}h"
            else:
                allocated_hours_str = f"{hours}h{minutes}"
            allocated_hours_formatted = f" ({allocated_hours_str})"
        name_get = ""
        if group_by == "role_id":
            if self.employee_ids:
                name_get = format_list(self.env, self.employee_ids.mapped('name'))
        elif group_by == "resource_ids":
            if self.role_id:
                name_get = self.role_id.name
        else:
            name_get = format_list(self.env, self.employee_ids.mapped('name')) if self.employee_ids else ""
            if self.role_id:
                if name_get:
                    name_get += f" - {self.role_id.name}"
                else:
                    name_get = self.role_id.name

        slot_title = f"{print_planning_format_time(slot_start, tz_info)} – {print_planning_format_time(slot_end, tz_info)}{allocated_hours_formatted}"
        if name_get:
            slot_title += f" {name_get}"
        return slot_title

    @api.model
    def action_print_plannings(self, date_start, date_end, group_bys, domain):

        def print_planning_split_fake_pill(shift, values):
            shift.ensure_one()
            assert 'start_datetime' in values and 'end_datetime' in values and not shift._origin
            record = print_planning_create_fake_pill(shift, {'start_datetime': values.get('start_datetime').astimezone(UTC).replace(tzinfo=None)})
            shift.update({'end_datetime': values.get('end_datetime').astimezone(UTC).replace(tzinfo=None)})
            return record

        def print_planning_create_fake_pill(shift, vals=None):
            record = self.env['planning.slot'].new({
                **shift._read_format(shift._print_planning_get_fields_to_copy())[0],
                **(vals or {}),
            })
            # copy method called inside the original split_pill method recomputes the allocated_hours again after the split (dates changed)
            record._compute_allocated_hours()
            return record

        def print_planning_get_fake_pill_datetime(datetime_per_resource_per_day, resource_id, day, tz_info, default):
            if day in datetime_per_resource_per_day[resource_id]:
                return datetime_per_resource_per_day[resource_id][day].astimezone(tz_info)

            return datetime.combine(day, default, tzinfo=tz_info)

        def print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource_id, day, tz_info):
            return print_planning_get_fake_pill_datetime(start_datetime_per_resource_per_day, resource_id, day, tz_info, time.min)

        def print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource_id, day, tz_info):
            return print_planning_get_fake_pill_datetime(end_datetime_per_resource_per_day, resource_id, day, tz_info, time.max)

        def print_planning_add_slot(shift, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by):
            if float_utils.float_is_zero(shift.allocated_hours, precision_digits=2):
                return

            slot_start = shift.start_datetime.astimezone(tz_info)
            slot_end = shift.end_datetime.astimezone(tz_info)
            date = format_date(self.env, slot_start, date_format="EEEE d")
            for index, week, _dummy in weeks:
                if date in week:
                    group_by_slots_per_day_per_week[index][group][date].append({
                        "title": shift._print_planning_get_slot_title(slot_start, slot_end, tz_info, group_by),
                        "style": f"background-color: {get_light_color(shift.role_id.color, 0.5, not shift.resource_ids)};"
                    })
                    return

        def print_planning_update_datetime(_datetime, resource_id, datetime_per_resource_per_day, func):
            day = _datetime.date()
            if day in datetime_per_resource_per_day[resource_id]:
                datetime_per_resource_per_day[resource_id][day] = func(datetime_per_resource_per_day[resource_id][day], _datetime)
            else:
                datetime_per_resource_per_day[resource_id][day] = _datetime

        def print_planning_flexible_resources_work_intervals(start, end, resources):
            assert all(resource._is_flexible() and not resource._is_fully_flexible() for resource in resources)
            return {resource.id: Intervals([(start, end, self.env['resource.calendar.attendance'])]) for resource in resources}

        group_bys = [g for g in (group_bys or []) if self.fields_get(g)[g.split(':')[0]]['type'] not in {"datetime", "date"}]
        if not group_bys:
            group_bys = ['resource_ids']

        group_by = group_bys[-1]
        date_start = datetime.strptime(date_start, DEFAULT_SERVER_DATETIME_FORMAT)
        date_end = datetime.strptime(date_end, DEFAULT_SERVER_DATETIME_FORMAT)

        if date_end < date_start:
            date_start, date_end = date_end, date_start

        group_by_slots = self.env['planning.slot']._read_group(
            domain,
            [group_by],
            ['id:recordset'],
        )

        if not group_by_slots:
            return False

        tz_info = ZoneInfo(self._get_tz())
        day_start_in_user_tz = date_start.astimezone(tz_info).date()
        day_end_in_user_tz = date_end.astimezone(tz_info).date()
        days_count = (day_end_in_user_tz - day_start_in_user_tz).days + 1
        days = [day_start_in_user_tz + timedelta(days=i) for i in range(days_count)]
        group_by_slots_per_day_per_week = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        unassigned = self.env._("Open Shifts") if group_by == 'resource_ids' else self.env._("Undefined %(group)s", group=self.fields_get(group_by)[group_by]["string"])
        group_by_name_by_id = {}
        non_flexible_resources_ids = set()
        flexible_resources_ids = set()

        group_by_field = self._fields[group_by]
        selection_value_per_key = {}
        if group_by_field.type == 'selection':
            selection_value_per_key = dict(group_by_field._description_selection(self.env))

        for g, slots in group_by_slots:
            if group_by_field.relational:
                g_id = str(g.id) if g else 'false'
                g_name = g.display_name or unassigned
            else:
                g_id = str(g) if g is not False else 'false'
                if g is False:
                    g_name = unassigned
                elif group_by_field.type == 'selection':
                    g_name = selection_value_per_key.get(g, unassigned)
                else:
                    g_name = str(g)
            group_by_name_by_id[g_id] = g_name
            for slot in slots:
                for resource in slot.resource_ids:
                    (flexible_resources_ids if not resource._is_fully_flexible() and resource._is_flexible() else non_flexible_resources_ids).add(resource.id)

        non_flexible_resources = self.env['resource.resource'].browse(non_flexible_resources_ids)
        flexible_resources = self.env['resource.resource'].browse(flexible_resources_ids)

        start_utc, end_utc = date_start.replace(tzinfo=UTC), date_end.replace(tzinfo=UTC)
        resources_work_intervals, _dummy = non_flexible_resources._get_valid_work_intervals(
            start_utc, end_utc
        )

        resources_work_intervals.update(print_planning_flexible_resources_work_intervals(start_utc, end_utc, flexible_resources))

        weeks = [
            (
                int(i / 7),
                [format_date(self.env, day, date_format="EEEE d") for day in days[i:i + 7]],
                self.env._(
                    "Week %(start_date)s - %(end_date)s",
                    start_date=format_date(self.env, days[i:i + 7][0], date_format="w, MMM d"),
                    end_date=format_date(self.env, days[i:i + 7][-1], date_format="MMM d")
                ),
            )
            for i in range(0, len(days), 7)
        ]

        start_datetime_per_resource_per_day, end_datetime_per_resource_per_day = defaultdict(dict), defaultdict(dict)
        for resource_id, intervals in resources_work_intervals.items():
            for start_datetime, end_datetime, _dummy in intervals._items:
                print_planning_update_datetime(start_datetime, resource_id, start_datetime_per_resource_per_day, min)
                print_planning_update_datetime(end_datetime, resource_id, end_datetime_per_resource_per_day, max)

        def get_sort_key(group_key):
            if group_by_field.relational:
                return str(group_key.display_name or '')
            elif group_key is False:
                return ''
            elif group_by_field.type == 'selection':
                return str(selection_value_per_key.get(group_key, ''))
            return str(group_key)

        for group_val, slots in sorted(group_by_slots, key=lambda x: get_sort_key(x[0])):
            if group_by_field.relational:
                group = group_val.id if group_val else False
            else:
                group = group_val if group_val is not False else False
            for slot in slots.sorted(key=lambda s: (s.start_datetime, s.id)):
                slot_start = slot.start_datetime.astimezone(tz_info)
                slot_end = slot.end_datetime.astimezone(tz_info)

                slot_start_day = slot_start.date()
                slot_end_day = slot_end.date()
                if group_by == 'resource_ids':
                    resource = group_val
                else:
                    resource = slot.resource_ids[:1]

                # one day slot
                if slot_start_day == slot_end_day:
                    print_planning_add_slot(slot, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by)
                else:
                    # slot on more than one day, we do a fake copy using new without storing in db and
                    # we use split_pill function to cut the slot in many days
                    fake_slot = print_planning_create_fake_pill(slot)

                    # remove the part of the pill happening in the previous weeks
                    first_day = days[0]
                    if slot_start_day < first_day:
                        fake_slot = print_planning_split_fake_pill(fake_slot, {
                            "start_datetime": print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource.id, first_day, tz_info),
                            "end_datetime": print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource.id, first_day + timedelta(days=-1), tz_info)
                        })

                    # remove the part of the pill happening in the next weeks
                    last_day = days[-1]
                    if slot_end_day > last_day:
                        print_planning_split_fake_pill(fake_slot, {
                            "start_datetime": print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource.id, last_day + timedelta(days=1), tz_info),
                            "end_datetime": print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource.id, last_day, tz_info),
                        })

                    # split the pill in different pills, pill per day
                    current_day = fake_slot.start_datetime.date()
                    last_day = fake_slot.end_datetime.date()
                    while current_day < last_day:
                        split_slot = print_planning_split_fake_pill(fake_slot, {
                            "start_datetime": print_planning_get_fake_pill_start_datetime(start_datetime_per_resource_per_day, resource.id, current_day + timedelta(days=1), tz_info),
                            "end_datetime": print_planning_get_fake_pill_end_datetime(end_datetime_per_resource_per_day, resource.id, current_day, tz_info),
                        })

                        print_planning_add_slot(fake_slot, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by)
                        fake_slot = split_slot
                        current_day += timedelta(days=1)

                    print_planning_add_slot(fake_slot, tz_info, group_by_slots_per_day_per_week, group, weeks, group_by)

        # groups were inserted in the dict in a specific order (false, then sorted non DESC order)
        # but in Qweb, the order was lost
        # so we transformed it to a dict {week: (group, {day: slots})}
        group_by_slots_per_day_per_week_formatted = {
            week: [(group, val) for group, val in data.items()]
            for week, data in group_by_slots_per_day_per_week.items()
        }

        return self.env.ref('planning.report_planning_slot').with_context(discard_logo_check=True, allow_printing_planning_report=True).report_action(None,
            data={
                'group_by_slots_per_day_per_week': group_by_slots_per_day_per_week_formatted,
                'weeks': weeks,
                'group_by_name_by_id': group_by_name_by_id,
            }
        )

    # ----------------------------------------------------
    # Business Methods
    # ----------------------------------------------------

    def _calculate_slot_duration(self):
        self.ensure_one()
        if not self.start_datetime or not self.end_datetime:
            return 0.0
        resource = self.resource_ids.filtered(lambda r: r.resource_type == 'user')[:1] or self.resource_ids[:1]
        period = self.end_datetime - self.start_datetime
        if resource:
            start = self.start_datetime.replace(tzinfo=UTC).astimezone(ZoneInfo(resource.tz))
            end = self.end_datetime.replace(tzinfo=UTC).astimezone(ZoneInfo(resource.tz))
            if resource._is_flexible():
                work_intervals, hours_per_day, hours_per_week = resource._get_flexible_resource_valid_work_intervals(start, end)
                slot_duration = resource._get_flexible_resource_work_hours(work_intervals[resource.id], hours_per_day[resource.id], hours_per_week[resource.id])
            else:
                work_intervals, _dummy = resource._get_valid_work_intervals(start, end)
                slot_duration = sum_intervals(work_intervals[resource.id])
        else:
            slot_duration = period.total_seconds() / 3600
        # if the resource is an employee, the hours_per_day of its calendar is used as max_hours_per_day.
        if resource.resource_type == 'user' and resource.employee_id:
            max_hours_per_day = resource.employee_id.resource_calendar_id.hours_per_day
        # For other resource and open shifts, we refer to the max of the company's default contract
        else:
            max_hours_per_day = self.company_id.resource_calendar_id.hours_per_day
        max_duration = (period.days + (1 if period.seconds else 0)) * max_hours_per_day
        if not max_duration or max_duration >= slot_duration:
            return slot_duration
        return max_duration

    # ----------------------------------------------------
    # Copy Slots
    # ----------------------------------------------------

    def _add_delta_with_dst(self, start, delta):
        """
        Add a time delta to a naive UTC datetime, adjusting the hours if needed
        to account for a shift in the local timezone between the start datetime and
        the resulting datetime (typically due to daylight saving time).

        :param datetime.datetime start: the origin naive datetime in UTC timezone, without timezone info.
        :param datetime.timedelta delta: the time difference to add.
        :returns: the resulting naive datetime in UTC timezone.
        :rtype: datetime.datetime
        """
        try:
            tz = ZoneInfo(self._get_tz())
        except ZoneInfoNotFoundError:
            tz = timezone.utc
        start = start.replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)
        result = start + delta
        return result.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)

    def _init_remaining_hours_to_plan(self, remaining_hours_to_plan):
        """
            Inits the remaining_hours_to_plan dict for a given slot and returns wether
            there are enough remaining hours.

            :return a bool representing wether or not there are still hours remaining
        """
        self.ensure_one()
        return True

    def _update_remaining_hours_to_plan_and_values(self, remaining_hours_to_plan, values):
        """
            Update the remaining_hours_to_plan with the allocated hours of the slot in `values`
            and returns wether there are enough remaining hours.

            If remaining_hours is strictly positive, and the allocated hours of the slot in `values` is
            higher than remaining hours, than update the values in order to consume at most the
            number of remaining_hours still available.

            :return a bool representing wether or not there are still hours remaining
        """
        self.ensure_one()
        return True

    def _get_split_slot_values(self, values, intervals, remaining_hours_to_plan, unassign=False):
        """
            Generates and returns slots values within the given intervals

            The slot in values, which represents a forecast planning slot, is split in multiple parts
            filling the (available) intervals.

            :return a vals list of the slot to create
        """
        self.ensure_one()
        split_slot_values = []
        for start_inter, end_inter, _resource in intervals:
            new_slot_vals = {
                **values,
                'start_datetime': start_inter.astimezone(UTC).replace(tzinfo=None),
                'end_datetime': end_inter.astimezone(UTC).replace(tzinfo=None),
            }
            was_updated = self._update_remaining_hours_to_plan_and_values(remaining_hours_to_plan, new_slot_vals)
            period = end_inter - start_inter
            slot_duration = period.total_seconds() / 3600
            human_resources = self.resource_ids.filtered(lambda r: r.resource_type == 'user')
            # If the slot is assigned to a flexible resource, the allocated hours are computed based on the hours_per_day of the resource calendar
            # However if it's a fully flexible resource, the allocated hours are the same as the slot duration.
            if (
                not unassign
                and len(human_resources) == 1
                and human_resources._is_flexible() and
                not human_resources._is_fully_flexible()
            ):
                # refer to the hours_per_day if the slot duration exceeds it.
                max_hours_per_day = human_resources.hours_per_day
                max_duration = (period.days + (1 if period.seconds else 0)) * max_hours_per_day
                slot_duration = min(slot_duration, max_duration)
            new_slot_vals['allocated_hours'] = float_utils.float_round(
                slot_duration * (self.allocated_percentage / 100.0),
                precision_digits=2
            )
            if not was_updated:
                return split_slot_values
            if unassign:
                new_slot_vals['resource_ids'] = False
            split_slot_values.append(new_slot_vals)
        return split_slot_values

    def _copy_slots(self, start_dt, end_dt, delta):
        """
            Copy slots planned between `start_dt` and `end_dt`, after a `delta`

            Takes into account the resource calendar and the slots already planned.
            All the slots will be copied, whatever the value of was_copied is.

            :return a vals list of the slot to create
        """
        # 1) Retrieve all the slots of the new period and create intervals within the slots will have to be unassigned (resource_slots_intervals),
        #    add it to `unavailable_intervals_per_resource`
        # 2) Retrieve all the calendars for the resource and their validity intervals (intervals within which the calendar is valid for the resource)
        # 3) For each calendar, retrieve the attendances and the leaves. Add attendances by resource in `attendance_intervals_per_resource` and
        #    the leaves by resource in `unavailable_intervals_per_resource`
        # 4) For each slot, check if the slot is at least within an attendance and outside a company leave :
        #    - If it is a planning :
        #       - Copy it if the resource is available
        #       - Copy and unassign it if the resource isn't available
        #    - Otherwise :
        #       - Split it and assign the part within resource work intervals
        #       - Split it and unassign the part within resource leaves and outside company leaves
        resource_per_calendar = defaultdict(lambda: self.env['resource.resource'])
        resource_calendar_validity_intervals = defaultdict(dict)
        attendance_intervals_per_resource = defaultdict(Intervals)  # key: resource, values: attendance intervals
        unavailable_intervals_per_resource = defaultdict(Intervals)  # key: resource, values: unavailable intervals
        attendance_intervals_per_calendar = defaultdict(Intervals)  # key: calendar, values: attendance intervals (used for company calendars)
        leave_intervals_per_calendar = defaultdict(Intervals)  # key: calendar, values: leave intervals (used for company calendars)
        new_slot_values = []
        # date utils variable
        start_dt_delta = start_dt + delta
        end_dt_delta = end_dt + delta
        start_dt_delta_utc = start_dt_delta.replace(tzinfo=UTC)
        end_dt_delta_utc = end_dt_delta.replace(tzinfo=UTC)
        # 1)
        # Search for all resource slots already planned
        resource_slots = self.search([
            ('start_datetime', '>=', start_dt_delta),
            ('end_datetime', '<=', end_dt_delta),
            ('resource_ids', 'in', self.resource_ids.ids),
        ])
        # And convert it into intervals
        for slot in resource_slots:
            for resource in slot.resource_ids:
                unavailable_intervals_per_resource[resource] |= Intervals([(
                    slot.start_datetime.replace(tzinfo=UTC),
                    slot.end_datetime.replace(tzinfo=UTC),
                    self.env['resource.calendar.leaves'])])
        # 2)
        resource_calendar_validity_intervals = self.resource_ids.sudo().filtered(lambda resource: not resource._is_flexible())._get_calendars_validity_within_period(
            start_dt_delta_utc, end_dt_delta_utc)
        for slot in self:
            for resource in slot.resource_ids:
                for calendar in resource_calendar_validity_intervals[resource.id]:
                    resource_per_calendar[calendar] |= resource
            company_calendar_id = slot.company_id.resource_calendar_id
            resource_per_calendar[company_calendar_id] |= self.env['resource.resource']  # ensures the company_calendar will be in resource_per_calendar keys.
        # 3)
        for calendar, resources in resource_per_calendar.items():
            # calendar can be empty here only for the company_calendar_id entry above, when the
            # company has no default Working Schedule configured (flexible resources are already
            # filtered out before this point, so they never reach this loop with an empty calendar).
            if not calendar:
                continue
            # For each calendar, retrieves the work intervals of every resource
            resources_per_tz = resources._get_resources_per_tz()
            attendances = {
                resource_id: Intervals(work_interval._items)
                for resource_id, work_interval in calendar._attendance_intervals_batch(
                    start_dt_delta_utc,
                    end_dt_delta_utc,
                    resources_per_tz=resources_per_tz
                ).items()
            }
            leaves = calendar._leave_intervals_batch(
                start_dt_delta_utc,
                end_dt_delta_utc,
                resources_per_tz=resources_per_tz
            )
            attendance_intervals_per_calendar[calendar] = attendances[False]
            leave_intervals_per_calendar[calendar] = leaves[False]
            for resource in resources:
                # for each resource, adds his/her attendances and unavailabilities for this calendar, during the calendar validity interval.
                attendance_intervals_per_resource[resource] |= (attendances[resource.id] & resource_calendar_validity_intervals[resource.id][calendar])
                unavailable_intervals_per_resource[resource] |= (leaves[resource.id] & resource_calendar_validity_intervals[resource.id][calendar])
        # 4)
        remaining_hours_to_plan = {}
        Slot = self.env['planning.slot']
        for slot in self:
            if not slot._init_remaining_hours_to_plan(remaining_hours_to_plan):
                continue
            values = slot.copy_data(default={'state': '1_draft'})[0]
            if not values.get('start_datetime') or not values.get('end_datetime'):
                continue
            values['start_datetime'] = slot._add_delta_with_dst(values['start_datetime'], delta)
            values['end_datetime'] = slot._add_delta_with_dst(values['end_datetime'], delta)
            if slot.allocation_type == 'forecast' and (not slot.resource_ids or all(r._is_fully_flexible() for r in slot.resource_ids)):
                new_slot_values.append(values)
                continue
            resource_ids = slot._convert_resource_ids_vals(values.get('resource_ids', []))
            if any(
                set(Slot._convert_resource_ids_vals(new_slot['resource_ids'] or [])) == set(resource_ids) and
                new_slot['start_datetime'] <= values['end_datetime'] and
                new_slot['end_datetime'] >= values['start_datetime']
                for new_slot in new_slot_values
            ):
                values['resource_ids'] = False
            interval = Intervals([(
                values.get('start_datetime').replace(tzinfo=UTC),
                values.get('end_datetime').replace(tzinfo=UTC),
                self.env['resource.calendar.attendance']
            )])
            company_calendar = slot.company_id.resource_calendar_id
            # Check if interval is contained in the resource work interval.
            # For flexible hours, ignore the resource work interval and return the whole interval of slot as valid.
            effective_attendance_intervals_per_resource = {}
            effective_unavailable_intervals_per_resource = {}
            if slot.resource_ids:
                attendance_interval_company = interval
                for resource in slot.resource_ids:
                    if resource._is_flexible():
                        effective_attendance_intervals_per_resource[resource.id] = interval
                    else:
                        effective_attendance_intervals_per_resource[resource.id] = interval & attendance_intervals_per_resource[resource]
                        # Check if interval is contained in the company attendances interval
                        attendance_interval_company &= attendance_intervals_per_calendar[company_calendar]
                    effective_unavailable_intervals_per_resource[resource.id] = interval & unavailable_intervals_per_resource[resource]
            else:
                attendance_resource = attendance_intervals_per_calendar[company_calendar]
                effective_attendance_intervals_per_resource[False] = interval & attendance_resource
                effective_unavailable_intervals_per_resource[False] = interval & leave_intervals_per_calendar[company_calendar]
                # Check if interval is contained in the company attendances interval
                attendance_interval_company = interval & attendance_intervals_per_calendar[company_calendar]
            # Check if interval is contained in the company leaves interval
            unavailable_interval_company = interval & leave_intervals_per_calendar[company_calendar]
            if not unavailable_interval_company:
                # Either the employee has, at least, some attendance that are not during the company unavailability
                # Either the company has, at least, some attendance that are not during the company unavailability

                if slot.allocation_type == 'planning':
                    # /!\ It can be an "Extended Attendance" (see hereabove), and the slot may be unassigned.
                    available_resources = []
                    for resource in slot.resource_ids:
                        if not effective_unavailable_intervals_per_resource.get(resource.id) and effective_attendance_intervals_per_resource.get(resource.id):
                            available_resources.append(resource.id)
                    if not available_resources and slot.resource_ids and not slot.employee_ids:
                        # If the resource type is not user and the resource is not available, do not copy it nor unassign it
                        continue
                    if values.get('resource_ids') is not False:
                        values['resource_ids'] = available_resources
                    if not slot._update_remaining_hours_to_plan_and_values(remaining_hours_to_plan, values):
                        # make sure the hours remaining are enough
                        continue
                    new_slot_values.append(values)
                else:
                    if effective_attendance_intervals_per_resource:
                        # if the resource has attendances, at least during a while of the future slot lifetime,
                        # 1) Work interval represents the availabilities of the employee
                        # 2) The unassigned intervals represents the slots where the employee should be unassigned
                        #    (when the company is not unavailable and the employee is unavailable)
                        work_interval_employees = None
                        unavailable_interval_resources = None
                        for resource in slot.resource_ids:
                            unavailable_interval_resource = unavailable_intervals_per_resource[resource]
                            work_interval_employee = effective_attendance_intervals_per_resource[resource.id] - unavailable_interval_resource
                            if work_interval_employees is None:
                                work_interval_employees = work_interval_employee
                            else:
                                work_interval_employees |= work_interval_employee
                            if unavailable_interval_resources is None:
                                unavailable_interval_resources = unavailable_interval_resource
                            else:
                                unavailable_interval_resources |= unavailable_interval_resource

                        unassigned_interval = (unavailable_interval_resources - unavailable_interval_company) & (attendance_interval_company - unavailable_interval_company)
                        split_slot_values = slot._get_split_slot_values(values, work_interval_employees, remaining_hours_to_plan)
                        if slot.employee_ids:
                            split_slot_values += slot._get_split_slot_values(values, unassigned_interval, remaining_hours_to_plan, unassign=True)
                    elif not slot.employee_ids:
                        # If the resource type is not user and the slot can not be assigned to the resource, do not copy not unassign it
                        continue
                    else:
                        # When the employee has no attendance at all, we are in the case where the employee has a calendar different than the
                        # company (or no more calendar), so the slot will be unassigned
                        unassigned_interval = attendance_interval_company - unavailable_interval_company
                        split_slot_values = slot._get_split_slot_values(values, unassigned_interval, remaining_hours_to_plan, unassign=True)
                    # merge forecast slots in order to have visually bigger slots
                    new_slot_values += self._merge_slots_values(split_slot_values, unassigned_interval)
        return new_slot_values

    def _display_name_fields(self):
        """ List of fields that can be displayed in the display_name """
        return ['role_id']

    def _get_fields_breaking_publication(self):
        """ Fields list triggering the `publication_warning` to True when updating shifts """
        return [
            'employee_ids',
            'start_datetime',
            'end_datetime',
            'role_id',
        ]

    @api.model
    def _get_template_fields(self):
        # key -> field from template
        # value -> field from slot
        return {
            'role_id': 'role_id',
            'start_time': 'start_datetime',
            'end_time': 'end_datetime',
            'duration_days': 'working_days_count',
            'company_id': 'company_id',
        }

    def _get_tz(self):
        return (self.env.user.tz
                or self.employee_ids[:1].tz
                or self.resource_ids[:1].tz
                or self.env.context.get('tz')
                or self.company_id.tz
                or 'UTC')

    def _prepare_template_values(self):
        """ extract values from shift to create a template """
        # compute duration w/ tzinfo otherwise DST will not be taken into account
        destination_tz = ZoneInfo(self._get_tz())
        start_datetime = self.start_datetime.replace(tzinfo=UTC).astimezone(destination_tz)
        end_datetime = self.end_datetime.replace(tzinfo=UTC).astimezone(destination_tz)

        # get days span from slot
        duration_days = days_span(start_datetime, end_datetime)

        return {
            'start_time': start_datetime.hour + start_datetime.minute / 60.0,
            'end_time': end_datetime.hour + end_datetime.minute / 60.0,
            'duration_days': duration_days,
            'role_id': self.role_id.id
        }

    def _manage_archived_resources(self, archived_resources, departure_date):
        shift_vals_list = []
        shift_ids_to_remove_resource = []
        for slot in self:
            split_time = departure_date.replace(tzinfo=ZoneInfo(self._get_tz())).astimezone(UTC).replace(tzinfo=None)
            if (slot.start_datetime < split_time) and (slot.end_datetime > split_time):
                shift_vals_list.append({
                    'start_datetime': split_time,
                    **slot._prepare_shift_vals(),
                })
                if split_time > slot.start_datetime:
                    slot.write({'end_datetime': split_time})
            elif slot.start_datetime >= split_time:
                shift_ids_to_remove_resource.append(slot.id)
        if shift_vals_list:
            self.sudo().create(shift_vals_list)
        if shift_ids_to_remove_resource:
            self.sudo().browse(shift_ids_to_remove_resource).write({'resource_ids': [Command.unlink(r.id) for r in archived_resources]})

    def _group_expand_resource_ids(self, resources, domain):
        dom_tuples = [(dom[0], dom[1]) for dom in domain if isinstance(dom, (tuple, list)) and len(dom) == 3]
        resource_ids = self.env.context.get('filter_resource_ids', False)
        if resource_ids:
            return self.env['resource.resource'].search([('id', 'in', resource_ids)])
        if self.env.context.get('planning_expand_resource') and ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            # Search on the roles and resources
            search_on_role_domain = Domain.TRUE
            search_on_ressource_domain = Domain.TRUE
            search_on_department_domain = Domain.TRUE
            if ('role_id', '=') in dom_tuples or ('role_id', 'ilike') in dom_tuples or ('role_id', 'in') in dom_tuples:
                role_search_domain = Domain(self._expand_domain_m2o_groupby(domain, 'role_id'))
                role_ids = self.env["planning.role"].search(role_search_domain).ids
                search_on_role_domain = Domain('role_ids', 'in', role_ids)
            if ('resource_ids', '=') in dom_tuples or ('resource_ids', 'ilike') in dom_tuples or ('resource_ids', 'in') in dom_tuples:
                domain = Domain(domain)

                def _map_condition(cond):
                    if cond.field_expr == 'resource_ids':
                        return Domain('name' if 'like' in cond.operator else 'id', cond.operator, cond.value)
                    elif cond.field_expr == 'user_ids':
                        return Domain('user_id', cond.operator, cond.value)
                    return None

                search_on_ressource_domain = filter_map_domain(domain, _map_condition)
            if ('department_id', '=') in dom_tuples or ('department_id', 'ilike') in dom_tuples or ('department_id', 'in') in dom_tuples:
                department_search_domain = Domain(self._expand_domain_m2o_groupby(domain, 'department_id'))
                department_ids = self.env["hr.department"].search(department_search_domain).ids
                search_on_department_domain = Domain('employee_id.department_id', 'in', department_ids)
                if ('id', '=', False) in search_on_ressource_domain and len(list(search_on_ressource_domain)) == 1:
                    search_on_ressource_domain = Domain.TRUE
            # Search on the slots
            filters = self._expand_domain_dates(domain)
            resources = self.env['planning.slot'].search(filters).mapped('resource_ids')
            search_on_expanded_dates = Domain('id', 'in', resources.ids)
            # Merge the search domains
            if search_on_role_domain or search_on_department_domain or search_on_ressource_domain:
                search_domain = Domain.AND([search_on_role_domain, search_on_department_domain, search_on_ressource_domain])
                return self.env["resource.resource"].search(search_domain | search_on_expanded_dates)
            return self.env["resource.resource"].search(search_on_expanded_dates)
        return resources

    def _read_group_role_id(self, roles, domain):
        dom_tuples = [(dom[0], dom[1]) for dom in domain if isinstance(dom, list) and len(dom) == 3]
        if self.env.context.get('planning_expand_role') and ('start_datetime', '<') in dom_tuples and ('end_datetime', '>') in dom_tuples:
            if ('role_id', '=') in dom_tuples or ('role_id', 'ilike') in dom_tuples:
                filter_domain = self._expand_domain_m2o_groupby(domain, 'role_id')
                return self.env['planning.role'].search(filter_domain)
            filters = Domain.AND([[('role_id.active', '=', True)], self._expand_domain_dates(domain)])
            return self.env['planning.slot'].search(filters).mapped('role_id')
        return roles

    @api.model
    def _expand_domain_m2o_groupby(self, domain, filter_field=False):
        filter_domains = []
        for dom in domain:
            if dom[0] == filter_field:
                field = self._fields[dom[0]]
                if field.type == 'many2one' and len(dom) == 3:
                    if dom[1] in ['=', 'in']:
                        filter_domains.append([('id', dom[1], dom[2])])
                    elif dom[1] == 'ilike':
                        rec_name = self.env[field.comodel_name]._rec_name
                        filter_domains.append([(rec_name, dom[1], dom[2])])
        return Domain.OR(filter_domains) if filter_domains else Domain.TRUE

    def _expand_domain_dates(self, domain):
        delta = get_timedelta(1, self.env.context.get("scale", "week"))

        def update_start_end_dates(cond):
            if cond.field_expr == 'start_datetime' and cond.operator[0] == '<':
                value = cond.value or datetime.now()
                value += delta
            elif cond.field_expr == 'end_datetime' and cond.operator[0] == '>':
                value = cond.value or datetime.now()
                value -= delta
            else:
                return cond
            return Domain(cond.field_expr, cond.operator, value)

        return Domain(domain).optimize_full(self).map_conditions(update_start_end_dates)

    @api.model
    def _format_datetime_to_user_tz(self, datetime_without_tz, record_env, tz=None, lang_code=False):
        return format_datetime(record_env, datetime_without_tz, tz=tz, dt_format='short', lang_code=lang_code)

    @api.model
    def _generate_planning_report_pdf(self, start_datetime, end_datetime, slot_ids):
        ActionsReport = self.env['ir.actions.report']
        if ActionsReport.get_pdf_engine_state(
            ActionsReport._get_pdf_engine()
        ) == 'install':
            return False
        slot_report_data = self.env["planning.slot"].action_print_plannings(
            fields.Datetime.to_string(start_datetime),
            fields.Datetime.to_string(end_datetime),
            ["resource_ids"],
            [("id", "in", slot_ids)],
        )
        report_data = slot_report_data.get('data', {})
        emp_data = report_data.get('group_by_name_by_id', {})
        grouped_slots = slot_report_data['data']['group_by_slots_per_day_per_week']
        pdf_content, _ = ActionsReport.with_context(
            discard_logo_check=True,
            allow_printing_planning_report=True,
        )._render_qweb_pdf(
            'planning.report_planning_slot',
            slot_ids,
            data={
                'weeks': report_data.get('weeks', []),
                'group_by_slots_per_day_per_week': json.loads(json.dumps(grouped_slots)),
                'group_by_name_by_id': json.loads(json.dumps(emp_data)),
            },
        )
        return pdf_content

    def _send_slot(self, employees, start_datetime, end_datetime, include_unassigned=True, message=None):
        if not include_unassigned:
            self = self.filtered('resource_ids')  # noqa: PLW0642
        if not self:
            return False
        self.ensure_one()

        employee_with_backend = employees.filtered(lambda e: e.user_id)
        template = self.env.ref('planning.email_template_slot_single')
        employee_url_map = employee_with_backend._planning_get_url(start_datetime.date(), end_datetime.date())

        cal_url = self._get_slot_resource_urls()
        view_context = dict(self.env.context)
        view_context.update({
            'open_shift_available': not self.resource_ids,
            'mail_subject': self.env._('Planning: new open shift available on'),
            'google_url': cal_url['google_url'],
            'iCal_url': cal_url['iCal'],
        })

        email_values = {}
        pdf_content = self._generate_planning_report_pdf(self.start_datetime, self.end_datetime, self.ids)
        if pdf_content:
            attachment = self.env['ir.attachment'].create({
                'name': self.env._("Planning Report.pdf"),
                'type': 'binary',
                'raw': pdf_content,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            email_values['attachment_ids'] = [Command.link(attachment.id)]

        if self.employee_ids:
            employees = self.employee_ids
            view_context.update({'mail_subject': self.env._('Planning: new shift on')})

        mails_to_send_ids = []

        unassign_button = self.employee_ids and self.allow_self_unassign and not self.is_unassign_deadline_passed
        for employee in employees:
            if not employee.work_email:
                continue
            if unassign_button:
                if employee_url_map.get(employee.id):
                    view_context.update({'unavailable_link':
                        '/planning/unassign/%s/%s' % (employee.sudo().employee_token, self.id),
                    })
                else:
                    view_context['unavailable_link'] = False
            if not self.employee_ids and employee in employee_with_backend and not self.is_past:
                view_context.update({'available_link': '/planning/assign/%s/%s' % (employee.sudo().employee_token, self.id)})
            else:
                view_context['available_link'] = False
            start_datetime = self._format_datetime_to_user_tz(self.start_datetime, employee.env, tz=employee.tz, lang_code=employee.user_partner_id.lang)
            end_datetime = self._format_datetime_to_user_tz(self.end_datetime, employee.env, tz=employee.tz, lang_code=employee.user_partner_id.lang)
            unassign_deadline = self._format_datetime_to_user_tz(self.unassign_deadline, employee.env, tz=employee.tz, lang_code=employee.user_partner_id.lang)
            allocated_hours = timedelta(hours=self.allocated_hours).total_seconds()
            formatted_allocated_hours = "%d:%02d" % (allocated_hours // 3600, round(allocated_hours % 3600 / 60))
            allocated_percentage = float_utils.float_repr(self.allocated_percentage, precision_digits=0)
            lang = employee.user_partner_id.lang or employee.work_contact_id.lang or self.env.context.get('lang')
            # update context to build a link for view in the slot
            view_context.update({
                'is_internal_user': employee.user_id and not employee.user_id.share,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'employee_name': employee.name,
                'work_email': employee.work_email,
                'allocated_hours': formatted_allocated_hours,
                'allocated_percentage': allocated_percentage,
                'unassign_deadline': unassign_deadline,
                'lang': lang,
            })
            mail_id = template.with_context(view_context).send_mail(
                self.id,
                email_layout_xmlid='mail.mail_notification_light',
                email_values=email_values,
            )
            mails_to_send_ids.append(mail_id)

        mails_to_send = self.env['mail.mail'].sudo().browse(mails_to_send_ids)
        if mails_to_send:
            mails_to_send.send()

        vals = {
            'publication_warning': False,
        }
        if self.state == '1_draft':
            vals['state'] = '2_published'
        self.write(vals)
        return None

    def _send_shift_assigned(self, human_resources):
        email_from = self.company_id.email or ''

        template = self.env.ref('planning.email_template_shift_switch_email', raise_if_not_found=False)
        for resource in self.resource_ids:
            if not (resource.resource_type == 'user' and resource.employee_id and resource not in human_resources):
                continue
            assignee = resource.employee_id
            start_datetime = self._format_datetime_to_user_tz(self.start_datetime, assignee.env, tz=assignee.tz, lang_code=assignee.user_partner_id.lang)
            end_datetime = self._format_datetime_to_user_tz(self.end_datetime, assignee.env, tz=assignee.tz, lang_code=assignee.user_partner_id.lang)
            allocated_hours = float_utils.float_repr(self.allocated_hours, precision_digits=2)
            allocated_percentage = float_utils.float_repr(self.allocated_percentage, precision_digits=0)
            template_context = {
                'old_assignee_name': assignee.name,
                'new_assignee_names': format_list(self.env, human_resources.employee_id.mapped('name')),
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'allocated_hours': allocated_hours,
                'allocated_percentage': allocated_percentage,
            }
            if template:
                template.with_context(**template_context).send_mail(
                    self.id,
                    email_values={
                        'email_to': assignee.work_email,
                        'email_from': email_from,
                    },
                    email_layout_xmlid='mail.mail_notification_light',
                )

    # ---------------------------------------------------
    # Slots generation/copy
    # ---------------------------------------------------

    @api.model
    def _merge_slots_values(self, slots_to_merge, unforecastable_intervals):
        """
        Return a list of merged slots.

        :param list slots_to_merge: Sorted list of slots to merge.
        :param Intervals unforecastable_intervals: Intervals where the employee cannot work.
        :returns: List of merged slots.
        :rtype: list[dict]

        Example::

            slots_to_merge = [{
                'start_datetime': '2021-08-01 08:00:00',
                'end_datetime': '2021-08-01 12:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }, {
                'start_datetime': '2021-08-01 13:00:00',
                'end_datetime': '2021-08-01 17:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }, {
                'start_datetime': '2021-08-02 08:00:00',
                'end_datetime': '2021-08-02 12:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }, {
                'start_datetime': '2021-08-03 08:00:00',
                'end_datetime': '2021-08-03 12:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }, {
                'start_datetime': '2021-08-04 13:00:00',
                'end_datetime': '2021-08-04 17:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }]

            unforecastable = Intervals([(
                datetime.datetime(2021, 8, 2, 13, 0, 0, tzinfo='UTC'),
                datetime.datetime(2021, 8, 2, 17, 0, 0, tzinfo='UTC'),
                self.env['resource.calendar.attendance'],
            )])

            result = [{
                'start_datetime': '2021-08-01 08:00:00',
                'end_datetime': '2021-08-02 12:00:00',
                'employee_id': 1,
                'allocated_hours': 12.0,
            }, {
                'start_datetime': '2021-08-03 08:00:00',
                'end_datetime': '2021-08-03 12:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }, {
                'start_datetime': '2021-08-04 13:00:00',
                'end_datetime': '2021-08-04 17:00:00',
                'employee_id': 1,
                'allocated_hours': 4.0,
            }]
        """
        if not slots_to_merge:
            return slots_to_merge
        # resulting vals_list of the merged slots
        new_slots_vals_list = []
        # accumulator for mergeable slots
        sum_allocated_hours = 0
        to_merge = None
        # invariants for mergeable slots
        common_allocated_percentage = slots_to_merge[0]['allocated_percentage']
        resource_ids = slots_to_merge[0].get('resource_ids')
        start_datetime = slots_to_merge[0]['start_datetime']
        previous_end_datetime = start_datetime
        for slot in slots_to_merge:
            mergeable = True
            if (not slot['start_datetime']
               or common_allocated_percentage != slot['allocated_percentage']
               or resource_ids != slot['resource_ids']
               or (slot['start_datetime'] - previous_end_datetime).total_seconds() > 3600 * 24):
                # last condition means the elapsed time between the previous end time and the
                # start datetime of the current slot should not be bigger than 24hours
                # if it's the case, then the slot can not be merged.
                mergeable = False
            if mergeable:
                end_datetime = slot['end_datetime']
                interval = Intervals([(
                    start_datetime.replace(tzinfo=UTC),
                    end_datetime.replace(tzinfo=UTC),
                    self.env['resource.calendar.attendance']
                )])
                if not (interval & unforecastable_intervals):
                    sum_allocated_hours += slot['allocated_hours']
                    to_merge = {
                        **slot,
                        'start_datetime': start_datetime,
                        'allocated_hours': sum_allocated_hours,
                    }
                else:
                    mergeable = False
            if not mergeable:
                if to_merge:
                    new_slots_vals_list.append(to_merge)
                to_merge = slot
                start_datetime = slot['start_datetime']
                common_allocated_percentage = slot['allocated_percentage']
                resource_ids = slot.get('resource_ids')
                sum_allocated_hours = slot['allocated_hours']
            previous_end_datetime = slot['end_datetime']
        if to_merge:
            new_slots_vals_list.append(to_merge)
        return new_slots_vals_list

    def _get_working_hours_over_period(self, start_utc, end_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day=None, flexible_resources_hours_per_week=None):
        """
        Compute the total work hours of the slot based on its work intervals or its working calendar.

        The following are the different cases:

        1. If the assigned resource has a flexible contract, its working hours is computed via ``_get_flexible_resource_work_hours``
           that takes into account contract, timeoff, max hours per day and per week
        2. If the slot is an open shift, take the ``hours_per_day`` of the company's calendar to calculate the working hours.
           This allows the creation of open slots outside the company's calendar attendance (such as weekends).
        3. If the resource is assigned and has fixed working hours, compute the work hours based on its work intervals.

        :return: The total number of working hours for the slot.
        :rtype: float
        """
        start = max(start_utc, self.start_datetime.replace(tzinfo=UTC))
        end = min(end_utc, self.end_datetime.replace(tzinfo=UTC))
        slot_interval = Intervals([(
            start, end, self.env['resource.calendar.attendance']
        )])
        period = self.end_datetime - self.start_datetime
        slot_duration = period.total_seconds() / 3600
        # For open shift, take the `hours_per_day` of the company's default calendar
        if not self.resource_ids:
            if self.allocation_type == 'forecast':
                max_hours_per_day = self.company_id.resource_calendar_id.hours_per_day
                max_duration = (period.days + (1 if period.seconds else 0)) * max_hours_per_day
                return round(min(slot_duration, max_duration), 2)
            else:
                working_intervals = calendar_intervals.get(self.company_id.resource_calendar_id.id, Intervals())
                return round(sum_intervals(slot_interval & working_intervals), 2)

        return sum(self._get_working_hours_over_period_per_resource(
            start_utc, end_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week,
        ).values())

    def _get_working_hours_over_period_per_resource(self, start_utc, end_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day=None, flexible_resources_hours_per_week=None):
        """
        Calculates the working hours per resource.

        For flexible resources, call ``_get_flexible_resource_work_hours`` to do the compute.
        Otherwise, compute the work hours based on its work intervals.

        :return: dict mapping resource.id -> working hours (float)
        :rtype: dict
        """
        if not self.resource_ids:
            return {}
        start = max(start_utc, self.start_datetime.replace(tzinfo=UTC))
        end = min(end_utc, self.end_datetime.replace(tzinfo=UTC))
        slot_interval = Intervals([(
            start, end, self.env['resource.calendar.attendance']
        )])

        flexible_resources = self.resource_ids.filtered(lambda r: r._is_flexible())
        remaining_resources = self.resource_ids - flexible_resources
        if self.employee_ids:
            flexible_resources = flexible_resources.filtered(lambda r: r.resource_type == 'user')
            remaining_resources = remaining_resources.filtered(lambda r: r.resource_type == 'user')

        hours_per_resource = {}
        if flexible_resources:
            assert flexible_resources_hours_per_day is not None and flexible_resources_hours_per_week is not None
            for r in flexible_resources:
                hours_per_resource[r.id] = r._get_flexible_resource_work_hours(
                    slot_interval & work_intervals[r.id], flexible_resources_hours_per_day.get(r.id, 0.0), flexible_resources_hours_per_week.get(r.id, 0.0))

        for resource in remaining_resources:
            # Resource with fixed working hours, else we refer to the company's calendar
            working_intervals = work_intervals[resource.id]
            hours_per_resource[resource.id] = round(sum_intervals(slot_interval & working_intervals), 2)

        return hours_per_resource

    def _get_duration_over_period_per_resource(self, start_utc, stop_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week, has_allocated_hours=True):
        """
        The total duration, possibly manually overridden by the user is kept as the reference and
        redistributed between resources proportionally to their own working hours over the period,
        so that resources with different calendars each get their actual share.

        :return: dict mapping resource.id -> duration (float)
        :rtype: dict
        """
        self.ensure_one()
        working_hours_per_resource = self._get_working_hours_over_period_per_resource(
            start_utc, stop_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week,
        )
        if not working_hours_per_resource:
            return {}
        total_duration = self._get_duration_over_period(
            start_utc, stop_utc, work_intervals, calendar_intervals,
            flexible_resources_hours_per_day, flexible_resources_hours_per_week, has_allocated_hours,
        )
        total_working_hours = sum(working_hours_per_resource.values())
        if not total_working_hours:
            # None of the resources have working hours over the period: split evenly.
            return dict.fromkeys(working_hours_per_resource, total_duration / len(working_hours_per_resource))
        return {
            resource_id: total_duration * hours / total_working_hours
            for resource_id, hours in working_hours_per_resource.items()
        }

    def _get_slot_resource_urls(self):
        def get_url_dt(dt):
            return dt.astimezone(ZoneInfo(self._get_tz())).strftime('%Y%m%dT%H%M%S')
        ics_description_data = {
            'shift': self._get_ics_description_data(),
            'is_google_url': True,
        }
        return {
            'google_url': "https://www.google.com/calendar/render?" + url_encode({
                'action': 'TEMPLATE',
                'text': self.display_name or self.env._('New Shift'),  # Event title
                'dates': f'{get_url_dt(self.start_datetime)}/{get_url_dt(self.end_datetime)}',  # Event start and end date/time
                'ctz': self._get_tz(),
                'details': self.env['ir.qweb']._render('planning.planning_shift_ics_description', ics_description_data),
            }),
            'iCal': f'/slot/{self.access_token}.ics',
        }

    def _get_duration_over_period(self, start_utc, stop_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week, has_allocated_hours=True):
        assert start_utc.tzinfo and stop_utc.tzinfo
        self.ensure_one()
        start, stop = start_utc.replace(tzinfo=None), stop_utc.replace(tzinfo=None)
        if has_allocated_hours and self.start_datetime >= start and self.end_datetime <= stop:
            return self.allocated_hours
        # if the slot goes over the gantt period, compute the duration only within the gantt period
        ratio = self.allocated_percentage / 100.0
        working_hours = self._get_working_hours_over_period(start_utc, stop_utc, work_intervals, calendar_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week)
        return working_hours * ratio

    def _get_employee_work_hours_within_interval(self, resource, work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week):
        """
        Compute the total work hours of an employee based on either work intervals
        or flexible calendar hours.
        :param Intervals work_intervals: The work intervals of the employee
        :return: the number of work hours
        :rtype: float

        This covers 2 use cases:

        1. If the employee has a flexible contract, their working hours are computed via
           ``_get_flexible_resource_work_hours`` that takes into account contract, timeoff, max hours per day
           and per week.
        2. If the employee has fixed working hours, we compute the work hours based on their work intervals.
        """
        if resource._is_flexible():
            return resource._get_flexible_resource_work_hours(work_intervals, flexible_resources_hours_per_day[resource.id], flexible_resources_hours_per_week[resource.id])

        return sum_intervals(work_intervals)

    def _gantt_progress_bar_group_by_field(self, res_ids, start, stop, group_by_field):
        start_naive, stop_naive = start.replace(tzinfo=None), stop.replace(tzinfo=None)

        model = {
            "resource_ids": "resource.resource",
            "role_id": "planning.role",
            "department_id": "hr.department",
        }
        resource_field = {
            "role_id": "role_ids",
            "department_id": "department_id",
        }
        resource_db_field = {
            "role_id": "role_ids",
            "department_id": "employee_id.department_id",
        }

        records = self.env[model[group_by_field]].with_context(active_test=False).search([('id', 'in', res_ids)])
        planning_slots = self.env['planning.slot'].search([
            (group_by_field, 'in', res_ids),
            ('start_datetime', '<=', stop_naive),
            ('end_datetime', '>=', start_naive),
        ])

        if group_by_field == "resource_ids":
            resources = records
        else:
            # retrieve all resources even if they are not displayed
            # don't use planning_slots.resource_id because the user doing the slot should have the role/department to be computed
            resources = self.env['resource.resource'].search([
                (resource_db_field[group_by_field], 'in', res_ids),
            ])

        flexible_resources = resources.filtered(lambda r: r._is_flexible())
        regular_resources = resources - flexible_resources

        planned_hours_mapped = defaultdict(float)
        resource_work_intervals, calendar_work_intervals = regular_resources.sudo()._get_valid_work_intervals(start, stop)

        flexible_resource_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week = flexible_resources._get_flexible_resource_valid_work_intervals(start, stop)
        resource_work_intervals.update(flexible_resource_work_intervals)

        for slot in planning_slots:
            if group_by_field == 'resource_ids' and slot.resource_ids:
                duration_per_resource = slot._get_duration_over_period_per_resource(
                    start, stop, resource_work_intervals, calendar_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week
                )
                for resource in slot.resource_ids:
                    planned_hours_mapped[resource.id] += duration_per_resource.get(resource.id, 0.0)
                continue
            duration = slot._get_duration_over_period(
                start, stop, resource_work_intervals, calendar_work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week
            )
            group_records = slot[group_by_field]
            if group_records:
                for group in group_records:
                    planned_hours_mapped[group.id] += duration
            else:
                planned_hours_mapped[False] += duration

        # Compute employee work hours based on its work intervals.
        work_hours = defaultdict(int)
        groups_linked_to_only_fully_flexible_resources = defaultdict(lambda: True)
        for resource in resources:
            if resource.id not in resource_work_intervals:
                continue

            work_intervals = resource_work_intervals[resource.id]
            work_duration = self._get_employee_work_hours_within_interval(resource, work_intervals, flexible_resources_hours_per_day, flexible_resources_hours_per_week)
            if group_by_field == "resource_ids":
                work_hours[resource.id] = work_duration
                groups_linked_to_only_fully_flexible_resources[resource.id] = resource._is_fully_flexible()
            else:
                for field in resource[resource_field[group_by_field]]:
                    work_hours[field.id] += work_duration
                    if resource._is_fully_flexible():
                        continue

                    groups_linked_to_only_fully_flexible_resources[field.id] = False

        res = {}
        for record in records:
            res[record.id] = {
                'value': planned_hours_mapped[record.id],
                'max_value': work_hours.get(record.id, 0.0),
                'all_group_by_resources_fully_flexible': groups_linked_to_only_fully_flexible_resources.get(record.id, False)
            }
            if group_by_field == 'resource_ids':
                res[record.id].update({
                    'is_material_resource': record.resource_type == 'material',
                    'resource_color': record.color,
                    'display_popover_material_resource': len(record.role_ids) > 1,
                    'employee_id': record.sudo().employee_id.id,
                    'is_flexible_hours': record._is_flexible(),
                    'is_fully_flexible_hours': record._is_fully_flexible(),
                })

        return res

    def _gantt_progress_bar(self, field, res_ids, start, stop):
        if not self.env.user._is_internal():
            return {}

        if field not in ['resource_ids', 'role_id', 'department_id']:
            raise NotImplementedError(self.env._("This Progress Bar is not implemented."))

        start, stop = start.replace(tzinfo=UTC), stop.replace(tzinfo=UTC)
        res = self._gantt_progress_bar_group_by_field(res_ids, start, stop, field)

        if field == 'resource_id':
            res["warning"] = self.env._("This employee is not expected to work during this period, either because they do not have a current contract or because they are on leave.")

        return res

    def _prepare_shift_vals(self):
        """ Generate shift vals"""
        self.ensure_one()
        return {
            'resource_ids': False,
            'end_datetime': self.end_datetime,
            'role_id': self.role_id.id,
            'company_id': self.company_id.id,
            'allocated_percentage': self.allocated_percentage,
            'name': self.name,
            'recurrency_id': self.recurrency_id.id,
            'repeat': self.repeat,
            'repeat_interval': self.repeat_interval,
            'repeat_unit': self.repeat_unit,
            'repeat_type': self.repeat_type,
            'repeat_until': self.repeat_until,
            'repeat_number': self.repeat_number,
            'template_id': self.template_id.id,
        }

    def undo_split_shift(self, start_datetime, end_datetime, resource_ids):
        if len(self) != 2:
            raise ValueError(self.env._("This method must take two slots in argument."))
        initial_shift, copied_shift = self
        if not (initial_shift.exists() and copied_shift.exists()):
            return False
        initial_shift.start_datetime = start_datetime
        initial_shift.end_datetime = end_datetime
        initial_shift.resource_ids = resource_ids
        copied_shift.unlink()
        return True

    def _convert_resource_ids_vals(self, resource_ids):
        assert len(self) <= 1
        return self._fields['resource_ids'].convert_to_cache(resource_ids, self, validate=False)
