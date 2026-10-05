# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round

from datetime import timedelta
from markupsafe import Markup


class L10n_BeHrPayrollScheduleChangeWizard(models.TransientModel):
    _name = 'l10n_be.hr.payroll.schedule.change.wizard'
    _description = 'Change contract working schedule'

    version_id = fields.Many2one(
        'hr.version', string='Contract', readonly=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    company_id = fields.Many2one(related='version_id.company_id', readonly=True)
    employee_id = fields.Many2one(related='version_id.employee_id', readonly=True)
    structure_type_id = fields.Many2one(related='version_id.structure_type_id', readonly=True)
    date_start = fields.Date('Start Date', help='Start date of the new contract.', required=True)
    date_end = fields.Date('End Date', help='End date of the new contract.')
    work_time_rate = fields.Float(related='resource_calendar_id.work_time_rate', readonly=True)
    full_wage = fields.Monetary('Full Time Equivalent Wage', compute='_compute_wages', store=True, readonly=True)
    current_wage = fields.Monetary('Wage', compute='_compute_wages', store=True, readonly=True)
    wage = fields.Monetary(
        compute='_compute_wages', store=True, readonly=False,
        string='New Wage', required=True,
        help="Employee's monthly gross wage for the new contract.")
    currency_id = fields.Many2one(string="Currency", related='company_id.currency_id', readonly=True)

    full_resource_calendar_id = fields.Many2one(
        'resource.calendar', 'Working Hours Reference',
        compute='_compute_full_resource_calendar_id',
        store=True,
        readonly=False)
    current_resource_calendar_id = fields.Many2one(
        'resource.calendar',
        'Current Working Schedule',
        related='version_id.resource_calendar_id')
    resource_calendar_id = fields.Many2one(
        'resource.calendar', 'New Working Schedule', required=True,
        default=lambda self: self.env.company.resource_calendar_id.id,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    reorganisation_measure_ids = fields.Many2many(related="resource_calendar_id.l10n_be_reorganisation_measure_ids")
    full_time_off_allocation = fields.Float(compute='_compute_full_time_off_allocation', readonly=True)
    time_off_allocation = fields.Float(
        compute='_compute_time_off_allocation', store=True, readonly=False,
        help="The computed amount is the sum of the new right to time off and the number of time off already taken by the employee. Example: Moving from a full time to a 4/5 part time with 6 days already taken will result into an amount of 80%% of 14 days + 6 days (rounded down) = 17 days.")
    time_off_allocation_hours = fields.Float(compute='_compute_time_off_allocation', store=True, readonly=False)
    leave_allocation_id = fields.Many2one('hr.leave.allocation', compute='_compute_leave_allocation_id')
    initial_time_off_allocation = fields.Float(compute='_compute_leave_allocation_id')
    initial_time_off_allocation_hours = fields.Float(compute='_compute_leave_allocation_id')
    remaining_time_off_allocation = fields.Float(compute='_compute_leave_allocation_id')
    requires_new_contract = fields.Boolean(compute='_compute_requires_new_contract')
    adapt_allocation = fields.Boolean(default=True)
    adapt_wage = fields.Boolean(default=True)

    @api.depends('employee_id.resource_calendar_id.reference_calendar_id', 'structure_type_id.default_resource_calendar_id')
    def _compute_full_resource_calendar_id(self):
        for wizard in self:
            wizard.full_resource_calendar_id = wizard.employee_id.resource_calendar_id.reference_calendar_id or wizard.structure_type_id.default_resource_calendar_id

    @api.depends('version_id', 'resource_calendar_id', 'date_start', 'date_end')
    def _compute_wages(self):
        for wizard in self:
            #Compute full wage first since wage depends on it
            wizard.current_wage = wizard.version_id._get_contract_wage()
            work_time_rate = wizard.version_id.work_time_rate
            wizard.full_wage = wizard.current_wage / (work_time_rate if work_time_rate else 1)

            ref_calendar = wizard.version_id._get_reference_calendar()
            date_start = wizard.date_start or fields.Date.today()
            date_end = wizard.date_end or date_start
            new_work_time_rate = wizard.resource_calendar_id._l10n_be_get_work_time_rate_time_credit_included(
                date_start,
                date_end,
                ref_calendar=ref_calendar
            )
            wizard.wage = wizard.full_wage * float(new_work_time_rate)

    @api.depends('full_resource_calendar_id')
    def _compute_full_time_off_allocation(self):
        # NOTE: Hard coded to 20, this might cause issues later but we can't thing of any case where
        #  it is not 20 but kept as a compute for it to be easier to adapt if necessary
        self.write({
            'full_time_off_allocation': 20,
        })

    @api.model
    def _compute_new_allocation(self, leave_allocation, current_calendar, new_calendar, date_start):
        """Returns a (days, hours) tuple. Hours are computed independently alongside days (not
        derived from the day count and new_calendar's hours/day), mirroring
        hr.payroll.alloc.paid.leave's own hours-first computation, so the exact hour counter (see
        l10n_be_hr_payroll's l10n_be_hours_tracked) doesn't silently go stale on a schedule change.
        """
        if current_calendar.hours_per_week == 0 or not leave_allocation:
            return 0, 0

        if new_calendar.work_time_rate < current_calendar.work_time_rate:
            rate = new_calendar.work_time_rate / current_calendar.work_time_rate
            leaves_taken = leave_allocation.leaves_taken
            remaining_leaves = leave_allocation.number_of_days - leaves_taken
            days = leaves_taken + float_round(remaining_leaves * rate, precision_rounding=0.5)
            hours_taken = leave_allocation.l10n_be_hours_taken
            remaining_hours = leave_allocation.number_of_hours - hours_taken
            hours = hours_taken + float_round(remaining_hours * rate, precision_digits=2)
            return days, hours

        # Simulate the start of year allocation to have an accurate value
        paid_leave_wizard = self.env['hr.payroll.alloc.paid.leave']\
            .with_company(leave_allocation.employee_company_id).with_context(forced_calendar=new_calendar).new({
                'year': str(date_start.year - 1),
                'employee_ids': leave_allocation.employee_id,
            })
        if paid_leave_wizard.alloc_employee_ids:
            alloc_employee = paid_leave_wizard.alloc_employee_ids[0]
            new_allocation = max(0, alloc_employee.expected_paid_time_off_to_allocate - leave_allocation.leaves_taken)
            new_allocation_hours = max(0, alloc_employee.expected_hours_to_allocate - leave_allocation.l10n_be_hours_taken)
        else:
            new_allocation = 0
            new_allocation_hours = 0

        # There is a maximum that we should never pass, in theory we should never pass that limit
        # since we round down, but since the payroll officer will not be able to modify this values
        # it is good to have that limit
        max_allocation = (new_calendar.days_per_week * 4) - leave_allocation.leaves_taken
        max_allocation_hours = (new_calendar.hours_per_week * 4) - leave_allocation.l10n_be_hours_taken

        # An allocation's number of days/hours may never be below what was already taken
        days = max(min(new_allocation, max_allocation) + leave_allocation.leaves_taken, leave_allocation.leaves_taken)
        hours = max(min(new_allocation_hours, max_allocation_hours) + leave_allocation.l10n_be_hours_taken, leave_allocation.l10n_be_hours_taken)
        return days, hours

    @api.depends('leave_allocation_id', 'resource_calendar_id', 'date_start')
    def _compute_time_off_allocation(self):
        for wizard in self:
            date_start = wizard.date_start or fields.Date().today()
            wizard.time_off_allocation, wizard.time_off_allocation_hours = self._compute_new_allocation(
                wizard.leave_allocation_id, wizard.current_resource_calendar_id,
                wizard.resource_calendar_id, date_start,
            )

    def _compute_leave_allocation_id(self):
        employee_ids = self.version_id.employee_id.ids
        allocations = self.env["hr.leave.allocation"].search([
            ("work_entry_type_id.code", "=", "016.00"),
            ("work_entry_type_id.country_code", "=", "BE"),
            ("employee_id", "in", employee_ids),
            ("state", "=", "validate"),
        ], order="id")
        allocations_by_employee = allocations.grouped("employee_id")
        for wizard in self:
            allocation = allocations_by_employee.get(
                wizard.version_id.employee_id,
                self.env["hr.leave.allocation"],
            )[:1]

            wizard.leave_allocation_id = allocation
            wizard.initial_time_off_allocation = allocation.number_of_days if allocation else 0
            wizard.initial_time_off_allocation_hours = allocation.number_of_hours if allocation else 0
            wizard.remaining_time_off_allocation = (
                allocation.number_of_days - allocation.leaves_taken
                if allocation else 0
            )

    @api.depends('version_id', 'date_start')
    def _compute_requires_new_contract(self):
        # NOTE: this might need more checks
        requires_new_contract = self.filtered(lambda w: (
            not w.date_start or
            not w.version_id or
            not w.version_id.contract_date_start or
            w.date_start <= w.version_id.contract_date_start
        ))
        requires_new_contract.write({'requires_new_contract': True})
        (self - requires_new_contract).write({'requires_new_contract': False})

    def _update_allocation_or_schedule(self, date, contract, current, new, max_days):
        self.ensure_one()
        if not self.leave_allocation_id:
            return
        if date > fields.Date.context_today(self) or self.env.context.get('force_schedule', False):
            # Schedule for cron
            self.env['l10n_be.schedule.change.allocation'].create({
                'effective_date': date,
                'version_id': contract.id,
                'current_resource_calendar_id': current.id,
                'new_resource_calendar_id': new.id,
                'leave_allocation_id': self.leave_allocation_id.id,
                'maximum_days': max_days
            })
        else:
            # NOTE: for now we don't check the period but since creating a part time contract for a
            #  previous period is pretty weird something like this might be needed:
            # not self.date_end or self.date_end >= fields.Date.today()
            # Update directly, use initial time off allocation if this is the continuation contract
            is_continuation = new == self.version_id.resource_calendar_id
            new_total = self.initial_time_off_allocation if is_continuation else self.time_off_allocation
            new_total_hours = self.initial_time_off_allocation_hours if is_continuation else self.time_off_allocation_hours

            allocation = self.leave_allocation_id

            days_remaining_before = allocation.number_of_days - allocation.leaves_taken
            hours_remaining_before = allocation.number_of_hours - allocation.l10n_be_hours_taken

            allocation.write({
                'number_of_days': new_total,
                'number_of_hours': new_total_hours,
            })

            days_remaining_after = new_total - allocation.leaves_taken
            hours_remaining_after = new_total_hours - allocation.l10n_be_hours_taken

            allocation._message_log(body=self.env._(
                'Working schedule changed from %(current_schedule)s to %(new_schedule)s%(br)s'
                'Remaining time off: %(days_remaining_before)s days (%(hours_remaining_before)s hours)%(br)s'
                'Adapted to: %(days_remaining_after)s days (%(hours_remaining_after)s hours)%(br)s'
                'New total: %(new_total_days)s days (%(new_total_hours)s hours)',
                current_schedule=current.name,
                new_schedule=new.name,
                days_remaining_before=days_remaining_before,
                hours_remaining_before=hours_remaining_before,
                days_remaining_after=days_remaining_after,
                hours_remaining_after=hours_remaining_after,
                new_total_days=new_total,
                new_total_hours=new_total_hours,
                br=Markup('<br/>'),
            ))

    def action_validate(self):
        self.ensure_one()
        if self.date_end and self.date_start > self.date_end:
            raise ValidationError(self.env._('Start date must be earlier than end date.'))
        if self.date_start < self.version_id.contract_date_start:
            raise ValidationError(self.env._('Start date must be later than the current contract\'s start date.'))
        if self.version_id.contract_date_end and self.date_end and self.version_id.contract_date_end < self.date_end:
            raise ValidationError(self.env._('Current contract is finished before the end of the new contract.'))

        # Set a closing date on the current contract
        previous_contract_date_end = self.version_id.contract_date_end
        previous_wage = self.version_id._get_contract_wage()
        contract_date_end = False
        if self.date_start != self.version_id.contract_date_start:
            contract_date_end = self.date_start - timedelta(days=1)
        elif self.date_end:
            contract_date_end = self.date_end

        if contract_date_end:
            self.with_context(close_contract=False).version_id.contract_date_end = contract_date_end

        new_wage = self.wage if self.adapt_wage else self.version_id._get_contract_wage()
        wage_field = self.version_id._get_contract_wage_field()
        new_version = self.version_id.employee_id.create_version({
            'date_version': self.date_start,
            'contract_date_start': self.date_start,
            'contract_date_end': self.date_end,
            wage_field: new_wage,
            'resource_calendar_id': self.resource_calendar_id.id,
        })
        new_contracts = new_version
        # Since _get_contract_wage_field is not always 'wage' we also want to change the original wage
        if new_contracts._get_contract_wage_field() != 'wage':
            new_contracts.wage = new_wage

        # Process allocation changes
        if self.leave_allocation_id and self.adapt_allocation:
            original_allocated_days = self.leave_allocation_id.number_of_days - self.leave_allocation_id.leaves_taken
            self._update_allocation_or_schedule(
                self.date_start,
                new_contracts[0],
                self.current_resource_calendar_id,
                self.resource_calendar_id,
                self.full_time_off_allocation,
            )

        if self.date_end:
            # Create a contract for the rest of the original contrat's time period if it exists
            if not previous_contract_date_end or self.date_end < previous_contract_date_end:
                post_contract = self.version_id.employee_id.create_version({
                    'date_version': self.date_end + timedelta(days=1),
                    'contract_date_start': self.date_end + timedelta(days=1),
                    'contract_date_end': previous_contract_date_end,
                    # resource_calendar_id is copy=False
                    'resource_calendar_id': self.version_id.resource_calendar_id.id,
                    wage_field: previous_wage,
                    'work_time_rate': self.version_id.work_time_rate,
                })
                new_contracts |= post_contract
                # We also need to update the allocation when this contract starts,
                #  basically revert back changes
                if self.leave_allocation_id and self.adapt_allocation:
                    self._update_allocation_or_schedule(
                        post_contract.contract_date_start,
                        post_contract,
                        self.resource_calendar_id,
                        self.current_resource_calendar_id,
                        original_allocated_days,
                    )

        # When changing the schedule from the contract history we can just reload the view instead of going on to a separate view
        if self.env.context.get('from_history', False):
            return True

        version_created = new_version != self.version_id
        if not version_created:
            new_version.write({
                wage_field: new_wage,
                'resource_calendar_id': self.resource_calendar_id.id,
            })

        next_action = {
            'res_model': 'hr.employee',
            'res_id': new_version.employee_id.id,
            'view_id': False,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'type': 'ir.actions.act_window',
            'context': {'version_id': new_version.id},
        }

        if version_created:
            message = self.env._('New employee version created')
        else:
            message = (
                self.env._('Working schedule and wage updated')
                if self.adapt_wage
                else self.env._('Working schedule updated')
            )
        next_action = self._get_notification_action(message=message, next_action=next_action)

        if self.adapt_allocation and self.leave_allocation_id:
            allocation_url = self.leave_allocation_id._notify_get_action_link('view')
            message = self.env._('%%s updated to %(days)s days.', days=self.time_off_allocation)
            links = [{
                'label': self.env._('Allocation'),
                'url': allocation_url,
            }]
            next_action = self._get_notification_action(message=message, next_action=next_action, links=links,
                sticky=True)

        return next_action

    def _get_notification_action(self, message, next_action, links=None, sticky=False):
        params = {
            'type': 'success',
            'message': message,
            'sticky': sticky,
            'next': next_action,
        }
        if links:
            params['links'] = links
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': params,
        }
