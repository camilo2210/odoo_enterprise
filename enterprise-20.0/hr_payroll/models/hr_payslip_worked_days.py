# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.tools import float_round


class HrPayslipWorkedDays(models.Model):
    _name = 'hr.payslip.worked_days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    custom_name = fields.Char()
    name = fields.Char(compute='_compute_name', inverse='_inverse_name', store=False, string='Description', readonly=False)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    date_from = fields.Date(string='From', related="payslip_id.date_from", store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', related='payslip_id.employee_id', store=True, index=True)
    employee_type_id = fields.Many2one(related='employee_id.employee_type_id')
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(string='Code', related='work_entry_type_id.code')
    work_entry_type_id = fields.Many2one('hr.work.entry.type', string='Type', required=True, index=True, help="The code that can be used in the salary rules")
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    fte = fields.Float(string='FTE', compute='_compute_fte', store=True, copy=True, help="Work Time Rate * (Record Hours / Total Period Hours). For example, 4 hours of sick time for a 4/5 part-time worker (0.8 rate, 30.4 weekly hours) represents 0.105 FTE. Warning: Do not aggregate these FTE values across different pay periods, as fluctuating total hours between periods will distort the final calculation.")
    is_paid = fields.Boolean(compute='_compute_is_paid', store=True)
    amount = fields.Monetary(string='Amount', compute='_compute_amount', store=True, copy=True, readonly=False)
    version_id = fields.Many2one('hr.version', required=True, index=True, string='Employee Record',
        help="The contract this worked days should be applied to")
    currency_id = fields.Many2one('res.currency', related='payslip_id.currency_id')
    ytd = fields.Monetary(string='YTD')
    department_id = fields.Many2one(related='payslip_id.department_id')
    job_id = fields.Many2one(related='payslip_id.job_id')
    sex = fields.Selection(related='version_id.sex', string="Sex")
    resource_calendar_id = fields.Many2one(related='version_id.resource_calendar_id', string="Working Hours")
    reference_calendar_id = fields.Many2one(related='resource_calendar_id.reference_calendar_id')
    payslip_run_id = fields.Many2one(related='payslip_id.payslip_run_id')
    company_id = fields.Many2one('res.company', string='Company', related='employee_id.company_id')
    period_start_date = fields.Date(string="Period Start", compute='_compute_period_start_date')
    period_end_date = fields.Date(string="Period End", compute='_compute_period_end_date')
    category_options_ids = fields.Many2many('hr.salary.rule.category', string="Options")
    category_ids = fields.Many2many(
        related='work_entry_type_id.category_ids', string="Categories",
        groups='hr_payroll.group_hr_payroll_user')

    @api.depends(
        'work_entry_type_id', 'payslip_id', 'payslip_id.struct_id',
        'payslip_id.employee_id', 'payslip_id.version_id', 'payslip_id.struct_id', 'payslip_id.date_from', 'payslip_id.date_to')
    def _compute_is_paid(self):
        for worked_days in self:
            worked_days.is_paid = worked_days.work_entry_type_id.amount_rate != 0

    @api.depends('payslip_id.worked_days_line_ids.version_id.work_time_rate', 'payslip_id.sum_worked_hours')
    def _compute_fte(self):
        for version, worked_days in self.grouped('version_id').items():
            work_time_rate = version.work_time_rate
            for payslip, worked_days_by_payslip in worked_days.grouped('payslip_id').items():
                sum_worked_hours = payslip.sum_worked_hours
                for worked_day in worked_days_by_payslip:
                    work_rate = worked_day.number_of_hours / sum_worked_hours if sum_worked_hours else 1
                    worked_day.fte = work_time_rate * work_rate

    @api.depends(
        'is_paid', 'number_of_hours', 'payslip_id', 'version_id.wage', 'version_id.hourly_wage', 'payslip_id.sum_worked_hours',
        'work_entry_type_id.amount_rate', 'work_entry_type_id.is_extra_hours')
    def _compute_amount(self):
        all_calendar_periods = dict()
        for payslip_id in self.grouped('payslip_id'):
            date_from, date_to = payslip_id.date_from, payslip_id.date_to
            if not date_from or not date_to:
                continue
            all_worked_day_line_versions = payslip_id.worked_days_line_ids.version_id
            for version in all_worked_day_line_versions:
                calendar = version.resource_calendar_id
                if calendar._is_flexible():
                    continue
                version_start, version_end = version.date_start or date_from, version.date_end or date_to
                old_period = all_calendar_periods.get(calendar, (version_start, version_end))
                all_calendar_periods[version] = (
                    min(version_start, old_period[0], date_from),
                    max(version_end, old_period[1], date_to),
                    calendar,
                )

        work_intervals_per_version = dict()
        for version, (date_from, date_to, calendar) in all_calendar_periods.items():
            ctz = ZoneInfo(version._get_tz())
            dt_from = datetime.combine(date_from, time.min, ctz)
            dt_to = datetime.combine(date_to, time.max, ctz)
            work_intervals_per_version[version] = calendar._work_intervals_batch(dt_from, dt_to, compute_leaves=False)[False]

        work_times_per_payslip = dict()
        for payslip_id in self.grouped('payslip_id'):
            for version in payslip_id.worked_days_line_ids.grouped('version_id'):
                date_from, date_to = payslip_id.date_from, payslip_id.date_to
                work_time = 0
                if date_from and date_to:
                    calendar = version.resource_calendar_id
                    if calendar and not version.sudo()._is_flexible():
                        tz = ZoneInfo(version._get_tz())
                        time_start, time_end = datetime.combine(date_from, time.min, tz), datetime.combine(date_to, time.max, tz)
                        sum_work_time = 0
                        for interval in work_intervals_per_version.get(version):
                            if interval[0] <= time_end and interval[1] >= time_start:
                                sum_work_time += (interval[1] - interval[0]).total_seconds()
                        work_time = sum_work_time / 3600
                    else:
                        work_time = sum(wd.number_of_hours for wd in payslip_id.worked_days_line_ids if not wd.work_entry_type_id.is_extra_hours)
                work_times_per_payslip[payslip_id] = float_round(work_time, 2)

        for worked_days in self:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or worked_days.code in '000.00':
                worked_days.amount = 0
                continue
            version = worked_days.version_id
            amount_rate = worked_days.work_entry_type_id.amount_rate
            if version.wage_type == "hourly":
                hourly_rate = version._get_contract_wage()
            else:
                hourly_rate = version._get_contract_wage() / (work_times_per_payslip[worked_days.payslip_id] or 1)
            worked_days.amount = hourly_rate * worked_days.number_of_hours * amount_rate if worked_days.is_paid else 0

    def _is_incomplete_day(self):
        self.ensure_one()
        work_hours = self.payslip_id._get_worked_day_lines_hours_per_day(self.version_id)
        # For refunds number of days is negative
        return abs(self.number_of_days) < 1 or float_round(self.number_of_hours / self.number_of_days, 2) < work_hours

    @api.depends('work_entry_type_id', 'number_of_days', 'number_of_hours', 'payslip_id')
    @api.depends_context('lang')
    def _compute_name(self):
        if not self.payslip_id:
            return

        for worked_days in self:
            worked_days.name = worked_days.custom_name or worked_days._get_default_name()

    def _inverse_name(self):
        for worked_days in self:
            if worked_days.name != worked_days._get_default_name():
                worked_days.custom_name = worked_days.name
            else:
                worked_days.custom_name = False

    @api.depends('version_id.date_start', 'payslip_id.date_from')
    def _compute_period_start_date(self):
        for worked_day in self:
            worked_day.period_start_date = max(worked_day.version_id.date_start, worked_day.payslip_id.date_from)

    @api.depends('version_id.date_end', 'payslip_id.date_to')
    def _compute_period_end_date(self):
        for worked_day in self:
            worked_day.period_end_date = min(worked_day.version_id.date_end or date.max, worked_day.payslip_id.date_to)

    def _get_default_name(self):
        self.ensure_one()
        type_name = self.work_entry_type_id.name or ''
        incomplete_day = self._is_incomplete_day()
        name = type_name + ('' if not incomplete_day else self.env._(' (Half-Day)') if self.work_entry_type_id.request_unit == 'half_day' else self.env._(' (Custom Hours)'))
        if self.category_options_ids:
            options = ', '.join(self.category_options_ids.mapped('name'))
            name += self.env._(' (%s)', options)
        return name
