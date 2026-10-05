# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

OUT_OF_SCHEDULE_KW = ['_REST', 'OVERTIME', '040.00', 'TARD']


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    l10n_ph_hr_payroll_holiday_rate = fields.Float(
        string='Holiday Pay Rate',
        help='Rate affecting the amount of holiday pay for this worked day line.',
    )
    l10n_ph_hr_payroll_overtime_rate = fields.Float(
        string='Overtime Pay Rate',
        help='Rate affecting the amount of overtime pay for this worked day line.',
    )
    l10n_ph_hr_payroll_night_shift_rate = fields.Float(
        string='Night Shift Pay Rate',
        help='Rate affecting the amount of night shift pay for this worked day line.',
    )
    l10n_ph_hr_payroll_basic_amount = fields.Monetary(compute='_compute_amount', store=True, copy=True)
    l10n_ph_hr_payroll_holiday_amount = fields.Monetary(compute='_compute_amount', store=True, copy=True)
    l10n_ph_hr_payroll_overtime_amount = fields.Monetary(compute='_compute_amount', store=True, copy=True)
    l10n_ph_hr_payroll_shift_amount = fields.Monetary(compute='_compute_amount', store=True, copy=True)

    @api.depends('version_id.wage_type', 'version_id.l10n_ph_hr_payroll_daily_wage', 'l10n_ph_hr_payroll_holiday_rate',
                 'l10n_ph_hr_payroll_overtime_rate', 'l10n_ph_hr_payroll_night_shift_rate')
    def _compute_amount(self):
        """
        Calculate the monetary amounts for each payslip worked day line.

        This method bridges Odoo's standard dynamic calendar math with Philippine DOLE
        regulations. We intercept the calculation to enforce EEMR (Estimated Equivalent
        Monthly Rate) rules:
        - Daily paid employees get strictly paid for actual hours worked using their EEMR.
        - Monthly paid employees use Odoo's flat target wage for normal days, but their
          overtime, absences, and night shift differentials are intercepted and calculated
          using strict DOLE formulas.
        """
        philippines_worked_days = self.filtered(lambda wd: wd.version_id._is_struct_from_country("PH"))
        super(HrPayslipWorkedDays, self - philippines_worked_days)._compute_amount()
        if not philippines_worked_days:
            return

        # precompute the worked days that can use Odoo's calculation as base.
        regular_worked_days = philippines_worked_days.filtered(
            lambda wd: not any(kw in wd.code for kw in OUT_OF_SCHEDULE_KW) and wd.version_id.wage_type == 'monthly'
        )
        super(HrPayslipWorkedDays, regular_worked_days)._compute_amount()

        for worked_day in philippines_worked_days:
            if any(kw in worked_day.code for kw in OUT_OF_SCHEDULE_KW) or worked_day.version_id.wage_type != 'monthly':
                # Employees that are paid strictly on a worked-time basis must use the EEMR as basis for their wage.
                # The same applies for the differential given to employees for work done outside their schedule.
                basic_pay, holiday_pay, overtime_pay, night_shift_differential = worked_day._l10n_ph_hr_payroll_compute_amount_using_eemr()
                # For work done outside of schedule, the whole amount always goes into the OT and diff line.
                is_holiday_leave = worked_day.code in ['RH_LEAVE', 'DH_LEAVE', 'SNWH_LEAVE']
                is_regular_schedule = not any(kw in worked_day.code for kw in ['OVERTIME', '040.00', '_REST']) and not is_holiday_leave
                worked_day.update({
                    'l10n_ph_hr_payroll_basic_amount': basic_pay if is_regular_schedule else 0.0,
                    'l10n_ph_hr_payroll_holiday_amount': holiday_pay + (basic_pay if is_holiday_leave else 0.0),
                    'l10n_ph_hr_payroll_overtime_amount': overtime_pay + (basic_pay if not is_regular_schedule and not is_holiday_leave else 0.0),
                    'l10n_ph_hr_payroll_shift_amount': night_shift_differential,
                    'amount': basic_pay + holiday_pay + overtime_pay + night_shift_differential,
                })
            else:
                if worked_day.code == '002.00':
                    worked_day._l10n_ph_hr_payroll_adjust_unpaid_amount(philippines_worked_days)

                holiday_pay, overtime_pay, night_shift_differential = worked_day._l10n_ph_hr_payroll_compute_differential_for_monthly_paid_employees()
                worked_day.update({
                    'l10n_ph_hr_payroll_basic_amount': worked_day.amount,
                    'l10n_ph_hr_payroll_holiday_amount': holiday_pay,
                    'l10n_ph_hr_payroll_overtime_amount': overtime_pay,
                    'l10n_ph_hr_payroll_shift_amount': night_shift_differential,
                    'amount': worked_day.amount + holiday_pay + overtime_pay + night_shift_differential,
                })

    def _l10n_ph_hr_payroll_compute_amount_using_eemr(self, compute_unpaid=False):
        """
        Calculate the base pay and statutory premiums for a worked day using the EEMR formula.

        This completely bypasses Odoo's dynamic calendar rate. Instead, it extracts the strict
        hourly rate directly from the employee's fixed contract wage.

        It also handles the 'Monthly-paid' quirk: if a monthly employee works on a Rest Day,
        their base 100% pay is already covered by their standard salary, so we zero out the
        base and only calculate the statutory premium to prevent double payment.
        """
        self.ensure_one()
        if self.payslip_id.edited or self.payslip_id.state != 'draft' or (not compute_unpaid and not self.is_paid):
            return 0.0, 0.0, 0.0, 0.0
        if not self.version_id or self.code == '000.00':
            return 0.0, 0.0, 0.0, 0.0
        version = self.payslip_id.version_id
        amount_rate = self.work_entry_type_id.amount_rate
        if compute_unpaid and amount_rate == 0:
            amount_rate = 1.0
        if version.wage_type == "hourly":
            hourly_rate = version.hourly_wage
        else:
            # This is the important change; the rate is directly calculated from the wage using the EEMR.
            if base := version.l10n_ph_hr_payroll_daily_wage:
                hourly_rate = version._l10n_ph_hr_payroll_from_to_schedule(
                    amount=base,
                    from_schedule='daily',
                    to_schedule='hourly',
                )
            else:
                hourly_rate = version._l10n_ph_hr_payroll_from_to_schedule(to_schedule='hourly')

        # Monthly paid employees are considered to be paid 365 days a year; so only the 'extra' coming from
        # work done on rest days must be paid (for work falling into regular work hours).
        # Manager and supervisor are by default unpaid on overtimes, so we only add the base if the rate was changed
        # to something else than 0.
        base = 1.0
        if '_REST' in self.code and 'OVERTIME' not in self.code and version.wage_type == 'monthly':
            base = 0.0
        if ("OVERTIME" in self.code or "040.00" in self.code) and not self.l10n_ph_hr_payroll_overtime_rate:
            base = 0.0

        base_amount = hourly_rate * self.number_of_hours * amount_rate

        basic_pay = base_amount * base
        holiday_pay = base_amount * self.l10n_ph_hr_payroll_holiday_rate
        overtime_pay = base_amount * self.l10n_ph_hr_payroll_overtime_rate
        night_shift_differential = base_amount * self.l10n_ph_hr_payroll_night_shift_rate
        return basic_pay, holiday_pay, overtime_pay, night_shift_differential

    def _l10n_ph_hr_payroll_adjust_unpaid_amount(self, other_worked_days):
        """
        Correct the 002.00 line to use strict EEMR deductions instead of Odoo's dynamic ones.

        For monthly-paid employees, Odoo natively deducts absences using a fluctuating
        hourly rate based on how many days are in the current month. We intercept that here,
        calculate the exact difference between Odoo's deduction and the strict DOLE EEMR
        deduction, and adjust 002.00 so the employee is deducted the correct fixed amount.

        We also use this step to inject pay for Special Non-Working Holidays (SNWH).
        Since SNWH is globally configured as 'unpaid' (for daily workers), we override it
        here for monthly workers because their fixed salary legally covers unworked holidays.
        """
        self.ensure_one()
        amount_rate = self.work_entry_type_id.amount_rate or 1
        number_of_hours = self.number_of_hours or 1
        hourly_rate = self.amount / amount_rate / number_of_hours

        related_unpaid_wd = other_worked_days.filtered(lambda wd: not wd.is_paid and wd.payslip_id == self.payslip_id)

        # Special case: special non-working holidays should be considered paid, only for monthly paid employees.
        snwh_wds = related_unpaid_wd.filtered(lambda wd: wd.code == 'SNWH_LEAVE')
        if snwh_wds:
            related_unpaid_wd -= snwh_wds
            for wd in snwh_wds:
                wd.update({
                    'l10n_ph_hr_payroll_basic_amount': wd.number_of_hours * hourly_rate,
                    'amount': wd.number_of_hours * hourly_rate,
                })

        total_unpaid_eemr = sum(wd._l10n_ph_hr_payroll_compute_amount_using_eemr(compute_unpaid=True)[0] for wd in related_unpaid_wd)
        total_unpaid_hours = sum(related_unpaid_wd.mapped('number_of_hours'))

        if total_unpaid_eemr:
            original_unpaid_amount = hourly_rate * total_unpaid_hours
            self.amount += (original_unpaid_amount - total_unpaid_eemr)

    def _l10n_ph_hr_payroll_compute_differential_for_monthly_paid_employees(self):
        """
        Calculate the extra premium pay for monthly employees working special hours.

        Since monthly employees already have their 100% base pay covered by their
        fixed flat salary (002.00), this method only calculates the extra statutory
        percentages (like a 10% Night Shift premium or Holiday premiums) for hours
        worked within their regular schedule.

        It relies on the strict EEMR hourly rate for these premiums so they don't
        fluctuate based on how many days are in the current month.
        """
        self.ensure_one()
        if not self.is_paid:
            return 0.0, 0.0, 0.0

        # Extract the strict EEMR hourly rate to use as the base for our premium multipliers
        eemr_hourly_rate = self.version_id._l10n_ph_hr_payroll_from_to_schedule(to_schedule='hourly')
        base_amount = eemr_hourly_rate * self.number_of_hours * self.work_entry_type_id.amount_rate

        holiday_pay = base_amount * self.l10n_ph_hr_payroll_holiday_rate
        overtime_pay = base_amount * self.l10n_ph_hr_payroll_overtime_rate
        night_shift_differential = base_amount * self.l10n_ph_hr_payroll_night_shift_rate
        return holiday_pay, overtime_pay, night_shift_differential
