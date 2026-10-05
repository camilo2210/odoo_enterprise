# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    l10n_hk_leave_id = fields.Many2one('hr.leave', string='Leave', readonly=True)

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'version_id', 'payslip_id.l10n_hk_average_daily_wage')
    def _compute_amount(self):
        hk_worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "HK")

        for worked_days in hk_worked_days:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or worked_days.code == '000.00' or not worked_days.is_paid:
                worked_days.amount = 0
                continue
            amount_rate = worked_days.work_entry_type_id.amount_rate
            if worked_days.payslip_id.wage_type == "hourly":
                hourly_wage = worked_days.payslip_id.version_id.hourly_wage
                if worked_days.work_entry_type_id.l10n_hk_use_713:
                    hourly_wage = worked_days.payslip_id.l10n_hk_average_daily_wage / worked_days.version_id.resource_calendar_id.hours_per_day
                worked_days.amount = hourly_wage * worked_days.number_of_hours * amount_rate
            else:
                payslip = worked_days.payslip_id
                if worked_days.l10n_hk_leave_id:
                    payslip = self.env['hr.payslip'].search([
                        ('employee_id', '=', worked_days.payslip_id.employee_id.id),
                        ('date_from', '<=', worked_days.l10n_hk_leave_id.date_from),
                        ('date_to', '>=', worked_days.l10n_hk_leave_id.date_from),
                        ('state', 'in', ['validated', 'paid']),
                    ], limit=1) or worked_days.payslip_id
                attendance_hours = sum(
                    wd.number_of_hours for wd in payslip.worked_days_line_ids
                    if not wd.work_entry_type_id.is_extra_hours
                )
                sum_worked_days = attendance_hours / worked_days.version_id.resource_calendar_id.hours_per_day
                daily_wage = worked_days.version_id._get_contract_wage() / (sum_worked_days or 1)
                if worked_days.work_entry_type_id.l10n_hk_use_713:
                    daily_wage = payslip.l10n_hk_average_daily_wage
                elif worked_days.work_entry_type_id.code == 'HKLEAVE112':  # Work Injury Sick Leave
                    daily_wage = worked_days._get_work_injury_baseline(payslip) / (sum_worked_days or 1)
                number_of_days = worked_days.number_of_hours / worked_days.version_id.resource_calendar_id.hours_per_day
                worked_days.amount = daily_wage * number_of_days * amount_rate

        super(HrPayslipWorkedDays, self - hk_worked_days)._compute_amount()

    def _get_work_injury_baseline(self, origin_payslip):
        """
        Computes the baseline Work Injury Periodical Payment strictly under Section 10 of the
        Employees' Compensation Ordinance (Cap. 282).

        Under Cap. 282, statutory compensation for temporary incapacity is strictly defined as
        four-fifths (80%) of the difference between normal pre-accident monthly earnings and
        the actual monthly earnings obtained during the incapacity period.

        Calculation Sequence:
        1. Averages 12-month gross earnings prior to the accident, discounting periods of non-full pay.
        2. Compares the 12-month AMW against the immediate preceding month's gross earnings, establishing the higher value as the legal baseline.
        3. Subtracts standard taxable post-accident earnings (`POST_ACCIDENT_EARNINGS`) generated during the recovery period.

        :param origin_payslip: The payslip matching the month in which the injury leave started.
        :returns the final differential baseline for the 80% multiplier.
        """
        self.ensure_one()
        # Calculate the number of days for past 12 months
        first_day = max(origin_payslip.date_from + relativedelta(months=-12, day=1), origin_payslip.employee_id._get_first_contract_date())
        last_day = origin_payslip.date_to + relativedelta(day=1)
        total_days = (last_day - first_day).days

        # Find past 12-month payslips
        last_year_payslips = origin_payslip._get_previous_year_payslips(order='date_from')

        # Calculate the work rate
        number_of_days = last_year_payslips._get_number_of_worked_days(only_full_pay=True)
        delta = relativedelta(last_day, first_day)
        period_months = delta.years * 12 + delta.months + (delta.days / (365 / 12))
        number_of_months = (number_of_days / total_days) * period_months if total_days > 0 else 0.0

        # Calculate the average monthly salary
        gross = last_year_payslips._get_line_values(['713_GROSS'], compute_sum=True)['713_GROSS']['sum']['total']
        gross -= last_year_payslips._get_total_non_full_pay()
        average_monthly_salary = gross / number_of_months if number_of_months > 0 else 0.0

        # POST_ACCIDENT_EARNINGS should of course always be based on the current payslip.
        return max(origin_payslip._get_713_gross_at_date(origin_payslip.date_from), average_monthly_salary) - self.payslip_id._get_input_line_amount('POST_ACCIDENT_EARNINGS')
