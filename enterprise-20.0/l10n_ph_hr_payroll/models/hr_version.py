# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from datetime import datetime

from odoo.tools.date_utils import localized
from odoo.tools.intervals import Intervals

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# The statutory PH work entry types are named after the prefixes below, not after
# the code of the base type they derive from.
COMPOUND_CODE_PREFIX = {
    '002.00': 'WORK100',
    '040.00': 'OVERTIME',
}


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_ph_hr_payroll_is_main_employment = fields.Boolean(
        string='Main Employment',
        groups="hr_payroll.group_hr_payroll_user",
        help='Check this box if this contract is the main employment for this employee.',
        default=True,
    )
    l10n_ph_hr_payroll_minimum_wage_earner = fields.Boolean(
        string='Minimum Wage Earner',
        groups="hr_payroll.group_hr_payroll_user",
        help='Exempts the employee from Income Tax and applies MWE-specific rates for SSS and PhilHealth.',
    )
    l10n_ph_hr_payroll_employee_rank = fields.Selection(
        string='Employee Rank',
        selection=[
            ('rank_and_file', 'Rank-and-File'),
            ('supervisory', 'Supervisory'),
            ('managerial', 'Managerial'),
        ],
        groups="hr_payroll.group_hr_payroll_user",
        help="Controls Overtime eligibility and Fringe Benefit Tax (FBT) calculations."
    )
    l10n_ph_hr_payroll_prev_employment_id = fields.Many2one(
        string='Previous Employment',
        comodel_name='l10n_ph_hr_payroll.previous_employment',
        domain="[('employee_id', '=', employee_id)]",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ph_hr_payroll_philhealth_pin = fields.Char(
        string='PhilHealth PIN',
        groups="hr.group_hr_user",
        help="The 12-digit PhilHealth Identification Number (PIN) assigned to the employee.",
    )
    l10n_ph_hr_payroll_sss_number = fields.Char(
        string='SS Number',
        groups="hr.group_hr_user",
        help="The 10-digit Social Security System (SSS) number assigned to the employee.",
    )
    l10n_ph_hr_payroll_pag_ibig_mid = fields.Char(
        string='Pag-IBIG MID',
        groups="hr.group_hr_user",
        help="The 12-digit Pag-IBIG Membership ID (MID) assigned to the employee.",
    )
    l10n_ph_hr_payroll_rdo_code = fields.Char(
        string="RDO Code",
        groups="hr.group_hr_user",
        help="Revenue District Office (RDO) Code where the employee is registered.",
    )
    # We NEED to be able to separate private (home) address vs registered address for compliance with yearly tax return.
    # To keep it simple, we simply store a char field to input the whole thing. ZIP is the special case as we need it separately.
    l10n_ph_hr_payroll_registered_address = fields.Char(
        string="Registered Address",
        groups="hr.group_hr_user",
        help="The official address registered with the BIR for this employee's TIN. Used for Form 2316. Leave blank to use the private address.",
    )
    l10n_ph_hr_payroll_registered_zip = fields.Char(
        string="Registered ZIP Code",
        groups="hr.group_hr_user",
    )
    l10n_ph_hr_payroll_foreign_address = fields.Char(
        string="Foreign Address",
        groups="hr.group_hr_user",
        help="Permanent residence in the home country for expatriates or non-resident aliens. Used for BIR Form 2316 (Item 6D). Leave blank for local resident employees.",
    )
    wage_type = fields.Selection(
        selection_add=[("daily", "Daily Wage")],
        ondelete={"daily": 'set monthly'},
    )
    l10n_ph_hr_payroll_daily_wage = fields.Monetary(
        string='Daily Wage',
        compute='_l10n_ph_hr_payroll_compute_daily_wage',
        inverse='_l10n_ph_hr_payroll_inverse_daily_wage',
        store=True,
        readonly=False,
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user"
    )

    @api.constrains('l10n_ph_hr_payroll_prev_employment_id')
    def _check_l10n_ph_hr_payroll_prev_employment_employee(self):
        """ Ensure that a previous employment record is never linked to a version whose employee doesn't match. """
        for version in self:
            prev_emp = version.l10n_ph_hr_payroll_prev_employment_id
            if prev_emp and prev_emp.employee_id != version.employee_id:
                raise ValidationError(version.env._("This Previous Employment record is already linked to a different employee."))

    @api.constrains('l10n_ph_hr_payroll_rdo_code')
    def _check_l10n_ph_hr_payroll_rdo_code(self):
        """
        Ensure that the RDO code set on the employee is recognized, and that we can map to a region.
        This is required for tax reporting.
        """
        region_mapping = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_ph_hr_payroll_rdo_regions', fields.Date.context_today(self), raise_if_not_found=False)
        # Could happen if the mapping was removed; or the date is too far in the past (test). In these cases, we can just skip.
        if not region_mapping:
            return

        for version in self:
            rdo_code = version.l10n_ph_hr_payroll_rdo_code
            if rdo_code and not region_mapping.get(rdo_code):
                raise ValidationError(version.env._("The RDO code set must be mapped to a region in the `Philippines: RDO region mapping` rule parameter."))

    @api.depends('wage', 'schedule_pay', 'wage_type')
    def _l10n_ph_hr_payroll_compute_daily_wage(self):
        for version in self:
            if version.wage_type != 'daily' or not version._is_struct_from_country('PH'):
                continue
            version.l10n_ph_hr_payroll_daily_wage = version._l10n_ph_hr_payroll_from_to_schedule(to_schedule='daily')

    def _l10n_ph_hr_payroll_inverse_daily_wage(self):
        for version in self:
            if version.wage_type != 'daily' or not version.l10n_ph_hr_payroll_daily_wage or not version._is_struct_from_country('PH'):
                continue
            version.wage = version._l10n_ph_hr_payroll_from_to_schedule(amount=version.l10n_ph_hr_payroll_daily_wage, from_schedule='daily')

    def _l10n_ph_hr_payroll_get_holiday_rate_code(self, non_worked_entries_vals):
        """
        Determine the highest-paying holiday code for a specific day.

        If a day contains multiple non-worked entries (e.g., a Regular Holiday
        and a Special Non-Working Holiday falling on the same date), DOLE requires
        us to use the most preferential rate.

        This method checks the non-worked entries in priority order (Double Holiday ->
        Regular Holiday -> Special Non-Working) and returns the winning code so it
        can be compounded with the work entry type later.
        """
        if not non_worked_entries_vals:
            return None

        leave_codes = {entry['work_entry_type_id'].code for entry in non_worked_entries_vals}

        if "DH_LEAVE" in leave_codes:
            return "DH"
        if "RH_LEAVE" in leave_codes:
            return "RH"
        if "SNWH_LEAVE" in leave_codes:
            return "SNW"

        return None

    def _l10n_ph_hr_payroll_is_rest_day(self, date):
        """
        Returns true if the provided date is a rest day according to the employee calendar.
        """
        return self.resource_calendar_id and not self.resource_calendar_id._works_on_date(date) or False

    def _l10n_ph_hr_payroll_get_work_hours(self, date_from, date_to, work_entries_vals):
        """
        Aggregate worked hours, dynamically substituting work entry types for DOLE compliance.

        Because calendar and timezone evaluations in Odoo are deeply tied to the company,
        this method groups the records by company before passing them down to the core
        evaluation logic (`_l10n_ph_hr_payroll_get_work_hours_data`).
        """
        assert not isinstance(date_from, datetime)
        assert not isinstance(date_to, datetime)

        work_data = defaultdict(float)

        versions_by_company = self.grouped('company_id')
        for company, versions in versions_by_company.items():
            work_data_tz = versions.with_company(company).sudo()._l10n_ph_hr_payroll_get_work_hours_data(date_from, date_to, work_entries_vals)
            for work_entry_type_id, hours in work_data_tz.items():
                work_data[work_entry_type_id] += hours
        return work_data

    def _l10n_ph_hr_payroll_get_work_hours_data(self, date_from, date_to, work_entries_vals):
        """
        Dynamically calculate and replace work entry types based on DOLE compound rules.

        This method processes work entries day by day. It checks the employee's
        specific working schedule to see if the day is a Rest Day, and checks the
        leave entries to see if the day is a Holiday.

        If premium conditions are met, it builds a compound code (e.g., 'WORK100_RH_REST')
        and searches the database for that specific statutory work entry type. If found,
        it substitutes the native work entry type for the statutory one.
        """
        assert not isinstance(date_from, datetime)
        assert not isinstance(date_to, datetime)

        all_work_entry_types_by_code = self.env['hr.work.entry.type'].with_context(active_test=False).search(
            [('country_id.code', '=', 'PH')]
        ).grouped('code')

        work_entries_by_version_date = defaultdict(list)
        for work_entry_vals in work_entries_vals:
            if work_entry_vals['version_id'] in self and date_from <= work_entry_vals['date'] <= date_to:
                work_entries_by_version_date[work_entry_vals["version_id"], work_entry_vals["date"]].append(work_entry_vals)

        work_data = defaultdict(float)
        for (version, date), daily_entries in work_entries_by_version_date.items():
            worked_entries_vals = []
            non_worked_entries_vals = []

            for we_val in daily_entries:
                if we_val["work_entry_type_id"].count_as == "working_time":
                    worked_entries_vals.append(we_val)
                else:
                    non_worked_entries_vals.append(we_val)

            is_rest_day = version._l10n_ph_hr_payroll_is_rest_day(date)
            holiday_rate_code = version._l10n_ph_hr_payroll_get_holiday_rate_code(non_worked_entries_vals)
            for work_entry_vals in worked_entries_vals:
                code = work_entry_vals['work_entry_type_id'].code
                code = COMPOUND_CODE_PREFIX.get(code, code)
                if holiday_rate_code:
                    code += f"_{holiday_rate_code}"
                if is_rest_day:
                    code += "_REST"

                mapped_type = all_work_entry_types_by_code.get(code, work_entry_vals['work_entry_type_id'])
                work_data[mapped_type, code] += work_entry_vals['duration']

            # Leaves on a day without other entries should be kept as is, unless they fall on a rest day.
            if non_worked_entries_vals and not worked_entries_vals and not is_rest_day:
                for work_entry_vals in non_worked_entries_vals:
                    work_data[work_entry_vals['work_entry_type_id'], work_entry_vals['work_entry_type_id'].code] += work_entry_vals['duration']

        return work_data

    def _get_real_leaves_static(self, leaves, expected_attendances):
        """
        Makes sure that we do not exclude leaves that fall outside the employee calendar.
        These are handled later, so that we can correctly calculate the wage for work time done during a rest day when a leave happens.
        """
        self.ensure_one()
        if not self._is_struct_from_country('PH'):
            return super()._get_real_leaves_static(leaves, expected_attendances)

        return leaves

    def _get_real_leaves_static_attendance(self, leaves, static_attendances):
        """
        Makes sure that we do not exclude leaves that overlap with attendances.
        These are handled later, so that we can correctly calculate the wage for work time done during a rest day when a leave happens.
        """
        self.ensure_one()
        if not self._is_struct_from_country('PH'):
            return super()._get_real_leaves_static_attendance(leaves, static_attendances)

        return leaves

    def _get_real_worked_leaves(self, worked_leaves, real_leaves):
        """
        By default, if a day has both worked leaves and real leaves, Odoo only considers the real leave.
        In our case, we will assume that it means 'the employee worked during a real leave' when this setup is used, allowing
        to cover this required use case.
        """
        if not self._is_struct_from_country('PH'):
            return super()._get_real_worked_leaves(worked_leaves, real_leaves)

        return worked_leaves

    def _get_real_attendances(self, attendances, leaves, worked_leaves):
        """
        Tardiness should not be counted as a worked leave, so that it doesn't reduce the attendance amount directly.
        This allows us to display a negative line on the payslip that explains the lower net.
        """
        if self._is_struct_from_country('PH'):
            worked_leaves = Intervals(worked_leave for worked_leave in worked_leaves if worked_leave[2].work_entry_type_id.code != 'TARD')
        return super()._get_real_attendances(attendances, leaves, worked_leaves)

    @api.model
    def _generate_work_entries_postprocess_adapt_to_calendar(self, vals):
        """
        Allows calculating the duration for work outside the calendar.
        For any work done inside the calendar, we follow the standard process.

        These data will be filtered again during worked day lines generation; where the outside of schedule holidays will
        be filtered out or transformed into the specific work entry types expected to cover our use case.
        """
        version_id = vals['version_id']
        if not version_id._is_struct_from_country('PH'):
            return super()._generate_work_entries_postprocess_adapt_to_calendar(vals)

        calendar = version_id.resource_calendar_id
        from_datetime = localized(vals['date_start'])
        to_datetime = localized(vals['date_stop'])
        intervals = calendar._attendance_intervals_batch(
            from_datetime,
            to_datetime,
            resources_per_tz=vals['employee_id']._get_resources_per_tz(),
        )

        if intervals[vals['employee_id'].resource_id.id] and calendar:
            return super()._generate_work_entries_postprocess_adapt_to_calendar(vals)
        return False

    def _l10n_ph_hr_payroll_from_to_schedule(self, amount=None, from_schedule=None, to_schedule=None):
        """
        Convert a wage amount between different pay schedules using DOLE EEMR multipliers.

        In the Philippines, you cannot just divide an annual salary by 12. DOLE dictates
        specific yearly multipliers based on the employee's schedule:
        - Monthly-paid: Fixed at 365 days.
        - Daily-paid (5 days/week): Fixed at 261 days.
        - Daily-paid (6 days/week): Fixed at 313 days.
        - Everyday workers: 392.5 days (if it includes Rest Day/Holiday premiums).

        Example: Converting a ₱500 Daily Wage for a 6-day worker to a Monthly Rate:
        1. ₱500 (Daily) * 313 (DOLE Factor) = ₱156,500 (Annual)
        2. ₱156,500 / 12 months = ₱13,041.67 (Monthly)
        """
        self.ensure_one()
        if amount is None:
            amount = self.wage
        if not from_schedule:
            from_schedule = self.schedule_pay
        if not to_schedule:
            to_schedule = self.schedule_pay

        if from_schedule == to_schedule:
            return amount

        # For simplicity, and avoid guess work, we force users to set calendars.
        hours_per_day = self.resource_calendar_id.hours_per_day or 8.0
        days_per_year = self._l10n_ph_hr_payroll_get_employee_eemr_factor()

        # 2. Define the Annual Multipliers
        annual_factors = {
            "hourly": hours_per_day * days_per_year,
            "daily": days_per_year,
            "weekly": 52.0,
            "bi-weekly": 26.0,
            "semi-monthly": 24.0,
            "monthly": 12.0,
            "bi-monthly": 6.0,
            "quarterly": 4.0,
            "semi-annually": 2.0,
            "annually": 1.0,
        }

        # 3. Convert Source -> Annual -> Target
        from_factor = annual_factors.get(from_schedule, 12.0)
        to_factor = annual_factors.get(to_schedule, 12.0)

        annual_amount = amount * from_factor
        return annual_amount / to_factor

    def _l10n_ph_hr_payroll_get_employee_eemr_factor(self):
        """
        Helper calculating and returning the factor used for EEMR calculations.
        It corresponds to the amount of work days per year for this employee.
        """
        self.ensure_one()
        calendar = self.resource_calendar_id
        if self.wage_type == 'monthly':
            days_per_year = 365  # Fixed as per the DOLE.
        else:
            # Find the amount of day when the employee is working.
            # Only count each day of the week once, as long as there are any worked time configured on them
            days_per_week = calendar.days_per_week
            if days_per_week == 5:
                days_per_year = 261.0
            elif days_per_week == 6:
                days_per_year = 313.0
            elif days_per_week == 7:
                days_per_year = 392.5 if calendar.l10n_ph_hr_payroll_is_392_5 else 365.0
            else:
                days_per_year = days_per_week * 52.0
        return days_per_year

    def _get_contract_wage_field(self):
        self.ensure_one()
        if self.wage_type == 'daily' and self._is_struct_from_country('PH'):
            return 'l10n_ph_hr_payroll_daily_wage'
        return super()._get_contract_wage_field()

    def _get_fields_that_recompute_payslip(self):
        return super()._get_fields_that_recompute_payslip() + ['l10n_ph_hr_payroll_daily_wage']
