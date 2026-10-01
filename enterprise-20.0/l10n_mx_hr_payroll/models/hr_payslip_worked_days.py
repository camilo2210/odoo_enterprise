# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'version_id.wage', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        mx_worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "MX")
        for worked_days in mx_worked_days:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or worked_days.code == '000.00':
                worked_days.amount = 0
                continue
            if not worked_days.payslip_id.date_from or not worked_days.payslip_id.date_to:
                continue

            period_wage = worked_days._get_period_wage()
            amount_rate = worked_days.work_entry_type_id.amount_rate
            worked_days.amount = period_wage * amount_rate
        return super(HrPayslipWorkedDays, self - mx_worked_days)._compute_amount()

    def _get_period_wage(self):
        self.ensure_one()
        version = self.version_id
        if not self.is_paid:
            return 0
        if version.wage_type == 'hourly':
            return version.hourly_wage * self.number_of_hours
        else:
            payslip = self.payslip_id
            hourly_wage = payslip.l10n_mx_daily_salary / payslip._get_worked_day_lines_hours_per_day(version=version)

            if self.code == 'SEVENTH_DAY':
                worked_hours = sum(
                    line.number_of_hours for line in payslip.worked_days_line_ids
                    if line.work_entry_type_id.amount_rate and line.work_entry_type_id != self.work_entry_type_id
                )

                weeks_in_period = 1 if version.schedule_pay == 'weekly' else 2
                expected_hours = version.resource_calendar_id.hours_per_week * weeks_in_period

                hourly_wage *= worked_hours / expected_hours

            return hourly_wage * self.number_of_hours
