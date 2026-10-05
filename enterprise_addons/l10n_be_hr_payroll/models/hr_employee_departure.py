# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, time
import math

from dateutil import rrule
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrEmployeeDeparture(models.Model):
    _inherit = 'hr.employee.departure'

    # Fields related to the Notice period
    l10n_be_first_contract_id = fields.Many2one('hr.version', string='First Contract',
        compute='_compute_first_contract', store=True)
    l10n_be_first_contract_date = fields.Date(string='In the Company Since',
        compute='_compute_first_contract', store=True)
    l10n_be_reason_code = fields.Integer(related='departure_reason_id.l10n_be_reason_code')
    l10n_be_seniority_description = fields.Char(string='Seniority', compute='_compute_seniority_description')
    l10n_be_thirteen_month_eligible = fields.Boolean(
        string='Eligible for a 13th Month upon Departure',
        compute='_compute_l10n_be_thirteen_month_eligible')
    l10n_be_termination_documents_generated = fields.Boolean()

    l10n_be_salary_december_2013 = fields.Selection([
        ('inferior', 'Gross annual salary < 32.254 €'),
        ('superior', 'Gross annual salary > 32.254 €')
        ], string='Gross Annual Salary as of December 31, 2013', required=True, default='superior')
    l10n_be_salary_visibility = fields.Boolean(compute='_compute_notice_duration', store=True)
    l10n_be_notice_duration_month_before_2014 = fields.Integer('Notice Duration in month',
        compute='_compute_notice_duration', store=True, readonly=False)
    l10n_be_notice_duration_week_after_2014 = fields.Integer('Notice Duration in weeks',
        compute='_compute_notice_duration', store=True, readonly=False)
    l10n_be_notice_duration = fields.Integer('Actual Notice Duration',
        compute='_compute_actual_notice_duration', store=True, readonly=False)
    l10n_be_notice_period_theoretical_end = fields.Date(
        string='Notice Period Theoretical End',
        compute='_compute_notice_theoretical_end', store=True)

    l10n_be_notice_period_start = fields.Date(
        string='Notice Period Start',
        compute='_compute_notice_period_start', store=True,
        help='First monday from the departure date (or the following open day if it is a public holiday).')

    l10n_be_notice_respect = fields.Selection([
        ('with', 'Works fully'),
        ('partial', 'Works partially'),
        ('without', "Doesn't work"),
        ], string='Respect of the notice period', required=True, default='with',
        help='Decides whether the employee will still work during his notice period or not.')

    # Fields related to the holiday attests
    l10n_be_payslip_n_ids = fields.Many2many(
        'hr.payslip', string='Payslips N', relation='holiday_attest_payslip_n_rel',
        compute='_compute_payslip_history')
    l10n_be_payslip_n_description = fields.Char(compute='_compute_payslips_description')
    l10n_be_payslip_n1_ids = fields.Many2many(
        'hr.payslip', string='Payslips N-1', relation='holiday_attest_payslip_n1_rel',
        compute='_compute_payslip_history')
    l10n_be_payslip_n1_description = fields.Char(compute='_compute_payslips_description')
    currency_id = fields.Many2one(related='employee_id.version_id.currency_id')
    l10n_be_egov3_code = fields.Char(related="employee_id.version_id.l10n_be_joint_committee_id.egov3_code")
    l10n_be_net_n = fields.Monetary('Yearly Gross (N)', compute='_compute_net', store=True,
        readonly=False, help="""
        Taking into account for remuneration:
            - Fixed and variable remuneration
            - Overtime worked
            - Benefits in kind and bonuses
            - Remuneration of statutory holidays occurring within 30 days of the end date of the contract
            - End-of-year bonus, 13th month or other similar amount
            - Beneficiary holdings
            - Various bonuses
        We draw your attention to the fact that this information is based on the data in Odoo and / or that you
        have introduced in Odoo and that it is important that they be accompanied by a verification on your part
        according to the particularities related to contract of the worker or your company which Odoo would not
        know.
        """
    )
    l10n_be_net_n1 = fields.Monetary(
        'Yearly Gross (N-1)',
        compute='_compute_net', store=True, readonly=False)
    l10n_be_fictitious_remuneration_n = fields.Monetary(
        'Remuneration fictitious current year', compute='_compute_fictitious_remuneration_n')
    l10n_be_fictitious_remuneration_n1 = fields.Monetary(
        'Remuneration fictitious previous year', compute='_compute_fictitious_remuneration_n1')
    l10n_be_gross_reference_remuneration_n = fields.Monetary(
        'Gross reference remuneration current year', compute='_compute_gross_reference_remuneration_n')
    l10n_be_gross_reference_remuneration_n1 = fields.Monetary(
        'Gross reference remuneration previous year', compute='_compute_gross_reference_remuneration_n1')

    l10n_be_time_off_line_ids = fields.One2many('l10n.be.employee.departure.holiday.attest.line', 'departure_id',
        string="Time Off", compute='_compute_time_off_line_ids', store=True, index='btree_not_null')

    l10n_be_professional_reclassification = fields.Selection(string='Professional Reclassification', selection=[
        ('general', 'General Scheme'),
        ('special', 'Special Scheme'),
        ('specific', 'Specific Scheme'),
        ('voluntary', 'Voluntary Scheme'),
    ], compute='_compute_professional_reclassification', store=True, readonly=False,
        help="Outplacement is defined as a set of services and guidance advice provided individually or in groups by a service provider, on behalf of an employer, to enable a worker to find employment with a new employer as quickly as possible or to develop a professional activity as a self-employed person. Contact your social secretariat for more information.")

    l10n_be_company_sector = fields.Selection(related="employee_id.version_id.payroll_config_id.l10n_be_sector")

    @api.depends('l10n_be_notice_duration_week_after_2014', 'employee_id.birthday', 'departure_date', 'l10n_be_first_contract_date')
    def _compute_professional_reclassification(self):
        for departure in self:
            if departure.country_code != 'BE' or not departure.employee_id:
                departure.l10n_be_professional_reclassification = False
                continue
            if departure.l10n_be_notice_duration_week_after_2014 >= 30:
                departure.l10n_be_professional_reclassification = 'general'
            elif departure.departure_date and departure.l10n_be_first_contract_date\
                and departure.employee_id._get_age(departure.departure_date) >= 45\
                and (relativedelta(departure.departure_date, departure.l10n_be_first_contract_date).years):
                departure.l10n_be_professional_reclassification = 'special'
            else:
                departure.l10n_be_professional_reclassification = False

    @api.constrains('l10n_be_professional_reclassification', 'l10n_be_notice_duration_week_after_2014', 'employee_id', 'departure_date')
    def _check_professional_reclassification(self):
        for departure in self:
            if departure.l10n_be_professional_reclassification == 'general' and departure.l10n_be_notice_duration_week_after_2014 and departure.l10n_be_notice_duration_week_after_2014 < 30:
                raise ValidationError(_("You cannot select the General Scheme if the notice period is less than 30 weeks."))
            if departure.l10n_be_professional_reclassification == 'specific':
                if departure.l10n_be_notice_duration_week_after_2014 > 30:
                    raise ValidationError(_("You cannot select the Specific Scheme if the notice period is more than 30 weeks."))
                if departure.employee_id._get_age(departure.departure_date) < 45:
                    raise ValidationError(_("You cannot select the Specific Scheme if the employee is less than 45 years old."))
                if departure.l10n_be_company_sector and departure.l10n_be_company_sector.startswith('public'):
                    raise ValidationError(_("You cannot select the Specific Scheme if the company sector is public."))
                if departure.employee_id.l10n_be_scale_seniority < 1:
                    raise ValidationError(_("You cannot select the Specific Scheme if the employee has less than 1 year of seniority."))

    @api.depends('employee_id')
    def _compute_first_contract(self):
        self.l10n_be_first_contract_id = False
        self.l10n_be_first_contract_date = False
        for departure in self.filtered(lambda dep: dep.country_code == 'BE'):
            in_contract_versions = departure.employee_id.version_ids.filtered(
                lambda v: v.contract_date_start and not v.is_PFI())
            if not in_contract_versions:
                continue
            departure.l10n_be_first_contract_id = in_contract_versions[0]
            departure.l10n_be_first_contract_date = departure.employee_id.l10n_be_fictive_hire_date or in_contract_versions[0].contract_date_start

    @api.depends('l10n_be_first_contract_date', 'dismissal_date')
    def _compute_seniority_description(self):
        for notice in self:
            difference = relativedelta(notice.departure_date, notice.l10n_be_first_contract_date)
            difference += relativedelta(years=notice.employee_id.l10n_be_scale_seniority, months=notice.employee_id.l10n_be_scale_seniority_months)
            if difference.years == 0:
                notice.l10n_be_seniority_description = self.env._('%(months)s months', months=difference.months)
            else:
                notice.l10n_be_seniority_description = self.env._(
                    '%(years)s years and %(months)s months',
                    months=difference.months, years=difference.years)

    @api.depends('country_code', 'l10n_be_egov3_code', 'l10n_be_reason_code', 'l10n_be_first_contract_date', 'departure_date')
    def _compute_l10n_be_thirteen_month_eligible(self):
        for departure in self:
            departure.l10n_be_thirteen_month_eligible = departure._get_l10n_be_thirteen_month_eligible()

    def _get_l10n_be_thirteen_month_eligible(self):
        self.ensure_one()
        if (
            self.country_code != 'BE'
            or self.l10n_be_egov3_code != '200'
            or not self.l10n_be_first_contract_date
            or not self.departure_date
        ):
            return False
        # fired, fired: serious misconduct, retired, fired/resigned: early retirement
        if self.l10n_be_reason_code in (342, 355, 340, 353, 354, 358, 359):
            required_seniority = self.env['hr.rule.parameter']._get_parameter_from_code(
                'cp200_thirteen_month_six_months_required_seniority', self.departure_date)
        else:
            required_seniority = self.env['hr.rule.parameter']._get_parameter_from_code(
                'cp200_thirteen_month_three_years_required_seniority', self.departure_date)
        return self.departure_date >= self.l10n_be_first_contract_date + relativedelta(**required_seniority)

    @api.depends('l10n_be_first_contract_id', 'departure_reason_id', 'l10n_be_salary_december_2013',
        'l10n_be_notice_period_start', 'employee_id.l10n_be_scale_seniority', 'employee_id.l10n_be_scale_seniority_months')
    def _compute_notice_duration(self):
        self.l10n_be_salary_visibility = False
        self.l10n_be_notice_duration_month_before_2014 = 0
        self.l10n_be_notice_duration_week_after_2014 = 0
        for departure in self.filtered('l10n_be_first_contract_id'):
            departure_code = departure.l10n_be_reason_code
            first_contract_date = departure.l10n_be_first_contract_date
            first_contract_date += relativedelta(
                years=-(departure.employee_id.l10n_be_scale_seniority or 0),
                months=-(departure.employee_id.l10n_be_scale_seniority_months or 0)
            )
            years_delta = relativedelta(date(2013, 12, 31), first_contract_date)
            difference_in_years = years_delta.years + years_delta.months / 12 + years_delta.days / 365
            # Part I
            if departure_code in (342, 358, 359) and difference_in_years > 0:  # fired
                departure.l10n_be_salary_visibility = True
                if departure.l10n_be_salary_december_2013 == 'inferior':
                    departure.l10n_be_notice_duration_month_before_2014 = math.ceil(difference_in_years / 5.0) * 3.0
                else:
                    departure.l10n_be_notice_duration_month_before_2014 = max(math.ceil(difference_in_years), 3)
            # Part II
            if departure_code in (340, 342, 343, 358, 359):  # retired, fired or resigned
                first_day_since_2014 = max(date(2014, 1, 1), first_contract_date)
                period_since_2014 = relativedelta(departure.l10n_be_notice_period_start, first_day_since_2014)
                period_in_month = period_since_2014.months + period_since_2014.years * 12

                on_economic_unemployment = bool(departure.employee_id.current_version_id.resource_calendar_id.attendance_ids.filtered(lambda a: a.work_entry_type_id.l10n_be_economic_unemployment))
                if on_economic_unemployment and departure_code == 343:
                    departure.l10n_be_notice_duration_week_after_2014 = 0
                    continue
                duration_parameter = 'l10n_be_duration_notice_resigned' if departure_code in [343, 340] else 'l10n_be_duration_notice_fired'
                current_version_start = departure.employee_id.current_version_id.date_start
                rule_param_date = date(2026, 7, 31) if current_version_start < date(2026, 8, 1) and departure.dismissal_date >= date(2026, 8, 1) else departure.dismissal_date
                duration_notice = self.env['hr.rule.parameter']._get_parameter_from_code(duration_parameter, rule_param_date)
                if departure_code != 343:
                    # Once you reach 24 years (288 months) of seniority,
                    # you have one more week in the notice period per year
                    # starting at 66 weeks for the 24th year.
                    threshold, duration = duration_notice[-1]
                    if period_in_month >= threshold:
                        departure.l10n_be_notice_duration_week_after_2014 = duration + 1 + period_in_month // 12 - threshold / 12
                        continue
                for seniority_upper_bound, duration in duration_notice:
                    if period_in_month < seniority_upper_bound:
                        departure.l10n_be_notice_duration_week_after_2014 = duration
                        break

    @api.depends('l10n_be_notice_period_start', 'departure_date')
    def _compute_actual_notice_duration(self):
        for departure in self:
            if not departure.l10n_be_notice_period_start or not departure.departure_date:
                departure.l10n_be_notice_duration = False
            else:
                weeks = rrule.rrule(rrule.WEEKLY,
                    dtstart=datetime.combine(departure.l10n_be_notice_period_start, time.min),
                    until=datetime.combine(departure.departure_date, time.max))
                departure.l10n_be_notice_duration = weeks.count()

    @api.depends('dismissal_date', 'l10n_be_notice_respect', 'l10n_be_reason_code', 'l10n_be_first_contract_id')
    def _compute_notice_period_start(self):
        def next_monday(initial_date):
            return initial_date + relativedelta(days=7 - initial_date.weekday())

        public_holiday_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday')
        for departure in self:
            if not departure.dismissal_date:
                continue
            remaining_economic_unemployment_days = 0
            on_economic_unemployment = bool(departure.employee_id.current_version_id.resource_calendar_id.attendance_ids.filtered(lambda a: a.work_entry_type_id.l10n_be_economic_unemployment))
            contract_end_date = departure.employee_id.current_version_id.contract_date_end
            if not contract_end_date or contract_end_date < departure.dismissal_date:
                contract_end_date = departure.dismissal_date
            if on_economic_unemployment:
                remaining_economic_unemployment_days = (contract_end_date - departure.dismissal_date).days
            if departure.country_code != 'BE' or not departure.l10n_be_first_contract_id or\
                    departure.l10n_be_notice_respect == 'without' or departure.l10n_be_reason_code in (350, 351):
                departure.l10n_be_notice_period_start = departure.dismissal_date
            elif departure.l10n_be_reason_code in (342, 358, 359):
                # We can only take the next monday that has at least 3 calendar days (Monday to Saturday except public
                # holidays) between the departure date and the start of the notice period
                public_leaves = self.employee_id.version_id.resource_calendar_id.global_leave_ids.filtered(
                    lambda leave: leave.work_entry_type_id == public_holiday_type)
                public_holidays_dates = (d.date() for d in public_leaves.mapped('date_from'))
                calendar_days = 0
                current_date = departure.dismissal_date + relativedelta(days=1 + remaining_economic_unemployment_days)
                while calendar_days < 3:
                    if current_date not in public_holidays_dates and current_date.weekday() != 6:
                        calendar_days += 1
                    current_date = current_date + relativedelta(days=1)
                departure.l10n_be_notice_period_start = next_monday(current_date)
            else:
                departure.l10n_be_notice_period_start = next_monday(departure.dismissal_date)

    @api.depends(
        "country_code", "l10n_be_reason_code", "l10n_be_first_contract_id",
        "l10n_be_notice_period_start", "l10n_be_notice_duration_week_after_2014",
        "l10n_be_notice_duration_month_before_2014",
    )
    def _compute_notice_theoretical_end(self):
        for departure in self:
            departure.l10n_be_notice_period_theoretical_end = departure.l10n_be_notice_period_start
            if (
                departure.country_code != 'BE'
                or not departure.l10n_be_first_contract_id
                or not departure.l10n_be_notice_period_start
                or departure.l10n_be_reason_code in (350, 351)
            ):
                continue
            # the notice period computation is different for prestated time before vs after 2014
            weeks_before_2014 = departure.l10n_be_notice_duration_month_before_2014 / 12 * 52
            notice_period_weeks = weeks_before_2014 + departure.l10n_be_notice_duration_week_after_2014
            # when the employee leaves if the notice period was fully prestated
            departure.l10n_be_notice_period_theoretical_end += relativedelta(weeks=notice_period_weeks, days=-1)

    @api.depends(
        "country_code", "l10n_be_reason_code", "l10n_be_first_contract_id",
        "l10n_be_notice_period_start", "l10n_be_notice_respect",
        "l10n_be_notice_period_theoretical_end",
    )
    def _compute_departure_date(self):
        # Skip calling super only when the case is partial and already has a valid date to preserve user input.
        partial_departures = self.filtered(lambda d: d.country_code == 'BE' and d.l10n_be_notice_respect == 'partial'
            and d.departure_date and d.dismissal_date and d.departure_date > d.dismissal_date)
        super(HrEmployeeDeparture, self - partial_departures)._compute_departure_date()
        for departure in self - partial_departures:
            if (
                departure.country_code != 'BE'
                or not departure.l10n_be_first_contract_id
                or not departure.l10n_be_notice_period_start
                or departure.l10n_be_notice_respect == 'without'
            ):
                continue

            departure.departure_date = departure.l10n_be_notice_period_start

            # departure_date is set to dismissal_date by default
            if departure.l10n_be_reason_code not in (350, 351) and departure.l10n_be_notice_respect != 'without':
                # meant to be manually changed if notice_respect == 'partial'
                departure.departure_date = departure.l10n_be_notice_period_theoretical_end

    @api.depends('employee_id', 'country_code', 'departure_date', 'employee_id.slip_ids.state')
    def _compute_payslip_history(self):
        struct_codes = ['BETHIRTEEN', 'BEMONTHLY']
        for departure in self:
            if not departure.employee_id or departure.country_code != 'BE' or not departure.departure_date:
                departure.update({
                    'l10n_be_payslip_n_ids': [(5, 0, 0)],
                    'l10n_be_payslip_n1_ids': [(5, 0, 0)],
                })
                continue
            departure.l10n_be_payslip_n_ids = [(4, p.id) for p in departure.employee_id._get_payslips_for_year(
                departure.departure_date.year, struct_codes
            )]
            departure.l10n_be_payslip_n1_ids = [(4, p.id) for p in departure.employee_id._get_payslips_for_year(
                departure.departure_date.year - 1, struct_codes
            )]

    @api.depends('l10n_be_payslip_n_ids', 'l10n_be_payslip_n1_ids')
    def _compute_payslips_description(self):
        for departure in self:
            departure.l10n_be_payslip_n_description = self.env._("(%s payslips)", len(departure.l10n_be_payslip_n_ids))
            departure.l10n_be_payslip_n1_description = self.env._("(%s payslips)", len(departure.l10n_be_payslip_n1_ids))

    @api.depends('l10n_be_payslip_n_ids', 'l10n_be_payslip_n1_ids')
    def _compute_net(self):
        onss_gross_codes = self.env['hr.payslip']._get_salary_wage_line_codes()
        for departure in self:
            departure.l10n_be_net_n = 0
            if departure.l10n_be_payslip_n_ids:
                line_values = departure.l10n_be_payslip_n_ids._origin._get_line_values(onss_gross_codes, compute_sum=True)
                departure.l10n_be_net_n = sum(line_values[code]['sum']['total'] for code in onss_gross_codes)
            departure.l10n_be_net_n1 = 0
            if departure.l10n_be_payslip_n1_ids:
                line_values = departure.l10n_be_payslip_n1_ids._origin._get_line_values(onss_gross_codes, compute_sum=True)
                departure.l10n_be_net_n1 = sum(line_values[code]['sum']['total'] for code in onss_gross_codes)

    @api.depends('employee_id', 'country_code', 'departure_date')
    def _compute_time_off_line_ids(self):
        for departure in self:
            if not departure.employee_id or departure.country_code != 'BE' or not departure.departure_date:
                departure.update({
                    'l10n_be_time_off_line_ids': [(5, 0, 0)],
                })
                continue

            work_entry_types = (
                self.env.ref('hr_work_entry.generic_work_entry_type_legal_leave') +
                self.env.ref('hr_work_entry.be_work_entry_type_legal_leave') +
                self.env.ref('hr_work_entry.l10n_be_work_entry_type_european') +
                self.env.ref('hr_work_entry.l10n_be_work_entry_type_youth_time_off') +
                self.env.ref('hr_work_entry.l10n_be_work_entry_type_senior_time_off') +
                self.env.ref('hr_work_entry.l10n_be_work_entry_type_postponed_paid_time_off_n1') +
                self.env.ref('hr_work_entry.l10n_be_work_entry_type_postponed_paid_time_off_n2')
            )

            current_year = departure.departure_date.replace(month=1, day=1)
            years = [current_year - relativedelta(years=i) for i in range(3)]

            domain = [
                ('employee_id', '=', departure.employee_id.id),
                ('date_from', '>=', current_year - relativedelta(years=3)),
                ('date_from', '<=', departure.departure_date),
                ('state', '=', 'validate'),
                ('work_entry_type_id', 'in', work_entry_types.ids),
            ]
            all_leaves = self.env['hr.leave']._read_group(
                    domain=domain,
                    groupby=['date_from:year', 'work_entry_type_id'],
                    aggregates=['id:recordset'],
                )
            leaves_per_year_lt = {(year.year, w_e_type): leaves for year, w_e_type, leaves in all_leaves}

            all_allocations = self.env['hr.leave.allocation']._read_group(
                    domain=domain,
                    groupby=['date_from:year', 'work_entry_type_id'],
                    aggregates=['id:recordset'],
                )
            allocations_per_year_lt = {(year.year, w_e_type): allocations for year, w_e_type, allocations in all_allocations}

            lines = []
            for start_date in years:
                for work_entry_type in work_entry_types:
                    leaves = leaves_per_year_lt.get((start_date.year, work_entry_type), self.env['hr.leave'])
                    leave_allocations = allocations_per_year_lt.get((start_date.year, work_entry_type), self.env['hr.leave.allocation'])
                    if leaves or leave_allocations:
                        lines.append(
                            {
                                'year': start_date.year,
                                'work_entry_type_id': work_entry_type.id,
                                'leave_allocation_count': sum(leave_allocations.mapped('number_of_days')),
                                'leave_count': sum(leaves.mapped('number_of_days')),
                            })

            lines = sorted(lines, key=lambda l: (l['work_entry_type_id'], l['year']))
            departure.l10n_be_time_off_line_ids = [(5, 0, 0)] + [(0, 0, l) for l in lines]

    @api.depends('l10n_be_payslip_n_ids')
    def _compute_fictitious_remuneration_n(self):
        for departure in self:
            if not departure.employee_id or departure.country_code != 'BE' or not departure.departure_date:
                departure.l10n_be_fictitious_remuneration_n = 0
                continue
            departure.l10n_be_fictitious_remuneration_n = departure.employee_id._get_fictitious_remuneration_previous_year(
                departure.departure_date + relativedelta(years=1),
                departure.l10n_be_payslip_n_ids)

    @api.depends('l10n_be_payslip_n1_ids')
    def _compute_fictitious_remuneration_n1(self):
        for departure in self:
            if not departure.employee_id or departure.country_code != 'BE' or not departure.departure_date:
                departure.l10n_be_fictitious_remuneration_n1 = 0
                continue
            departure.l10n_be_fictitious_remuneration_n1 = departure.employee_id._get_fictitious_remuneration_previous_year(
                departure.departure_date,
                departure.l10n_be_payslip_n1_ids)

    @api.depends('l10n_be_net_n', 'l10n_be_fictitious_remuneration_n')
    def _compute_gross_reference_remuneration_n(self):
        for departure in self:
            departure.l10n_be_gross_reference_remuneration_n = departure.l10n_be_net_n + departure.l10n_be_fictitious_remuneration_n

    @api.depends('l10n_be_net_n1', 'l10n_be_fictitious_remuneration_n1')
    def _compute_gross_reference_remuneration_n1(self):
        for departure in self:
            departure.l10n_be_gross_reference_remuneration_n1 = departure.l10n_be_net_n1 + departure.l10n_be_fictitious_remuneration_n1

    def action_register(self):
        self._process_fixed_term_departure()
        res = super().action_register()
        self.filtered(lambda departure: departure.country_code == 'BE')._compute_net()
        return res

    def action_generate_termination_payslip(self):
        self.ensure_one()
        payslip = self._generate_termination_payslip()
        return {
            'name': self.env._('Termination Payslips'),
            'view_mode': 'form',
            'res_model': 'hr.payslip',
            'res_id': payslip.id,
            'type': 'ir.actions.act_window',
            'views': [[False, 'form']],
        }

    def _process_fixed_term_departure(self):
        fixed_term_reason = self.env.ref(
            'l10n_be_hr_payroll.departure_contract_end_fixed_term',
            raise_if_not_found=False,
        )
        for departure in self:
            if departure.country_code != 'BE' or not departure.employee_id:
                continue

            if not fixed_term_reason or departure.departure_reason_id != fixed_term_reason:
                continue

            version = departure.employee_id.sudo()._get_version(departure.departure_date)
            if version:
                # write from hr_employee model so the field is tracked in the chatter
                departure.employee_id.with_context(version_id=version.id).write({'fixed_term': True})

    def _generate_termination_payslip(self):
        self.ensure_one()
        version = self._get_termination_version()
        is_worker = version.is_worker()
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        existing_payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', struct_id.id),
            ('date_from', '=', self.l10n_be_notice_period_start),
            ('state', '!=', 'cancel')
        ], limit=1)

        if existing_payslip:
            return existing_payslip

        termination_payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee_id.id,
            'date_from': self.l10n_be_notice_period_start,
            'date_to': self.l10n_be_notice_period_start,
            'struct_id': struct_id.id,
        })
        termination_payslip.worked_days_line_ids = [(5, 0, 0)]

        version = termination_payslip.version_id

        weeks = self.l10n_be_notice_duration_week_after_2014
        if self.l10n_be_notice_respect == 'partial':
            weeks -= self.l10n_be_notice_duration

        remaining_days = 0
        if is_worker and self.l10n_be_notice_period_start and self.departure_date:
            total_days = (self.departure_date - self.l10n_be_notice_period_start).days
            remaining_days = total_days % 7

        termination_payslip._set_input_values({
            'ND_MONTH': 0 if is_worker else self.l10n_be_notice_duration_month_before_2014,
            'ND_WEEK': weeks,
            'ND_DAY': remaining_days,
            'UNREASONABLE_DISMISSAL': 0,
            'NON_RESPECT_MOTIVATION': 0,
            'YEAREND_BONUS': self._get_termination_year_end_bonus(version, is_worker),
            'RESIDENCE': 0,
            'EXPATRIATE': 0,
            'VARIABLE_SALARY': termination_payslip._get_last_year_average_variable_revenues() * 12,
            'BENEFIT_IN_KIND': 0,
            'STOCK_OPTION': termination_payslip._get_last_year_average_warrant_revenues(),
            'SPECIFIC_RULES': 0,
            'OTHER': 0,
        })

        termination_payslip.compute_sheet()
        return termination_payslip

    def action_generate_termination_thirteen_month(self):
        self.ensure_one()
        payslip = self._generate_termination_thirteen_month()
        return {
            'name': self.env._('13th Month Payslip'),
            'view_mode': 'form',
            'res_model': 'hr.payslip',
            'res_id': payslip.id,
            'type': 'ir.actions.act_window',
            'views': [[False, 'form']],
        }

    def _generate_termination_thirteen_month(self):
        self.ensure_one()
        if not self.l10n_be_thirteen_month_eligible:
            raise UserError(self.env._("This employee is not eligible for a 13th month upon departure."))
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
        existing_payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', struct_id.id),
            ('date_to', '=', self.departure_date),
            ('state', '!=', 'cancel')
        ], limit=1)

        if existing_payslip:
            return existing_payslip

        thirteen_month_payslip = self.env['hr.payslip'].create({
            'name': '%s - %s' % (struct_id.payslip_name, self.employee_id.legal_name),
            'employee_id': self.employee_id.id,
            'date_from': self.departure_date,
            'date_to': self.departure_date,
            'struct_id': struct_id.id,
        })
        thirteen_month_payslip.compute_sheet()
        return thirteen_month_payslip

    def _get_termination_year_end_bonus(self, version, is_worker):
        self.ensure_one()
        if not is_worker:
            return version._get_contract_wage()
        if not self.departure_date:
            return 0
        return version._l10n_be_get_monthly_wage(self.departure_date.year)

    def action_generate_termination_holidays(self):
        self.ensure_one()
        payslips = self._generate_termination_holidays()
        return {
            'name': self.env._('Holiday Attests Payslips'),
            'view_mode': 'list',
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', payslips.ids)],
            'views': [[False, 'list'], [False, 'form']],
        }

    def _generate_termination_holidays(self):
        self.ensure_one()
        struct_n_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        struct_n1_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')

        payslips = self.env['hr.payslip']
        target_date_from = self.departure_date + relativedelta(day=1)
        termination_payslip_n = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', struct_n_id.id),
            ('date_from', '=', target_date_from),
            ('state', '!=', 'cancel')
        ], limit=1)

        if not termination_payslip_n:
            termination_payslip_n = self.env['hr.payslip'].create({
                'employee_id': self.employee_id.id,
                'struct_id': struct_n_id.id,
                'date_from': target_date_from,
            })
            termination_payslip_n.worked_days_line_ids = [(5, 0, 0)]

            # As regards the recovery of amounts for European holidays (“additional holidays”), the
            # amount paid in advance is
            # - or recovered from the double vacation pay (part 85%) for the following year;
            # - or, when the worker leaves, on the amount of the exit pay. The legislation does not
            # specifically state whether, in the event of an exit, the recovery is on the single or
            # the double, but, in order to be consistent, I would do the recovery on the double
            # (85% of 7.67 %).
            # In addition, when "additional" vacation has been taken, the vacation certificate must
            # mention: the number of days already granted + the related gross allowance.
            current_year_start = self.departure_date.replace(month=1, day=1)
            current_year_end = self.departure_date.replace(month=12, day=31)
            payslips_n = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '>=', current_year_start),
                ('date_to', '<=', current_year_end),
                ('state', 'in', ['draft', 'validated', 'paid'])])
            european_wds = payslips_n.worked_days_line_ids.filtered(lambda wd: wd.code == '142.20')
            european_leaves_amount = sum(european_wds.mapped('amount'))
            european_leaves_days = sum(european_wds.mapped('number_of_days'))
            european_amount_to_deduct = max(european_leaves_amount, 0)

            termination_payslip_n._set_input_values({
                'EU_LEAVE_DEDUC': european_amount_to_deduct,
                'EUROPEAN_DAYS': european_leaves_days,
                'PPTO1': 0,
                'PPTO2': 0,
                'TIME_OFF_TAKEN': 0,
                'ALLOCATION': 0,
                'GROSS_REF': self.l10n_be_gross_reference_remuneration_n,
            })

            termination_payslip_n.compute_sheet()
            termination_payslip_n.name = '%s - %s' % (struct_n_id.payslip_name, self.employee_id.legal_name)
        payslips += termination_payslip_n

        departure_year = self.departure_date.year if self.departure_date else fields.Date.today().year
        worked_in_n1 = (self.l10n_be_first_contract_date and self.l10n_be_first_contract_date.year < departure_year)

        if worked_in_n1:
            termination_payslip_n1 = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('struct_id', '=', struct_n1_id.id),
                ('date_from', '=', target_date_from),
                ('state', '!=', 'cancel')
            ], limit=1)

            if not termination_payslip_n1:
                termination_payslip_n1 = self.env['hr.payslip'].create({
                    'employee_id': self.employee_id.id,
                    'struct_id': struct_n1_id.id,
                    'date_from': target_date_from,
                })
                termination_payslip_n1.worked_days_line_ids = [(5, 0, 0)]

                # As regards the recovery of amounts for European holidays (“additional holidays”), the
                # amount paid in advance is
                # - or recovered from the double vacation pay (part 85%) for the following year;
                # - or, when the worker leaves, on the amount of the exit pay. The legislation does not
                # specifically state whether, in the event of an exit, the recovery is on the single or
                # the double, but, in order to be consistent, I would do the recovery on the double
                # (85% of 7.67 %).
                # In addition, when "additional" vacation has been taken, the vacation certificate must
                # mention: the number of days already granted + the related gross allowance.
                double_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
                double_holiday_n = self.env['hr.payslip'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('date_to', '>=', current_year_start),
                    ('state', 'in', ['validated', 'paid', 'draft']),
                    ('struct_id', '=', double_structure.id)])
                # Part already deducted on the double holiday for year N
                double_amount_n = - double_holiday_n._get_line_values(['EU_LEAVE_DEDUC'], compute_sum=True)['EU_LEAVE_DEDUC']['sum']['total']
                # Original Amount to deduct
                payslips_n1 = self.env['hr.payslip'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('date_to', '>=', current_year_start + relativedelta(years=-1)),
                    ('date_from', '<', current_year_start),
                    ('state', 'in', ['validated', 'paid'])])
                postponed_time_off_n1_remaining = 0
                postponed_time_off_n2_remaining = 0
                postponed_time_off_n1_total = 0
                postponed_time_off_n2_total = 0
                time_off_allocated = 0
                time_off_taken = 0
                for line in self.l10n_be_time_off_line_ids:
                    if line.year == current_year_start.year:
                        if line.work_entry_type_id.code == '016.00':
                            time_off_allocated += line.leave_allocation_count
                            time_off_taken += line.leave_count
                        elif line.work_entry_type_id.code == '142.24':
                            postponed_time_off_n1_remaining += line.leave_allocation_count - line.leave_count
                            postponed_time_off_n1_total += line.leave_allocation_count
                        elif line.work_entry_type_id.code == '142.26':
                            postponed_time_off_n2_remaining += line.leave_allocation_count - line.leave_count
                            postponed_time_off_n2_total += line.leave_allocation_count

                european_wds = payslips_n1.worked_days_line_ids.filtered(lambda wd: wd.code == '142.20')
                european_leaves_amount = sum(european_wds.mapped('amount'))
                european_leaves_days = sum(european_wds.mapped('number_of_days'))
                european_amount_to_deduct = max(european_leaves_amount - double_amount_n, 0)

                termination_payslip_n1._set_input_values({
                    'EU_LEAVE_DEDUC': european_amount_to_deduct,
                    'EUROPEAN_DAYS': european_leaves_days,
                    'PPTO1': postponed_time_off_n1_remaining,
                    'PPTO2': postponed_time_off_n2_remaining,
                    'TPPTO1': postponed_time_off_n1_total,
                    'TPPTO2': postponed_time_off_n2_total,
                    'TIME_OFF_TAKEN': time_off_taken,
                    'ALLOCATION': time_off_allocated,
                    'GROSS_REF': self.l10n_be_gross_reference_remuneration_n1,
                })

                termination_payslip_n1.compute_sheet()
                termination_payslip_n1.name = '%s - %s' % (struct_n1_id.payslip_name, self.employee_id.legal_name)

            payslips += termination_payslip_n1
        return payslips

    def _get_termination_version(self):
        self.ensure_one()
        reference_date = self.dismissal_date or self.departure_date or fields.Date.today()
        return self.employee_id._get_version(reference_date)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        res._process_fixed_term_departure()

        for departure in res:
            if departure.country_code != 'BE' or not departure.employee_id or not departure.l10n_be_professional_reclassification:
                continue
            departure.employee_id.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=departure.departure_date + relativedelta(days=15),
                note=self.env._('Outplacement: A professional reemployment assistance offer must be proposed to this employee (%(professional_reclassification)s).',
                    professional_reclassification=dict(self.env['hr.employee.departure']._fields['l10n_be_professional_reclassification']._description_selection(self.env)).get(departure.l10n_be_professional_reclassification)),
                user_id=departure.employee_id.current_version_id.hr_responsible_id.id or self.env.user.id,
                summary=self.env._('Outplacement'),
            )
        return res

    def _check_refuse_future_leaves_condition(self):
        """ Refuse future leaves for Belgian employees instead of deleting them. """
        self.ensure_one()
        if self.country_code == 'BE':
            return True
        return super()._check_refuse_future_leaves_condition()

    def _get_departures_to_archive(self):
        """ Exclude Belgian departures without an archive date from automatic archival. """
        departures = super()._get_departures_to_archive()
        return departures.filtered(lambda d: d.country_code != 'BE' or d.action_date)

    def _unassign_company_car(self):
        """ Keep company cars assigned for Belgian departures and post a message with the departure date.
        Other departures follow the standard car unassignment behavior.
        """
        be_departures = self.filtered(lambda d: d.country_code == 'BE')
        if be_departures:
            all_drivers = be_departures.employee_id.user_id.partner_id | be_departures.employee_id.work_contact_id
            cars_sudo = self.sudo().env['fleet.vehicle'].search([('driver_id', 'in', all_drivers.ids)])
            for departure in be_departures:
                drivers = departure.employee_id.user_id.partner_id | departure.employee_id.work_contact_id
                departure_cars = cars_sudo.filtered(lambda c: c.driver_id in drivers)
                for car in departure_cars:
                    car.message_post(body=self.env._(
                        "%(employee)s is leaving the company on %(departure_date)s.",
                        employee=departure.employee_id.name,
                        departure_date=departure.departure_date.strftime('%d/%m/%Y'),
                    ))
        other_departures = self - be_departures
        super(HrEmployeeDeparture, other_departures)._unassign_company_car()
