# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from zoneinfo import ZoneInfo

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_uz_annual_leave_eligibility = fields.Float(
        string="Eligible Leaves",
        default=21.0,
        store=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user",
        help="The number of annual leave days an employee is entitled to for one year of service",
    )
    l10n_uz_initial_average_monthly_wage = fields.Monetary(
        string="Initial Average Monthly Wage",
        currency_field="currency_id",
        compute="_compute_l10n_uz_initial_average_monthly_wage",
        store=True,
        readonly=False,
        tracking=True,
        help="Average monthly wage carried over from before the employee's first payslip in the system, so historical payroll data does not need to be re-entered."
    )

    @api.depends("wage")
    def _compute_l10n_uz_initial_average_monthly_wage(self):
        for version in self:
            if not version.l10n_uz_initial_average_monthly_wage:
                version.l10n_uz_initial_average_monthly_wage = version.wage or 0.0

    def _get_version_work_entries_values(self, date_start, date_stop):
        """
        In Uzbekistan, annual labor leaves use calendar days. All days consume leave balance, but
        Sundays are not paid and public holidays do not count against the leave.
        This method adds work entries for validated paid leaves that are not already covered by the schedule.
        For annual labor leave, Sundays are added as separate work entries
        (unpaid, 0% rate) so the payslip shows them as a distinct line from the paid days.
        E.g. employee has a 5-day Mon-Fri schedule and takes annual leave Thu-Mon:
        work entries show Thu, Fri, Sat, Mon (paid), Sun (unpaid).
        """
        results = super()._get_version_work_entries_values(date_start, date_stop)

        uz_versions = self.filtered(lambda v: v.company_id.country_id.code == 'UZ')
        if not uz_versions:
            return results

        annual_leave_types = uz_versions.company_id.mapped('l10n_uz_annual_leave_work_entry_type_id')
        sunday_leave_type = self.env.ref('hr_work_entry.l10n_uz_work_entry_type_annual_labor_leave_sunday', raise_if_not_found=False)
        if not sunday_leave_type:
            return results

        start_dt = date_start.replace(tzinfo=datetime.UTC) if not date_start.tzinfo else date_start
        end_dt = date_stop.replace(tzinfo=datetime.UTC) if not date_stop.tzinfo else date_stop

        leaves_by_employee = self.env['hr.leave'].search([
            ('employee_id', 'in', uz_versions.employee_id.ids),
            ('state', '=', 'validate'),
            ('work_entry_type_id', 'in', annual_leave_types.ids),
            ('date_from', '<=', end_dt.replace(tzinfo=None)),
            ('date_to', '>=', start_dt.replace(tzinfo=None)),
        ]).grouped('employee_id')

        for version in uz_versions:
            employee = version.employee_id
            if not leaves_by_employee.get(employee):
                continue

            tz = ZoneInfo(version._get_tz())
            calendar = employee.resource_calendar_id
            standard_duration = calendar.hours_per_day or 8.0

            covered_dates = {
                entry['date_start'].replace(tzinfo=datetime.UTC).astimezone(tz).date()
                for entry in results if entry['employee_id'] == employee
            }

            for leave in leaves_by_employee[employee]:
                leave_start_local = max(start_dt, leave.date_from.replace(tzinfo=datetime.UTC)).astimezone(tz).date()
                leave_end_local = min(end_dt, leave.date_to.replace(tzinfo=datetime.UTC)).astimezone(tz).date()

                current_date = leave_start_local
                while current_date <= leave_end_local:
                    if current_date not in covered_dates:
                        is_sunday = current_date.weekday() == 6

                        local_dt_start = datetime.datetime.combine(current_date, datetime.time(8, 0), tzinfo=tz)
                        local_dt_stop = local_dt_start + datetime.timedelta(hours=standard_duration)

                        results.append({
                            'name': f"{leave.work_entry_type_id.name}{' (Sunday)' if is_sunday else ''}",
                            'date_start': local_dt_start.astimezone(datetime.UTC).replace(tzinfo=None),
                            'date_stop': local_dt_stop.astimezone(datetime.UTC).replace(tzinfo=None),
                            'date': current_date,
                            'duration': standard_duration,
                            'work_entry_type_id': sunday_leave_type if is_sunday else leave.work_entry_type_id,
                            'employee_id': employee,
                            'company_id': version.company_id,
                            'version_id': version,
                            'leave_ids': leave
                        })
                        covered_dates.add(current_date)
                    current_date += datetime.timedelta(days=1)

        return results
