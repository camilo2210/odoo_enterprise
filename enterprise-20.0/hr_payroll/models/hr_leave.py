# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime, time

from odoo import _, api, fields, models, modules
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command, Domain
from odoo.tools import config
from odoo.tools.date_utils import localized
from odoo.tools.intervals import Intervals


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    payslip_state = fields.Selection([
        ('normal', 'To compute in next payslip'),
        ('done', 'Computed in current payslip'),
        ('blocked', 'Payslip to be corrected')], string='Payslip State',
        copy=False, default='normal', required=True)

    employee_registration_number = fields.Char(related="employee_id.registration_number")
    employee_type_id = fields.Many2one('hr.employee.type', compute='_compute_version_fields', store=True, groups="hr_payroll.group_hr_payroll_user")
    job_id = fields.Many2one('hr.job', compute='_compute_version_fields', store=True)
    structure_type_id = fields.Many2one('hr.payroll.structure.type', compute='_compute_version_fields', store=True, groups="hr_payroll.group_hr_payroll_user")
    payslip_count = fields.Integer("Payslip Count", compute='_compute_payslip_count', groups="hr_payroll.group_hr_payroll_user")
    category_options_ids = fields.Many2many('hr.salary.rule.category', string="Options", groups="hr_payroll.group_hr_payroll_user",
        domain="[('optional_on_work_entry_type_ids', 'in', work_entry_type_id)]")
    options_on_work_entry_type_ids = fields.Many2many(related='work_entry_type_id.optional_category_ids', groups="hr_payroll.group_hr_payroll_user")
    issues = fields.Json(compute='_compute_issues', store=True, readonly=True)

    @api.depends('employee_id', 'date_from')
    def _compute_version_fields(self):
        for leave in self:
            if not leave.date_from or not leave.employee_id:
                leave.employee_type_id = False
                leave.job_id = False
                leave.structure_type_id = False
                continue
            version = leave.employee_id._get_version(leave.date_from.date())
            leave.employee_type_id = version.employee_type_id
            leave.job_id = version.job_id
            leave.structure_type_id = version.structure_type_id

    def _has_blocking_payroll_warning(self):
        """Return True if any danger-level payroll warning applies to this leave."""
        self.ensure_one()
        warnings = self.env["hr.payroll.warning"].search([
            ("display_on_model", "=", True),
            ("model_name", "=", "hr.leave"),
            ("warning_color_class", "=", "danger"),
            ("active", "=", True),
        ])
        for warning in warnings:
            if warning.warning_type == 'domain':
                if self in warning._get_warning_domain_records(self.company_id, records_to_check=self):
                    return True
            else:
                related, _, _, _ = warning._get_warning_python_records(localdict={'active_ids': self.ids})
                if self in related:
                    return True
        return False

    def _process_auto_approve_activities(self):
        # Auto approve shouldn't be processed for non-officers when leave contains blocking warning
        self.ensure_one()
        is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user')

        if (self.validation_type == 'no_validation'
                and not is_officer
                and self.sudo()._has_blocking_payroll_warning()):
            holiday_sudo = self.sudo()
            holiday_sudo.add_follower(self.employee_id.id)
            hr_responsible = holiday_sudo.employee_id.hr_responsible_id
            if hr_responsible:
                holiday_sudo.activity_schedule('hr_holidays.mail_act_leave_approval', user_id=hr_responsible.id)
            return

        return super()._process_auto_approve_activities()

    @api.model
    def _issues_dependencies(self):
        # To be implemented after introducing generic issues on hr.leave
        return ['payslip_state']

    @api.depends(lambda self: self._issues_dependencies())
    def _compute_issues(self):
        self.issues = {}
        if (
            not self.env.registry.ready
            and not (config["test_enable"] or modules.module.current_test)
            # This context key acts as an escape hatch for upgrade scripts that need to
            # explicitly recompute payroll issues while the registry is still initializing.
            and not (self.env.context.get("hr_payroll_force_compute_issue"))
        ):
            return
        warnings = self.env["hr.payroll.warning"].search([
            ("display_on_model", "=", True),
            ("model_name", "=", "hr.leave"),
            ("active", "=", True),
        ])
        if not warnings:
            return
        for warning in warnings:
            if warning.warning_type == 'domain':
                related_leaves = warning._get_warning_domain_records(self.company_id)
                for leave in self:
                    issues = leave.issues or {}
                    if leave in related_leaves:
                        issues[len(issues)] = warning._get_warning_issue()
                    leave.issues = issues
            else:
                related_leaves, warning_details, _, _ = warning._get_warning_python_records(localdict={'active_ids': self.ids})
                for leave in self:
                    issues = leave.issues or {}
                    if leave in related_leaves:
                        if warning_details:
                            for detail in warning_details.get(leave, []):
                                issues[len(issues)] = detail
                        else:
                            issues[len(issues)] = warning._get_warning_issue()
                    leave.issues = issues

    @api.model
    def _gantt_availability(self, field, res_ids, start, stop, scale):
        """
            return {
                value: [
                    {
                        'date': date,
                        'hours': hours,
                        'full_cell': full_cell,
                    },
                    ...
                ]
            }
        """
        if field != "employee_id":
            return None
        start_date = fields.Datetime.to_string(start)
        stop_date = fields.Datetime.to_string(stop)
        employees = self.env['hr.employee'].browse(res_ids)
        work_mapping = defaultdict(Intervals)
        employee_versions = self.env['hr.version'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('contract_date_start', '!=', False),
            ('contract_date_start', '<=', stop_date),
            '|',
            ('contract_date_end', '=', False),
            ('contract_date_end', '>=', start_date),
        ])

        employee_with_contracts = employee_versions.employee_id
        employees_without_contracts = employees - employee_with_contracts

        # For employees without contracts
        work_mapping.update(
            employees_without_contracts.resource_id._get_valid_work_intervals(localized(start), localized(stop))[0])

        # For employees with contracts
        for calendar, versions in employee_versions.grouped('resource_calendar_id').items():
            if calendar._is_flexible():
                continue
            ends = versions.mapped('date_end')
            group_date_from = max(start, datetime.combine(min(versions.mapped('date_start')), time.min))
            group_date_to = min(stop, datetime.combine(max(ends), time.max)) if all(ends) else stop
            resources_work_intervals = calendar._work_intervals_batch(
                localized(group_date_from),
                localized(group_date_to),
                versions._get_resources_per_tz(),
            )
            for version in versions:
                # the versions share a calendar, not their dates: each covers its own days
                date_from = max(start, datetime.combine(version.date_start, time.min))
                date_to = min(stop, datetime.combine(version.date_end, time.max)) if version.date_end else stop
                version_interval = Intervals([
                    (localized(date_from), localized(date_to), self.env['resource.calendar'])])
                resource = version.employee_id.resource_id
                work_mapping[resource.id] |= resources_work_intervals[resource.id] & version_interval

        result = {}
        for employee in employees:
            intervals = work_mapping.get(employee.resource_id.id, [])
            result[employee.id] = [{'date': interval[0], 'hours': (interval[1] - interval[0]).total_seconds() / 3600} for interval in intervals]

        return result

    @api.model
    def get_gantt_data(self, domain, groupby,
        read_specification, limit=None, offset=0, unavailability_fields=None,
        progress_bar_fields=None, start_date=None, stop_date=None, scale=None,
    ):
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

        # we need to add new key ['availabilities'] to the gantt data which store
        # for each employee each day how many hours should this employee work
        # and if this should take whole cell (not half day leave) or only half cell
        res_ids_for_availabilities = defaultdict(set)
        field = 'employee_id'
        for group in gantt_data['groups']:
            res_id = group[field][0] if group[field] else False
            if res_id:
                res_ids_for_availabilities[field].add(res_id)
        if not res_ids_for_availabilities[field]:
            return gantt_data
        start, stop = fields.Datetime.from_string(start_date), fields.Datetime.from_string(stop_date)
        availabilities = {}
        availabilities[field] = self._gantt_availability(field, list(res_ids_for_availabilities[field]), start, stop, scale)
        gantt_data['availabilities'] = availabilities

        return gantt_data

    def _plans_hours_on_the_clock(self, worked_hours):
        """ Extra hours are worked on top of the schedule, not inside it. """
        return (self.work_entry_type_id.is_extra_hours and self.work_entry_type_id.request_unit == 'hour') \
            or super()._plans_hours_on_the_clock(worked_hours)

    def _get_payslip_domain(self):
        self.ensure_one()
        return [
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '<=', self.request_date_to),
            ('date_to', '>=', self.request_date_from),
            ('state', 'not in', ['draft', 'cancel']),
            ('worked_days_line_ids.work_entry_type_id', '=', self.work_entry_type_id.id),
        ]

    @api.depends('state', 'employee_id', 'department_id')
    def _compute_can_back_to_approve(self):
        super()._compute_can_back_to_approve()
        leaves_in_payslip = self._check_leave_in_payslip()
        for holiday in self:
            holiday.can_back_to_approve = holiday.can_back_to_approve and leaves_in_payslip[holiday]

    @api.depends('employee_id', 'request_date_from', 'request_date_to', 'work_entry_type_id')
    def _compute_payslip_count(self):
        for leave in self:
            if not (leave.employee_id and leave.request_date_from and leave.request_date_to):
                leave.payslip_count = 0
            else:
                leave.payslip_count = self.env['hr.payslip'].search_count(leave._get_payslip_domain())

    def _action_validate(self, check_state=True):
        def _overlaps(payslip, leave):
            """Check if a payslip overlaps with a leave."""
            return (
                payslip.date_from <= leave.date_to.date()
                and payslip.date_to >= leave.date_from.date()
            )

        # Get employees payslips
        all_payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', 'in', self.mapped('employee_id').ids),
        ]).filtered(lambda p: p.is_regular)
        done_payslips = all_payslips.filtered(lambda p: p.state in ['validated', 'paid'])
        waiting_payslips = all_payslips - done_payslips

        # Group payslips by employee
        done_by_employee = done_payslips.grouped('employee_id')
        waiting_by_employee = waiting_payslips.grouped('employee_id')

        # Mark Leaves to Defer
        for leave in self:
            done_for_emp = done_by_employee.get(leave.employee_id, [])
            waiting_for_emp = waiting_by_employee.get(leave.employee_id, [])

            overlaps_with_done_payslip = any(_overlaps(p, leave) for p in done_for_emp)
            overlaps_with_waiting_payslip = any(_overlaps(p, leave) for p in waiting_for_emp)

            if overlaps_with_done_payslip and not overlaps_with_waiting_payslip:
                leave.payslip_state = 'blocked'

        res = super()._action_validate(check_state=check_state)
        self.sudo()._recompute_payslips()
        return res

    def action_adjust_corresponding_payslip(self):
        payslips = self.env["hr.payslip"]
        for leave in self:
            matching_payslip = self.env["hr.payslip"].search([
                ('employee_id', '=', leave.employee_id.id),
                ('struct_type_id', '=', leave.structure_type_id.id),
                ('state', 'in', ['validated', 'paid']),
                ('date_from', '<=', leave.date_to.date()),
                ('date_to', '>=', leave.date_from.date()),
            ], order="id desc", limit=1)
            payslips |= matching_payslip
        if not payslips:
            return False
        return payslips.action_adjust_payslip()

    def _get_to_clean_activities(self):
        activities = super()._get_to_clean_activities()
        activities.append('hr_payroll.mail_activity_data_hr_leave_to_defer')
        return activities

    def action_refuse(self):
        res = super().action_refuse()
        self.sudo()._recompute_payslips()
        return res

    def _move_validate_leave_to_confirm(self):
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            raise AccessError(self.env._("Access allowed only for time-off officers."))

        res = super()._move_validate_leave_to_confirm()
        self.sudo()._recompute_payslips()
        self.sudo().write({'payslip_state': 'normal'})
        return res

    def _action_user_cancel(self, reason=None):
        res = super()._action_user_cancel(reason)
        self.sudo().payslip_state = 'done'
        self.sudo()._recompute_payslips()
        return res

    def _prepare_leave_unlink(self):
        super()._prepare_leave_unlink()
        self.sudo()._recompute_payslips()

    def _recompute_payslips(self):
        # Recompute draft/waiting payslips
        all_payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', 'in', self.mapped('employee_id').ids),
            ('state', '=', 'draft'),
        ]).filtered(lambda p: p.is_regular)
        draft_payslips = self.env['hr.payslip']
        waiting_payslips = self.env['hr.payslip']
        for leave in self:
            for payslip in all_payslips:
                if payslip.employee_id == leave.employee_id and (payslip.date_from <= leave.date_to.date() and payslip.date_to >= leave.date_from.date()):
                    if not payslip.line_ids:
                        draft_payslips |= payslip
                    else:
                        waiting_payslips |= payslip
        if draft_payslips:
            draft_payslips._compute_worked_days_line_ids()
        if waiting_payslips:
            waiting_payslips.action_refresh_from_work_entries()

    def activity_feedback(self, act_type_xmlids, user_id=None, feedback=None, attachment_ids=None, only_automated=True):
        if 'hr_payroll.mail_activity_data_hr_leave_to_defer' in act_type_xmlids:
            self.write({'payslip_state': 'done'})
        return super().activity_feedback(act_type_xmlids, user_id=user_id, feedback=feedback, attachment_ids=attachment_ids, only_automated=only_automated)

    def _check_leave_in_payslip(self):
        payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', 'in', self.employee_id.ids),
            ('date_from', '<=', max(self.mapped('date_to'))),
            ('date_to', '>=', min(self.mapped('date_from'))),
            ('state', 'in', ['validated', 'paid']),
        ])
        leaves_in_payslip = defaultdict(bool)
        for leave in self:
            if not any(
                    p.employee_id == leave.employee_id and
                    p.date_from <= leave.date_to.date() and
                    p.date_to >= leave.date_from.date() and
                    p.is_regular
                    for p in payslips
            ):
                leaves_in_payslip[leave] = True

        return leaves_in_payslip

    def _check_uncovered_by_validated_payslip(self):
        payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', 'in', self.employee_id.ids),
            ('date_from', '<=', max(self.mapped('date_to'))),
            ('date_to', '>=', min(self.mapped('date_from'))),
            ('state', 'in', ['validated', 'paid']),
        ])
        for leave in self:
            if any(
                    leave.state == 'validate' and
                    p.employee_id == leave.employee_id and
                    p.date_from <= leave.date_to.date() and
                    p.date_to >= leave.date_from.date() and
                    p.done_date > leave.create_date and
                    p.is_regular
                    for p in payslips
            ):
                raise UserError(_("The pay of the month is already validated with this day included. If you need to adapt, please refer to HR."))

    def write(self, vals):
        if vals.get('active') and self._check_uncovered_by_validated_payslip():
            self._check_uncovered_by_validated_payslip()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_payslip(self):
        self._check_uncovered_by_validated_payslip()

    def action_open_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': self._get_payslip_domain(),
        }

    def _prepare_resource_leave_vals(self):
        """
        Propagate category_options_ids to the underlying resource.calendar.leaves record when the leave is confirmed.
        """
        vals = super()._prepare_resource_leave_vals()
        if category_options_ids := self.sudo().category_options_ids:
            vals['category_options_ids'] = [(Command.set(category_options_ids.ids))]
        return vals

    @api.model
    def _gantt_progress_bar(self, field, res_ids, start, stop):
        """
        The number of hours displayed in the Gantt view of Time Off is based
        on the worked hours of the employee, but in the case of Belgium we also want
        to display the overtime hours in that counter
        """
        res = super()._gantt_progress_bar(field, res_ids, start, stop)

        work_entries = self.env['hr.work.entry.type']._search([
            ('category_ids', 'in', self.env.ref('hr_payroll.EXTRA_HOURS').id),
        ])

        aggregated_hours = self.env['hr.leave']._read_group(
            domain=Domain([
                ('employee_id', 'in', res_ids),
                ('state', '=', 'validate'),
                ('work_entry_type_id', 'in', work_entries),
                ('date_from', '<=', stop),
                ('date_to', '>=', start),
            ]),
            groupby=['employee_id'],
            aggregates=['number_of_hours:sum'],
        )

        for employee, hours in aggregated_hours:
            res[employee.id]['value'] += hours

        return res
