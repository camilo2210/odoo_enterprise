# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import UTC, date, datetime, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools import SQL, float_round
from odoo.exceptions import UserError


class HrPayrollAllocPaidLeave(models.TransientModel):
    _name = 'hr.payroll.alloc.paid.leave'
    _description = 'Manage the Allocation of Paid Time Off'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    def _get_range_of_years(self):
        current_year = fields.Date.today().year
        return [(str(year), str(year)) for year in range(current_year - 5, current_year + 1)]

    year = fields.Selection(string='Reference Period', selection='_get_range_of_years', required=True, help="Year of the period to consider", default=lambda self: str(fields.Date.context_today(self).year))
    employee_ids = fields.Many2many('hr.employee', string='Employees', help="Use this to limit the employees to compute")
    alloc_employee_ids = fields.One2many('hr.payroll.alloc.employee', 'alloc_paid_leave_id',
        compute='_compute_alloc_employee_ids', store=True, readonly=False)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    has_time_off_to_postpone = fields.Boolean(compute='_compute_has_time_off_to_postpone')

    def _get_default_paid_time_off_work_entry_type(self):
        return self.env.ref('hr_work_entry.be_work_entry_type_legal_leave')

    def _get_default_postponed_n1_work_entry_type(self):
        return self.env.ref('hr_work_entry.l10n_be_work_entry_type_postponed_paid_time_off_n1')

    def _get_default_postponed_n2_work_entry_type(self):
        return self.env.ref('hr_work_entry.l10n_be_work_entry_type_postponed_paid_time_off_n2')

    def _compute_display_name(self):
        for record in self:
            record.display_name = self.env._('Paid Time Off Allocation')

    def _get_calendar_nominal_days_per_week(self, calendar):
        """Nominal weekly schedule the employee is contractually entitled to leave against."""
        if calendar.calendar_type == 'variable':
            return calendar.days_per_week
        attendances = calendar.attendance_ids.filtered(lambda a: a._is_work_period())
        return len(set(attendances.mapped('dayofweek')))

    def _get_calendar_nominal_hours_per_day(self, calendar):
        """Hours/day derived fresh from hours/week and days/week, not the stored field."""
        days_per_week = self._get_calendar_nominal_days_per_week(calendar)
        return calendar.hours_per_week / days_per_week if days_per_week else 0

    def _cap_days_and_hours(self, hours, hours_per_day, day_cap):
        if not hours_per_day:
            return 0, 0
        days = float_round(hours / hours_per_day, precision_rounding=0.5, rounding_method='DOWN')
        days = min(days, day_cap)
        hours = min(hours, day_cap * hours_per_day)
        return days, hours

    def _get_working_days_count(self, date_start, date_end):
        """Number of Monday to Saturday days in the inclusive range."""
        total_days = (date_end - date_start).days + 1
        if total_days <= 0:
            return 0
        full_weeks, remaining_days = divmod(total_days, 7)
        sundays = full_weeks + ((6 - date_start.weekday()) % 7 < remaining_days)
        return total_days - sundays

    def _get_allocation_data(self):
        paid_time_off_work_entry_type = self._get_default_paid_time_off_work_entry_type()
        postponed_n1_work_entry_type = self._get_default_postponed_n1_work_entry_type()
        postponed_n2_work_entry_type = self._get_default_postponed_n2_work_entry_type()
        if not self.year or not self.company_id or not paid_time_off_work_entry_type:
            return {}

        period_start = date(int(self.year), 1, 1)
        period_end = date(int(self.year), 12, 31)
        next_period_start = period_start + relativedelta(years=1)
        next_period_end = period_end + relativedelta(years=1)

        period_work_days_count = self._get_working_days_count(period_start, period_end)

        query = SQL("""
            SELECT v.id AS version_id,
                   v.employee_id AS employee_id,
                   v.contract_date_start AS date_start,
                   v.contract_date_end AS date_end,
                   v.resource_calendar_id AS resource_calendar_id
              FROM hr_version v
              JOIN hr_employee e ON v.employee_id = e.id
         LEFT JOIN l10n_be_worker_code w ON v.l10n_be_worker_code_id = w.id
         LEFT JOIN l10n_be_joint_committee jc ON v.l10n_be_joint_committee_id = jc.id
             WHERE v.contract_date_start <= %(stop)s
               AND (v.contract_date_end IS NULL OR v.contract_date_end >= %(start)s)
               AND e.active IS TRUE
               AND e.company_id IN %(company)s
               AND v.l10n_be_dimona_category = 'oth'
               AND w.dmfa_code IN ('050', '439', '450', '484', '487', '495')
               AND v.company_id IN %(company)s
               AND v.active IS TRUE
               AND (jc.egov3_code IS NULL OR jc.egov3_code != '999')
               %(employee_check)s
            """,
            start=period_start,
            stop=period_end,
            company=tuple(self.env.companies.ids),
            employee_check=SQL("AND e.id IN %s", tuple(self.employee_ids.ids)) if self.employee_ids else SQL(),
        )
        self.env.cr.execute(query)

        # employee_id -> (periods, version_id). Hours accrue per period (ratio * 4 weeks *
        # that period's hours/week), kept separate rather than summed: the cap against next
        # year's rate applies per period, not once on the grand total. Days are derived last.
        alloc_employees = defaultdict(lambda: ([], None))
        for vals in self.env.cr.dictfetchall():
            periods, version_id = alloc_employees[vals['employee_id']]

            date_start = vals['date_start']
            date_end = vals['date_end']
            calendar = self.env['resource.calendar'].browse(vals['resource_calendar_id'])

            if date_start < period_start:
                date_start = period_start
            if date_end is None or date_end > period_end:
                if date_end is None:
                    version_id = vals['version_id']
                date_end = period_end

            work_days_count = self._get_working_days_count(date_start, date_end)
            work_days_ratio = work_days_count / period_work_days_count  # In case the employee didn't work over the whole period
            periods.append((work_days_ratio * 4, calendar.hours_per_week))

            alloc_employees[vals['employee_id']] = (periods, version_id)

        # alloc_employees is only populated by the loop above, so this must be built after it,
        # not before: browse()-ing it any earlier would freeze employees empty.
        employees = self.env['hr.employee'].browse(alloc_employees.keys())

        # Attestation hours are added as one more period (weeks_equivalent, hours_per_week),
        # so they go through the same per-period cap as everything else.
        for employee in employees:
            periods, version_id = alloc_employees[employee.id]
            employee_reference_calendar = employee.version_id._get_reference_calendar()
            reference_days_per_week = self._get_calendar_nominal_days_per_week(employee_reference_calendar)
            first_version_date = employee._get_first_version_date()
            if first_version_date and int(self.year) == first_version_date.year and reference_days_per_week:
                attests = employee.l10n_be_holiday_attest_ids.filtered(lambda a: a.year == int(self.year))
                for attest in attests:
                    year_work_ratio = attest.prev_assimilated_days / (attest.prev_work_days_per_week * 52)
                    weeks_equivalent = year_work_ratio * 20 / reference_days_per_week
                    # Capped at the previous employer's own absolute hours/week, someone moving from
                    # 20h/week to 40h/week keeps "4 weeks of 20 hours", capped at the old, lower
                    # absolute rate, regardless of what the current reference week is worth.
                    period_hours_per_week = min(attest.prev_work_hours_per_week, attest.prev_reference_work_hours_per_week)
                    periods.append((weeks_equivalent, period_hours_per_week))

        all_allocations = dict(self.env['hr.leave.allocation']._read_group(
            domain=[
                ('employee_id', 'in', alloc_employees.keys()),
                ('state', '!=', 'refuse'),
                ('work_entry_type_id', 'in', (
                    paid_time_off_work_entry_type + postponed_n1_work_entry_type + postponed_n2_work_entry_type
                ).ids),
                ('date_from', '>=', next_period_start),
                ('date_to', '<=', next_period_end),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset']))

        next_period_domain = [
            ('employee_id', 'in', [
                employee_id for employee_id, (_, version_id) in alloc_employees.items() if version_id is None
            ]),
            ('active', '=', True),
            ('company_id', 'in', self.env.companies.ids),
            ('contract_date_start', '<=', next_period_end),
            '|',
                ('contract_date_end', '=', False),
                ('contract_date_end', '>=', next_period_start),
        ]
        next_period_version_by_employee = {}
        for version in self.env['hr.version'].search(next_period_domain, order='contract_date_start desc'):
            next_period_version_by_employee.setdefault(version.employee_id.id, version)

        allocation_data_by_employee = {}

        for employee in employees:
            employee_id = employee.id
            periods, contract_next_period = alloc_employees[employee_id]
            accrued_hours = sum(weeks_equivalent * hours_per_week for weeks_equivalent, hours_per_week in periods)
            hours_to_allocate = 0
            expected_paid_time_off_to_allocate = 0
            expected_hours_to_allocate = 0
            paid_time_off_to_allocate = 0
            paid_time_off = 0
            paid_time_off_hours = 0
            already_allocated = 0
            already_allocated_hours = 0
            already_postponed_n1 = 0
            already_postponed_n2 = 0
            holiday_attest_balance = 0
            if contract_next_period is None:
                # We need the contract currently active for the next period for each employee to allocate the correct time off based on this contract.
                contract_next_period = next_period_version_by_employee.get(employee_id, self.env['hr.version'])
            else:
                contract_next_period = self.env['hr.version'].browse(contract_next_period)

            if contract_next_period.id:
                # fall back on the reference calendar, so that it does not crash for flexible employees
                calendar = self.env.context.get('forced_calendar', contract_next_period.resource_calendar_id) or employee_reference_calendar
                days_in_week = self._get_calendar_nominal_days_per_week(calendar)
                # Each period is capped at next year's own rate (not just the grand total), then
                # days are derived from the capped hours using next year's calendar.
                capped_hours = sum(
                    weeks_equivalent * min(hours_per_week, calendar.hours_per_week)
                    for weeks_equivalent, hours_per_week in periods
                )
                hours_per_day = self._get_calendar_nominal_hours_per_day(calendar)
                expected_paid_time_off_to_allocate, expected_hours_to_allocate = self._cap_days_and_hours(
                    capped_hours, hours_per_day, 4 * days_in_week)

                for alloc in all_allocations.get(employee, self.env['hr.leave.allocation']):
                    if alloc.work_entry_type_id.code == paid_time_off_work_entry_type.code:
                        already_allocated += alloc.number_of_days
                        already_allocated_hours += alloc.number_of_hours
                    elif postponed_n1_work_entry_type and alloc.work_entry_type_id.code == postponed_n1_work_entry_type.code:
                        already_postponed_n1 += alloc.number_of_days
                    elif postponed_n2_work_entry_type and alloc.work_entry_type_id.code == postponed_n2_work_entry_type.code:
                        already_postponed_n2 += alloc.number_of_days

                paid_time_off_to_allocate, hours_to_allocate = self._cap_days_and_hours(
                    max(0, capped_hours - already_allocated_hours), hours_per_day, 4 * days_in_week)

            if not contract_next_period.id:
                # fall back on the reference calendar, so that it does not crash for flexible employees
                employee_calendar = employee.resource_calendar_id or employee_reference_calendar
                days_in_week = self._get_calendar_nominal_days_per_week(employee_calendar)
                hours_per_day = self._get_calendar_nominal_hours_per_day(employee.version_id._get_reference_calendar())
            paid_time_off, paid_time_off_hours = self._cap_days_and_hours(accrued_hours, hours_per_day, 4 * days_in_week)

            if employee.first_contract_date and int(self.year) == employee.first_contract_date.year:
                holiday_attest_balance = sum(employee.l10n_be_holiday_attest_ids
                    .filtered(lambda a: a.year == int(self.year))
                    .mapped('days_to_allocate')
                )

            allocation_data_by_employee[employee] = {
                'employee_id': employee_id,
                'paid_time_off': paid_time_off,
                'paid_time_off_hours': paid_time_off_hours,
                'expected_paid_time_off_to_allocate': expected_paid_time_off_to_allocate,
                'expected_hours_to_allocate': expected_hours_to_allocate,
                'already_allocated_paid_time_off': already_allocated,
                'already_postponed_n1': already_postponed_n1,
                'already_postponed_n2': already_postponed_n2,
                'paid_time_off_to_allocate': paid_time_off_to_allocate,
                'hours_to_allocate': hours_to_allocate,
                'contract_next_year_id': contract_next_period.id,
                'holiday_attest_balance': holiday_attest_balance,
            }

        return allocation_data_by_employee

    @api.depends('year')
    def _compute_alloc_employee_ids(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_("You don't have the right to do this. Please contact your administrator!"))
        self.alloc_employee_ids = False

        allocation_data_by_employee = self._get_allocation_data()
        allocation_employees = self.env['hr.employee'].union(allocation_data_by_employee)

        # The days to postpone are the ones the user confirmed on the December payslip
        postponed_inputs_by_employee = self._get_postponed_inputs_by_employee(allocation_employees, int(self.year))

        # Include selected employees so they are shown even if they don't have a valid contract.
        employees = allocation_employees | self.employee_ids._origin

        alloc_employee_vals = []
        for employee in employees:
            vals = allocation_data_by_employee.get(employee, {})
            postponed_inputs = postponed_inputs_by_employee.get(employee, {})
            alloc_employee_vals.append({
                'employee_id': employee.id,
                'paid_time_off': vals.get('paid_time_off', 0),
                'paid_time_off_hours': vals.get('paid_time_off_hours', 0),
                'expected_paid_time_off_to_allocate': vals.get('expected_paid_time_off_to_allocate', 0),
                'expected_hours_to_allocate': vals.get('expected_hours_to_allocate', 0),
                'already_allocated_paid_time_off': vals.get('already_allocated_paid_time_off', 0),
                'paid_time_off_to_allocate': vals.get('paid_time_off_to_allocate', 0),
                'hours_to_allocate': vals.get('hours_to_allocate', 0),
                'paid_time_off_to_postpone_n1': max(0, postponed_inputs.get('PPTO1', 0) - vals.get('already_postponed_n1', 0)),
                'paid_time_off_to_postpone_n2': max(0, postponed_inputs.get('PPTO2', 0) - vals.get('already_postponed_n2', 0)),
                'contract_next_year_id': vals.get('contract_next_year_id', False),
                'holiday_attest_balance': vals.get('holiday_attest_balance', 0),
                'alloc_paid_leave_id': self.id,
            })

        self.alloc_employee_ids = self.env['hr.payroll.alloc.employee'].create(alloc_employee_vals)

    @api.depends('alloc_employee_ids.paid_time_off_to_postpone_n1', 'alloc_employee_ids.paid_time_off_to_postpone_n2')
    def _compute_has_time_off_to_postpone(self):
        for record in self:
            record.has_time_off_to_postpone = any(
                line.paid_time_off_to_postpone_n1 or line.paid_time_off_to_postpone_n2
                for line in record.alloc_employee_ids
            )

    def generate_allocation(self):
        allocation_values = []
        paid_time_off_work_entry_type = self._get_default_paid_time_off_work_entry_type()
        postponed_n1_work_entry_type = self._get_default_postponed_n1_work_entry_type()
        postponed_n2_work_entry_type = self._get_default_postponed_n2_work_entry_type()
        for alloc in self.alloc_employee_ids:
            if alloc.paid_time_off_to_allocate:
                number_of_days = round(alloc.paid_time_off_to_allocate * 2) / 2  # round the paid time off until x.5
                if number_of_days:
                    # number_of_hours is the wizard's own computed value, not days * rate.
                    allocation_values.append({
                        'name': self.env._('Paid Time Off Allocation'),
                        'work_entry_type_id': paid_time_off_work_entry_type.id,
                        'employee_id': alloc.employee_id.id,
                        'number_of_days': number_of_days,
                        'number_of_hours': alloc.hours_to_allocate,
                        'date_from': '%d-01-01' % (int(self.year) + 1),
                        'date_to': '%d-12-31' % (int(self.year) + 1),
                    })
            if alloc.paid_time_off_to_postpone_n1:
                allocation_values.append({
                    'name': self.env._('Postponed Paid Time Off (N-1) Allocation'),
                    'work_entry_type_id': postponed_n1_work_entry_type.id,
                    'employee_id': alloc.employee_id.id,
                    'number_of_days': alloc.paid_time_off_to_postpone_n1,
                    'date_from': '%d-01-01' % (int(self.year) + 1),
                    'date_to': '%d-12-31' % (int(self.year) + 1),
                })
            if alloc.paid_time_off_to_postpone_n2:
                allocation_values.append({
                    'name': self.env._('Postponed Paid Time Off (N-2) Allocation'),
                    'work_entry_type_id': postponed_n2_work_entry_type.id,
                    'employee_id': alloc.employee_id.id,
                    'number_of_days': alloc.paid_time_off_to_postpone_n2,
                    'date_from': '%d-01-01' % (int(self.year) + 1),
                    'date_to': '%d-12-31' % (int(self.year) + 1),
                })

        allocations = self.env['hr.leave.allocation'].create(allocation_values)

        # recompute payslips with allocated postponed paid time off N-1 to pay the postponed days
        postponed_time_off_employee_ids = allocations.filtered(lambda alloc: alloc.work_entry_type_id.code == postponed_n1_work_entry_type.code).employee_id
        postponed_time_off_payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', postponed_time_off_employee_ids.ids),
            ('state', '=', 'draft'),
            ('date_from', '=', date(int(self.year), 12, 1)),
            ('date_to', '=', date(int(self.year), 12, 31))
        ])
        postponed_time_off_payslips.compute_sheet()

        return {
            'name': 'Paid Time Off Allocation',
            'domain': [('id', 'in', allocations.ids)],
            'res_model': 'hr.leave.allocation',
            'view_id': False,
            'view_mode': 'list,form',
            'type': 'ir.actions.act_window',
        }

    def _get_postponed_inputs_by_employee(self, employees, year):
        december_payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '!=', 'cancel'),
            ('date_from', '>=', date(year, 12, 1)),
            ('date_to', '<=', date(year, 12, 31)),
        ])
        postponed_inputs_by_employee = defaultdict(lambda: {'PPTO1': 0, 'PPTO2': 0})
        for line in december_payslips.input_line_ids:
            if line.code in ('PPTO1', 'PPTO2'):
                postponed_inputs_by_employee[line.payslip_id.employee_id][line.code] += line.amount
        return postponed_inputs_by_employee

    def _get_paid_time_off_to_postpone_by_employee(self, employees, year):
        """Return the paid time off balances to be postponed for each employee.

        Employees absent in December can have their N-1 balance postponed, while employees absent for the
        whole year can have their N-2 balance postponed.
        """
        paid_time_off_work_entry_type = self._get_default_paid_time_off_work_entry_type()
        postponed_n1_work_entry_type = self._get_default_postponed_n1_work_entry_type()

        period_start = date(year, 1, 1)
        period_end = date(year, 12, 31)

        all_allocations = dict(self.env['hr.leave.allocation']._read_group(
            domain=[
                ('employee_id', 'in', employees.ids),
                ('state', '!=', 'refuse'),
                ('work_entry_type_id', 'in', (paid_time_off_work_entry_type + postponed_n1_work_entry_type).ids),
                ('date_from', '>=', period_start),
                ('date_to', '>=', period_start),
                ('date_to', '<=', period_end),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset']))

        balance_by_employee = {}
        for employee in employees:
            to_postpone_n1 = 0
            to_postpone_n2 = 0
            for alloc in all_allocations.get(employee, self.env['hr.leave.allocation']):
                if alloc.work_entry_type_id.code == paid_time_off_work_entry_type.code:
                    to_postpone_n1 += alloc.virtual_remaining_leaves
                elif alloc.work_entry_type_id.code == postponed_n1_work_entry_type.code:
                    to_postpone_n2 += alloc.virtual_remaining_leaves
            balance_by_employee[employee] = (to_postpone_n1, to_postpone_n2)

        candidates = self.env['hr.employee'].union(
            employee for employee, balance in balance_by_employee.items() if any(balance)
        )
        employees_worked_in_december_ids = self._get_employees_working_in_period(
            candidates, date(year, 12, 1), period_end) if candidates else set()
        employees_worked_in_year_ids = self._get_employees_working_in_period(
            candidates, period_start, period_end) if candidates else set()

        return {
            employee: {
                'postpone_n1': to_postpone_n1 if employee.id not in employees_worked_in_december_ids else 0,
                'postpone_n2': to_postpone_n2 if employee.id not in employees_worked_in_year_ids else 0,
            }
            for employee, (to_postpone_n1, to_postpone_n2) in balance_by_employee.items()
        }

    def _get_employees_working_in_period(self, employees, date_start, date_end):
        """
        Return a set of employee ids for employees who have at least one active work interval within the specified period.
        """
        worked_employee_ids = set()

        employee_versions = self.env['hr.version'].search([
            ('employee_id', 'in', employees.ids),
            ('contract_date_start', '<=', date_end),
            '|',
                ('contract_date_end', '=', False),
                ('contract_date_end', '>=', date_start),
        ])

        start_dt = datetime.combine(date_start, time.min, tzinfo=UTC)
        end_dt = datetime.combine(date_end, time.max, tzinfo=UTC)

        for calendar, versions in employee_versions.grouped('resource_calendar_id').items():
            resources_per_tz = versions.employee_id.resource_id._get_resources_per_tz()
            intervals_by_resource = calendar._work_intervals_batch(start_dt, end_dt, resources_per_tz)

            versions_by_resource = defaultdict(list)
            for version in versions:
                versions_by_resource[version.employee_id.resource_id.id].append((
                    version.employee_id.id,
                    max(start_dt, datetime.combine(version.contract_date_start, time.min, tzinfo=UTC)),
                    min(end_dt, datetime.combine(version.contract_date_end or end_dt.date(), time.max, tzinfo=UTC)),
                ))

            for resource_id, intervals in intervals_by_resource.items():
                if not intervals:
                    continue

                for employee_id, contract_start_dt, contract_end_dt in versions_by_resource[resource_id]:
                    if employee_id in worked_employee_ids:
                        continue

                    if any(start <= contract_end_dt and end >= contract_start_dt for start, end, _ in intervals):
                        worked_employee_ids.add(employee_id)

        return worked_employee_ids


class HrPayrollAllocEmployee(models.TransientModel):
    _name = 'hr.payroll.alloc.employee'
    _description = 'Manage the Allocation of Paid Time Off Employee'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, readonly=True)
    paid_time_off_hours = fields.Float(
        "Accrued Hours", readonly=True,
        help="Paid Time Off For The Period In Hours")
    paid_time_off = fields.Float(
        "Paid Time Off For The Period", required=True, readonly=True,
        help="A day here is worth next year's contract's actual hours/day when one is resolved, "
             "or the reference calendar's otherwise.")
    expected_paid_time_off_to_allocate = fields.Float("Expected Paid Time Off To Allocate", readonly=True)
    expected_hours_to_allocate = fields.Float("Expected Hours To Allocate", readonly=True)
    already_allocated_paid_time_off = fields.Float(string="Allocated", help="Allocated paid time off from approved allocation of the year", readonly=True)
    paid_time_off_to_allocate = fields.Float("Paid Time Off To Allocate", required=True, help="1 day is the number of the amount of hours per day in the working schedule")
    hours_to_allocate = fields.Float(
        "Hours To Allocate", readonly=True,
        help="Number of hours of paid time off granted for the period, computed independently from the number of days")
    contract_next_year_id = fields.Many2one('hr.version', string="Contract Active Next Year")
    resource_calendar_id = fields.Many2one(related='contract_next_year_id.resource_calendar_id', string="Current Working Schedule", readonly=True)
    alloc_paid_leave_id = fields.Many2one('hr.payroll.alloc.paid.leave')
    paid_time_off_to_postpone_n1 = fields.Float('To Postpone (N+1)')
    paid_time_off_to_postpone_n2 = fields.Float('To Postpone (N+2)')
    holiday_attest_balance = fields.Float(help='Remaining time off from previous employer')
