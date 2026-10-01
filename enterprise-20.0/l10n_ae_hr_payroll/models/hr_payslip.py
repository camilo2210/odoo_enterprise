# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"
    year_to_date_sick_days = fields.Float(compute='_compute_year_to_date_sick_days')
    days_on_leave_for_period = fields.Float(compute='_compute_days_on_leave_for_period', store=True, readonly=False)
    l10n_ae_basic_salary = fields.Monetary(string="Basic Salary", compute="_compute_l10n_ae_basic_salary", currency_field="currency_id")
    l10n_ae_hourly_wage = fields.Monetary(string="SA Hourly Wage", compute="_compute_l10n_ae_hourly_wage", currency_field="currency_id")
    l10n_ae_hours_worked = fields.Float(string="Hours Worked", compute="_compute_l10n_ae_worked_values")
    l10n_ae_total_paid_hours = fields.Float(string="Total Paid Hours", compute="_compute_l10n_ae_worked_values")

    @api.depends(
        'worked_days_line_ids.number_of_hours',
        'worked_days_line_ids.code',
        'worked_days_line_ids.is_paid',
    )
    def _compute_l10n_ae_worked_values(self):
        excluded_paid_entries = ['158.00', '000.00', '040.00']
        all_lines = self.env['hr.payslip.worked_days']._read_group(
            domain=[('payslip_id', 'in', self.ids)],
            groupby=['payslip_id', 'code', 'is_paid'],
            aggregates=['number_of_hours:sum'],
        )
        values_by_payslip = defaultdict(lambda: {'l10n_ae_hours_worked': 0, 'l10n_ae_total_paid_hours': 0})
        for line in all_lines:
            # line = (hr.payslip(), code, is_paid, number_of_hours)
            payslip_id = line[0]

            if line[1] == '002.00':
                values_by_payslip[payslip_id.id]['l10n_ae_hours_worked'] += line[3]

            if line[2] and line[1] not in excluded_paid_entries:
                values_by_payslip[payslip_id.id]['l10n_ae_total_paid_hours'] += line[3]

        for record in self:
            record.update(values_by_payslip[record.id])

    @api.depends(
        'version_id.wage_type',
        'version_id.resource_calendar_id.hours_per_day',
        'version_id.l10n_ae_housing_allowance',
        'version_id.l10n_ae_transportation_allowance',
        'version_id.l10n_ae_other_allowances'
    )
    def _compute_l10n_ae_hourly_wage(self):
        for record in self:
            if record.version_id.wage_type == 'hourly':
                record.l10n_ae_hourly_wage = record.version_id.hourly_wage
            else:
                hours = sum(record.worked_days_line_ids.mapped('number_of_days')) * record.version_id.resource_calendar_id.hours_per_day
                gross = record.version_id.wage + record.version_id.l10n_ae_housing_allowance + record.version_id.l10n_ae_transportation_allowance + record.version_id.l10n_ae_other_allowances
                record.l10n_ae_hourly_wage = gross / hours if hours > 0 else 0

    def _get_l10n_ae_total_work_hours(self):
        self.ensure_one()

        calendar = self.version_id.resource_calendar_id
        if calendar:
            date_from = fields.Datetime.to_datetime(self.date_from)
            date_to = fields.Datetime.to_datetime(self.date_to) + relativedelta(days=1) - relativedelta(microseconds=1)
            hours = calendar.get_work_duration_data(date_from, date_to).get('hours', 0)
            return hours

        return self.sum_worked_hours

    def _get_l10n_ae_hourly_allowance_value(self, allowance_type):
        self.ensure_one()
        total_hours = self._get_l10n_ae_total_work_hours()
        if allowance_type not in ('housing', 'transportation', 'other') or total_hours <= 0:
            return 0
        field = f'l10n_ae_{allowance_type}_allowance{"s" if allowance_type == "other" else ""}'
        return self.version_id[field] / total_hours

    @api.depends(lambda self: self._get_ae_compute_basic_salary_fields())
    def _compute_l10n_ae_basic_salary(self):
        for record in self:
            if record.version_id.has_static_work_entries():
                record.l10n_ae_basic_salary = record.version_id.wage
            else:
                total_hours = record._get_l10n_ae_total_work_hours()
                record.l10n_ae_basic_salary = (
                    record.l10n_ae_hours_worked * (record.version_id.wage / total_hours)
                    if total_hours > 0 else 0
                )

    def _get_ae_compute_basic_salary_fields(self):
        fields = ['sum_worked_hours', 'l10n_ae_hours_worked', 'version_id.wage']
        if self.env['ir.module.module']._get('hr_holidays_attendance').state == 'installed':
            fields = fields + ['version_id.attendance_based']
        return fields

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_ae_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
                'data/hr_payroll_structure_type_data.xml',
                'data/hr_payroll_structure_data.xml',
                'data/hr_salary_rule_regular_pay_data.xml',
                'data/hr_salary_rule_instant_pay_data.xml',
            ])]

    def _l10n_ae_get_eos_daily_salary(self):
        years = relativedelta(self.date_to, self.employee_id._get_first_version_date()).years
        ratio = 21 / 30 if years <= 5 else 1
        days_in_month = calendar.monthrange(self.date_from.year, self.date_from.month)[1] or 30

        salary = 0
        if self.version_id.l10n_ae_is_computed_based_on_daily_salary:
            salary = self.version_id.l10n_ae_eos_daily_salary
        else:
            salary = (self.version_id.wage / 12) / days_in_month

        return salary * ratio

    @api.model
    def _l10n_ae_get_wps_formatted_amount(self, val):
        currency = self.env.ref('base.AED')
        return f'{currency.round(val):.{currency.decimal_places}f}'

    def _l10n_ae_get_wps_data(self):
        rows = []
        input_codes = [
            "HOUALLOWINP",
            "CONVALLOWINP",
            "MEDALLOWINP",
            "ANNUALPASSALLOWINP",
            "OVERTIMEALLOWINP",
            "OTALLOWINP",
            "LEAVEENCASHINP",
        ]
        inputs_dict = self._get_line_values(input_codes)

        for payslip in self:
            employee = payslip.employee_id
            variable_inputs = [inputs_dict[code][payslip.id]['total'] for code in input_codes]
            total_variable = sum(variable_inputs)

            bank_account = employee.primary_bank_account_id
            l10n_ae_routing_code = bank_account._get_clearing_number('AE')
            rows.append([
                "EDR",
                (employee.identification_id or '').zfill(14),
                (l10n_ae_routing_code or '').zfill(9),
                bank_account.account_number or '',
                payslip.date_from.strftime('%Y-%m-%d'),
                payslip.date_to.strftime('%Y-%m-%d'),
                (payslip.date_to - payslip.date_from).days + 1,
                self._l10n_ae_get_wps_formatted_amount(payslip.net_wage - total_variable),
                self._l10n_ae_get_wps_formatted_amount(total_variable),
                payslip.days_on_leave_for_period
            ])

            if not payslip.currency_id.is_zero(total_variable):
                rows.append([
                    "Variable",
                    (employee.identification_id or '').zfill(14),
                    (l10n_ae_routing_code or '').zfill(9),
                    *map(self._l10n_ae_get_wps_formatted_amount, (max(0, v) for v in variable_inputs)),
                ])

        return rows

    def _weekdays_between(self, start, end):
        """Return number of weekdays between two dates inclusive."""
        attendances_by_date = self.employee_id.resource_calendar_id._get_attendances_by_date(start, end)
        return sum(1 for atts in attendances_by_date.values() if any(a._is_work_period() for a in atts))

    @api.depends('date_from', 'date_to', 'state')
    def _compute_year_to_date_sick_days(self):
        employee_ids = self.mapped('employee_id').ids
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('work_entry_type_id.code', '=', '013.00')
        ])
        for slip in self:
            total_leave_days = 0
            for leave in all_leaves.filtered(lambda leave: leave.employee_id.id == slip.employee_id.id):
                if not leave.request_date_from or not leave.request_date_to:
                    continue
                if leave.request_date_from > slip.date_to:
                    continue
                year_start = date(slip.date_to.year, 1, 1)
                start = max(leave.request_date_from, year_start)
                end = min(leave.request_date_to, slip.date_to)
                if start <= end:
                    total_leave_days += slip._weekdays_between(start, end)
            slip.year_to_date_sick_days = total_leave_days

    def _compute_input_line_ids(self):
        # Seed an advance-recovery input row whenever the employee has an
        # outstanding balance.
        res = super()._compute_input_line_ids()
        balance_by_employee = self._get_salary_advance_balances_by_employee()
        uae_employee_struct = self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure')
        input_advance_recovery_rule = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_employee_payroll_structure_advance_recovery')
        for slip in self:
            if not slip.employee_id or slip.country_code != "AE":
                continue
            if slip.struct_id == uae_employee_struct:
                balance = balance_by_employee[slip.employee_id]
                if balance <= 0:
                    continue
                slip._set_input_value(input_advance_recovery_rule.code, balance)
        return res

    def _get_salary_advance_balances_by_employee(self):
        input_salary_advance_rule_code = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_salary_advance').sudo().code
        input_advance_recovery_rule_code = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_employee_payroll_structure_advance_recovery').sudo().code
        ae_codes = [input_salary_advance_rule_code, input_advance_recovery_rule_code]
        payslips_by_employee = self._read_group(
            domain=[
                ('state', 'in', ('validated', 'paid')),
                ('employee_id', 'in', self.employee_id.ids),
                ('input_line_ids.code', 'in', ae_codes),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset']
        )
        balance_by_employee = defaultdict(float)
        for employee_id, payslips in payslips_by_employee:
            for payslip in payslips:
                # Check for ADV (Salary Advance)
                adv_amount = payslip._get_input_line_amount(input_salary_advance_rule_code)
                if adv_amount:
                    balance_by_employee[employee_id] += adv_amount
                # Check for ADVREC (Advance Recovery)
                advrec_amount = payslip._get_input_line_amount(input_advance_recovery_rule_code)
                if advrec_amount:
                    balance_by_employee[employee_id] -= advrec_amount
        return balance_by_employee

    def action_payslip_payment_report(self, export_format='l10n_ae_wps'):
        action = super().action_payslip_payment_report()
        if self.company_id.country_code != 'AE':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action

    def compute_sheet(self):
        ae_payslips = self.filtered(lambda payslip: payslip.country_code == 'AE')
        ae_payslips._compute_year_to_date_sick_days()
        ae_payslips._compute_l10n_ae_hourly_wage()
        ae_payslips._compute_l10n_ae_worked_values()
        ae_payslips._compute_l10n_ae_basic_salary()
        return super().compute_sheet()

    @api.depends('date_from', 'date_to', 'state')
    def _compute_days_on_leave_for_period(self):
        for rec in self:
            leave_days = 0
            line_ids = rec.worked_days_line_ids
            for line in line_ids:
                if line.code == '000.00' or line.code == '158.00' or line.code == '013.00':
                    leave_days += line.number_of_days
            rec.days_on_leave_for_period = leave_days

    @api.model
    def _issues_dependencies(self):
        dependencies = super()._issues_dependencies()
        dependencies += [
            'company_id.l10n_ae_bank_account_id',
            'company_id.l10n_ae_employer_code',
            'employee_id.bank_account_ids.clearing_label_id',
            'employee_id.bank_account_ids.clearing_number',
            'employee_id.identification_id',
        ]
        return dependencies
