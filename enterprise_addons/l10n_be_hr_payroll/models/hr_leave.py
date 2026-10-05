from collections import Counter
from datetime import date, timedelta, datetime, UTC
from bisect import bisect_left
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
from odoo.tools.intervals import Intervals

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    l10n_be_sickness_relapse = fields.Boolean(compute="_compute_l10n_be_sickness_relapse")
    l10n_be_sickness_can_relapse = fields.Boolean(compute="_compute_can_relapse")
    allowed_l10n_be_sickness_relapse_origin_leave_ids = fields.Many2many(
        'hr.leave',
        string="Allowed Related Leaves",
        compute="_compute_can_relapse",
        help="The list of leaves that can be linked as the origin leave for a sickness relapse"
    )
    l10n_be_sickness_relapse_origin_leave_id = fields.Many2one(
        'hr.leave',
        string="Sickness Relapse",
        tracking=True,
        compute="_compute_l10n_be_sickness_relapse_origin_leave_id",
        store=True,
        readonly=False,
        domain='[("id", "in", allowed_l10n_be_sickness_relapse_origin_leave_ids)]'
    )
    country_code = fields.Char(related='company_id.country_id.code', depends=['company_id'])

    @api.constrains('work_entry_type_id', 'date_from', 'employee_id')
    def _check_economic_unemployment_rules(self):
        economic_unemployement_leaves = self.filtered(lambda l: l.work_entry_type_id.code in ['137.00', '137.20'])
        for leave in economic_unemployement_leaves:
            version = leave.employee_id.sudo()._get_version(date=leave.date_from)
            if leave.work_entry_type_id.code == '137.00':
                if not version.is_worker() or version._is_artist():
                    raise ValidationError(self.env._("Code 137.00 cannot be used for an employee who is not a worker or who is artist worker"))
            else:
                # 137.20 case
                if version.is_worker() and not version._is_artist():
                    raise ValidationError(self.env._("Code 137.20 cannot be used for a worker, unless they have an artist status"))

    def _l10n_be_get_relapse_data(self):
        """Look up, for every leave in self, whether it can be a sickness relapse.

        Returns a dict {leave: (can_relapse, allowed_origin_leave_ids, origin_leave_id)}.
        Shared by `_compute_can_relapse` and `_compute_l10n_be_sickness_relapse_origin_leave_id` so both stay in sync.
        """
        sick_work_entry_types_codes = ['013.00', '122.00', '123.00', '010.00', '082.00', '072.00', '082.01', '072.01']

        # Only a sickness can be the relapse of an earlier one.
        # Without this the field shows up on any leave, an attendance included.
        l10n_be_leaves = self.filtered(
            lambda leave:
            leave.company_id.country_code == "BE"
            and leave.validation_type == "hr"
            and leave.employee_id
            and leave.date_from
            and leave.work_entry_type_id.code in sick_work_entry_types_codes
        )

        result = {leave: (False, [], False) for leave in (self - l10n_be_leaves)}

        if l10n_be_leaves:
            sickness_relapse_period_per_year = dict()
            leaves_by_date = l10n_be_leaves.grouped(lambda l: l.date_from.date())
            for date_from in leaves_by_date:
                relapse_period = sickness_relapse_period_per_year.get(date_from.year)
                if not relapse_period:
                    relapse_period = self.env["hr.rule.parameter"].sudo()._get_parameter_from_code("sickness_relapse_period_days", date=date_from, raise_if_not_found=False) or 0
                    sickness_relapse_period_per_year[date_from.year] = relapse_period

            previous_leaves = self.env['hr.leave'].search(
                domain=[
                    ("employee_id.id", "in", l10n_be_leaves.employee_id.ids),
                    ("date_to", "<=", max(l10n_be_leaves.mapped("date_from"))),
                    ("work_entry_type_id.code", "in", sick_work_entry_types_codes),
                    ("state", "=", "validate"),
                ],
            )

            for employee_id, leaves in l10n_be_leaves.grouped('employee_id').items():
                for leave in leaves:
                    relapse_period = sickness_relapse_period_per_year.get(leave.date_from.year)
                    leaves_in_relapse_period = previous_leaves.filtered_domain([
                        ("employee_id.id", '=', employee_id.id),
                        ("date_to", "<=", leave.date_from),
                    ]).sorted('date_to')

                    leaves_in_relapse_period = leaves_in_relapse_period[bisect_left(leaves_in_relapse_period, True, key=lambda l: self._get_relapse_days_between(l, leave) <= relapse_period):]
                    # If relapses already exist for the sickness, we only keep the last relapse in date
                    existing_relapse_origin_leave_ids = leaves_in_relapse_period.l10n_be_sickness_relapse_origin_leave_id.ids
                    leaves_in_relapse_period = leaves_in_relapse_period.filtered(lambda l: l.id not in existing_relapse_origin_leave_ids)

                    previous_day = leaves_in_relapse_period.filtered(lambda l: l.date_to.date() + relativedelta(days=1) == leave.date_from.date()).sorted('date_to', reverse=True)[:1]
                    if previous_day:
                        origin_leave_id = previous_day.id
                    else:
                        # No day-before match: keep whatever origin is already set, as long as it still makes sense.
                        # An unsaved form holds the user's pick in cache, a saved record only in database.
                        origin_field = leave._fields['l10n_be_sickness_relapse_origin_leave_id']
                        current_origin = (
                            leave.l10n_be_sickness_relapse_origin_leave_id
                            if leave.id in origin_field._get_cache(leave.env)
                            else leave._origin.l10n_be_sickness_relapse_origin_leave_id
                        )
                        origin_leave_id = current_origin.id if (
                            current_origin
                            and current_origin.employee_id == leave.employee_id
                            and current_origin.date_to <= leave.date_from
                        ) else False
                    result[leave] = (bool(leaves_in_relapse_period), leaves_in_relapse_period.ids, origin_leave_id)

        return result

    @api.depends("date_from", "validation_type", "employee_id", "work_entry_type_id.code", "company_id")
    def _compute_can_relapse(self):
        relapse_data = self._l10n_be_get_relapse_data()
        for leave in self:
            can_relapse, allowed_origin_leave_ids, origin_leave_id = relapse_data[leave]
            leave.l10n_be_sickness_can_relapse = can_relapse
            leave.allowed_l10n_be_sickness_relapse_origin_leave_ids = allowed_origin_leave_ids
            if leave.l10n_be_sickness_relapse_origin_leave_id.id != origin_leave_id:
                leave._compute_l10n_be_sickness_relapse_origin_leave_id()

    @api.depends("date_from", "validation_type", "employee_id", "work_entry_type_id.code", "company_id")
    def _compute_l10n_be_sickness_relapse_origin_leave_id(self):
        # Kept separate from _compute_can_relapse so setting this field on create doesn't skip recomputing the other two.
        relapse_data = self._l10n_be_get_relapse_data()
        for leave in self:
            leave.l10n_be_sickness_relapse_origin_leave_id = relapse_data[leave][2]

    @api.model
    def _get_relapse_days_between(self, leave_origin, leave_relapse):
        # This method computes the number of calendar days between two leaves, excluding absences
        inbetween_leaves = self.env['hr.leave'].search(
            domain=[
                ('employee_id.id', '=', leave_origin.employee_id.id),
                ('date_from', '>=', leave_origin.date_to),
                ('date_to', '<=', leave_relapse.date_from),
                ('work_entry_type_id.count_as', '=', 'absence'),
                ('state', '=', 'validate'),
            ],
        )
        return self._get_calendar_days_between_leaves(leave_origin, leave_relapse) - sum(leave._get_calendar_days() for leave in inbetween_leaves)

    @api.depends('l10n_be_sickness_relapse_origin_leave_id')
    def _compute_l10n_be_sickness_relapse(self):
        for leave in self:
            leave.l10n_be_sickness_relapse = leave.company_id.country_code == "BE" and bool(leave.l10n_be_sickness_relapse_origin_leave_id)

    def _issues_dependencies(self):
        return super()._issues_dependencies() + ['work_entry_type_id', 'date_from', 'date_to', 'employee_id', 'l10n_be_sickness_relapse', 'state', 'category_options_ids']

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self._check_create_wech010()
        return res

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in ('state', 'date_from', 'date_to', 'employee_id', 'work_entry_type_id')):
            self._check_create_wech010()
        return res

    def _check_create_wech010(self):
        youth_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_youth_time_off', raise_if_not_found=False)
        youth_holiday_risk_id = self.env.ref('l10n_be_hr_payroll.drs_risk_wech010_001').id
        senior_holiday_risk_id = self.env.ref('l10n_be_hr_payroll.drs_risk_wech010_002').id
        leaves_to_check = self.filtered(lambda leave: leave.work_entry_type_id == youth_type and leave.state == 'validate')
        if not youth_type or not leaves_to_check:
            return
        existing_drs = self.env['l10n.be.drs']._read_group([
            ('risk_id', 'in', (youth_holiday_risk_id, senior_holiday_risk_id)),
            ('employee_id', 'in', leaves_to_check.employee_id.ids),
        ], groupby=['risk_id', 'employee_id', 'year', 'month'], aggregates=['id:recordset'])
        existing_drs_dict = {(r, e.id, y, m): drs for r, e, y, m, drs in existing_drs}
        drs_vals = []
        for leave in leaves_to_check:
            # Right to youth holidays is defined based on the age at the end of the year
            # at which the employee takes the holidays
            age = leave.employee_id._get_age(leave.date_from.replace(month=12, day=31))
            if age < 25:
                risk_id = youth_holiday_risk_id
            elif age >= 50:
                risk_id = senior_holiday_risk_id
            else:
                continue
            l_month = leave.date_from.month
            l_year = leave.date_from.year
            if (risk_id, leave.employee_id, l_year, l_month) not in existing_drs_dict:
                drs_vals.append({
                    'is_automatically_created': True,
                    'employee_id': leave.employee_id.id,
                    'sector': 'unemployment',
                    'risk_id': risk_id,
                    'month': l_month,
                    'year': l_year,
                })
        self.env['l10n.be.drs'].create(drs_vals)

    def _get_calendar_days(self, date_min=date.min, date_max=date.max):
        self.ensure_one()
        leave_tz = ZoneInfo(self.tz)
        date_from = max(date_min, self.date_from.astimezone(leave_tz).date())
        date_to = min(date_max, self.date_to.astimezone(leave_tz).date())
        days = (date_to - date_from).days + 1
        if self.work_entry_type_request_unit == 'half_day':
            if self.request_date_from_period == self.request_date_to_period:
                return days - 0.5
            elif self.request_date_from_period == 'pm' and self.request_date_to_period == 'am':
                return days - 1
        return days

    def _l10n_be_is_progressive_resumption_neutralised(self):
        """Whether this leave's guaranteed salary is neutralised by progressive work resumption (122.04).

        Only applies to ordinary illness/accident, not occupational/work/commuting accidents.
        Up to 31/12/2025, applies only if incapacity occurs within the first 20 weeks (140 days).
        From 01/01/2026, applies for the entire progressive resumption period.
        Ongoing guaranteed salary from before 01/01/2026 is not affected.
        Ref: Art. 52 §5, Loi coord. 14/07/1994 (mod. Loi 19/12/2025, MB 30/12/2025).
        """
        self.ensure_one()
        version = self.employee_id.sudo()._get_version(date=self.date_from)
        is_progressive_resumption = any(
            att.work_entry_type_id.code == '122.04'
            for att in version.resource_calendar_id.attendance_ids
        )
        if not is_progressive_resumption:
            return False
        sick_leave_start = self.request_date_from
        if sick_leave_start >= date(2026, 1, 1):
            return True
        days_since_resumption_start = (sick_leave_start - version.date_start).days
        return days_since_resumption_start < 140

    def _get_l10n_be_sick_leave_split(self):
        """
        This method computes the sick leave split. In Belgium, if you take a sick leave, it might be paid at different
        levels depending on its duration, the employee worker code, and other variables.
        Examples (as of 2026):
            ~ For an employee, the salary is guaranteed for the first 30 days of sick leave. After that, it is not
                paid anymore by the employer. The relapse period is set to 56 days starting 01/01/2026.
                After 12 months of sickness, the leave switches to Long Term Sick (123.00),
                regardless of the 30-day paid/unpaid split above.
            ~ For a worker, rules are a bit different:
                - If the worker started less than one month ago: unpaid sick leave
                - The 7 first days: paid 100%
                - From 8 to 14 days: paid 85.88%
                - 15 to 30 days: paid 25.88% on the first 3464.43€ and 85.88% on the remaining amount above 3464.43€
                - after 30 days: unpaid
                - after 12 months Long term sickness
        Returns an *ordered* list of tuples where the key is the work entry type and the value the number of days
        """
        self.ensure_one()

        unpaid_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')

        leave_duration = self._get_calendar_days()
        version = self.employee_id.sudo()._get_version(date=self.date_from)
        is_worker = version.is_worker()
        is_short_term_employee = version.is_short_term_contract() and version.is_employee()

        if self._l10n_be_is_progressive_resumption_neutralised():
            return [(unpaid_sick_work_entry_type, leave_duration)]

        sick_work_entry_type_codes = ['013.00', '122.00', '123.00', '010.00', '082.00', '072.00', '082.01', '072.01']
        sick_work_entry_types = self.env['hr.work.entry.type'].search([
            ('code', 'in', sick_work_entry_type_codes),
            ('country_id.code', '=', 'BE')
        ])

        result = []
        paid_sick_work_entry_type = sick_work_entry_types.filtered(lambda w: w.code == '013.00')

        prev_sick_leaves_sum = 0
        prev_sick_leave = self
        if self.l10n_be_sickness_relapse:
            origin = self.l10n_be_sickness_relapse_origin_leave_id
            # A relapse must inherit the origin's genuine guaranteed-salary exhaustion.
            # It must not inherit unpaid status caused only by the origin's own progressive-resumption date window.
            origin_neutralised_by_progressive_resumption = origin._l10n_be_is_progressive_resumption_neutralised()
            if origin.work_entry_type_id.code == "122.00" and not origin_neutralised_by_progressive_resumption:
                return self._get_l10n_be_long_term_sick_split([(unpaid_sick_work_entry_type, leave_duration)])
            while prev_sick_leave.l10n_be_sickness_relapse:
                ancestor = prev_sick_leave.l10n_be_sickness_relapse_origin_leave_id
                # A neutralised ancestor's days were never charged against the guaranteed-salary budget.
                if not ancestor._l10n_be_is_progressive_resumption_neutralised():
                    prev_sick_leaves_sum += ancestor._get_calendar_days()
                prev_sick_leave = ancestor

        if is_worker or is_short_term_employee:
            first_contract_date = self.employee_id.sudo()._get_first_version_date()
            if not first_contract_date or (self.request_date_from < first_contract_date + relativedelta(months=1)):
                return [(unpaid_sick_work_entry_type, leave_duration)]

            first_week_sick_work_entry_type = sick_work_entry_types.filtered(lambda w: w.code == '010.00')
            second_week_sick_work_entry_type = (
                sick_work_entry_types.filtered(lambda w: w.code == "082.00")
                if is_worker
                else sick_work_entry_types.filtered(lambda w: w.code == "072.01")
            )
            third_fourth_week_sick_work_entry_type = sick_work_entry_types.filtered(lambda w: w.code == '072.00')
            total_counted_days = 0

            first_week_paid_days = min(leave_duration, max(0, 7 - prev_sick_leaves_sum))
            total_counted_days += first_week_paid_days
            if first_week_paid_days:
                result.append((first_week_sick_work_entry_type, first_week_paid_days))
            if total_counted_days >= leave_duration:
                return result

            second_week_paid_days = min(leave_duration - total_counted_days, max(0, 14 - prev_sick_leaves_sum - total_counted_days))
            total_counted_days += second_week_paid_days
            if second_week_paid_days:
                result.append((second_week_sick_work_entry_type, second_week_paid_days))
            if total_counted_days >= leave_duration:
                return result

            third_fourth_week_paid_days = min(leave_duration - total_counted_days, max(0, 30 - prev_sick_leaves_sum - total_counted_days))
            total_counted_days += third_fourth_week_paid_days
            if third_fourth_week_paid_days:
                result.append((third_fourth_week_sick_work_entry_type, third_fourth_week_paid_days))
            if total_counted_days >= leave_duration:
                return result

            unpaid_days = leave_duration - total_counted_days
            if unpaid_days:
                result.append((unpaid_sick_work_entry_type, unpaid_days))

        else:
            remaining_paid_sick_days = max(0, 30 - prev_sick_leaves_sum)
            paid_days = min(leave_duration, remaining_paid_sick_days)
            if paid_days:
                result.append((paid_sick_work_entry_type, paid_days))
            unpaid_days = leave_duration - paid_days
            if unpaid_days:
                result.append((unpaid_sick_work_entry_type, unpaid_days))

        return self._get_l10n_be_long_term_sick_split(result)

    def _get_l10n_be_long_term_sick_cutoff_date(self):
        """Return the date when this sickness chain crosses the twelve-month threshold."""
        self.ensure_one()
        return self.employee_id._l10n_be_get_sick_leave_twelve_months_cutoff_date(self.request_date_to, current_leave=self)

    def _get_l10n_be_long_term_sick_split(self, leave_split):
        """Convert the part of a sickness split after the twelve-month cutoff to LEAVE280."""
        self.ensure_one()
        if not leave_split:
            return leave_split

        leave_start = self.request_date_from
        cutoff_date = self._get_l10n_be_long_term_sick_cutoff_date()

        if cutoff_date > leave_start + relativedelta(days=sum(days for _, days in leave_split)):
            return leave_split

        long_term_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_long_sick')

        long_term_split = []
        current_date = leave_start
        for work_entry_type, nbr_days in leave_split:
            segment_end = current_date + relativedelta(days=nbr_days)
            if current_date >= cutoff_date:
                long_term_split.append((long_term_sick_work_entry_type, nbr_days))
            elif segment_end <= cutoff_date:
                long_term_split.append((work_entry_type, nbr_days))
            else:
                days_before_cutoff = (cutoff_date - current_date).days
                days_after_cutoff = nbr_days - days_before_cutoff
                if days_before_cutoff:
                    long_term_split.append((work_entry_type, days_before_cutoff))
                if days_after_cutoff:
                    long_term_split.append((long_term_sick_work_entry_type, days_after_cutoff))
            current_date = segment_end

        merged_split = []
        for work_entry_type, days in long_term_split:
            if merged_split and merged_split[-1][0] == work_entry_type:
                merged_split[-1] = (work_entry_type, merged_split[-1][1] + days)
            else:
                merged_split.append((work_entry_type, days))
        return merged_split

    def _get_l10n_be_work_accident_leave_split(self):
        """
        This method computes the work accident leave split. In Belgium, if you take a work accident leave, it might be
        paid at different levels depending on its duration, the employee worker code, and other variables.
        Examples (as of 2026):
            ~ For a worker (Ouvrier) or a CDD < 3 months employee (Employé):
                - The 7 first days: paid 100% (009.00)
                - From 8 to 30 days: paid 85.88% for workers / 86.93% for CDD < 3 months employees (082.01)
                - after 30 days: unpaid (110.00)
            ~ For a regular CDI employee (Employé):
                - The first 30 days: paid 100% (012.00)
                - after 30 days: unpaid (110.00)
        Returns an *ordered* list of tuples where the key is the work entry type and the value the number of days
        """
        self.ensure_one()

        leave_duration = self._get_calendar_days()
        version = self.employee_id.sudo()._get_version(date=self.date_from)
        is_worker = version.is_worker()
        is_short_term_employee = version.is_short_term_contract() and version.is_employee()

        unpaid_work_accident_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')

        work_accident_type_codes = ['009.00', '110.00', '012.00', '070.00', '082.01']
        work_accident_work_entry_types = self.env['hr.work.entry.type'].search([
            ('code', 'in', work_accident_type_codes),
            ('country_id.code', '=', 'BE')
        ])

        all_previous_work_accident_leaves = self.env['hr.leave'].search(
            [
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '<', self.date_from),
                ('work_entry_type_id', 'in', work_accident_work_entry_types.ids),
                ('state', '=', 'validate'),
            ],
            order="date_from desc",
        )

        prev_work_accident_leaves_sum = 0
        prev_work_accident_leave = self

        for leave in all_previous_work_accident_leaves:
            duration_between_leaves = self._get_calendar_days_between_leaves(leave, prev_work_accident_leave)
            if duration_between_leaves > 0:
                break

            prev_work_accident_leaves_sum += leave._get_calendar_days()

            if prev_work_accident_leaves_sum > 30:
                # after 30 work accident days, it becomes unpaid
                return [(unpaid_work_accident_work_entry_type, leave_duration)]

            prev_work_accident_leave = leave

        result = []

        if is_worker or is_short_term_employee:
            first_week_work_accident_work_entry_type = work_accident_work_entry_types.filtered(lambda w: w.code == '009.00')
            first_month_work_accident_work_entry_type = (
                work_accident_work_entry_types.filtered(lambda w: w.code == "070.00")
                if is_worker
                else work_accident_work_entry_types.filtered(lambda w: w.code == "082.01")
            )
            total_counted_days = 0

            first_week_paid_days = min(leave_duration, max(0, 7 - prev_work_accident_leaves_sum))
            total_counted_days += first_week_paid_days
            if first_week_paid_days:
                result.append((first_week_work_accident_work_entry_type, first_week_paid_days))
            if total_counted_days >= leave_duration:
                return result

            first_month_paid_days = min(leave_duration - 7, max(0, 30 - prev_work_accident_leaves_sum - total_counted_days))
            total_counted_days += first_month_paid_days
            if first_month_paid_days:
                result.append((first_month_work_accident_work_entry_type, first_month_paid_days))
            if total_counted_days >= leave_duration:
                return result

            unpaid_days = leave_duration - total_counted_days
            if unpaid_days:
                result.append((unpaid_work_accident_work_entry_type, unpaid_days))

        else:
            # Regular CDI employee: 30d 012.00 (100%), then 110.00 (unpaid)
            first_month_work_accident_work_entry_type = work_accident_work_entry_types.filtered(lambda w: w.code == '012.00')
            remaining_paid_days = max(0, 30 - prev_work_accident_leaves_sum)
            paid_days = min(leave_duration, remaining_paid_days)
            if paid_days:
                result.append((first_month_work_accident_work_entry_type, paid_days))
            unpaid_days = leave_duration - paid_days
            if unpaid_days:
                result.append((unpaid_work_accident_work_entry_type, unpaid_days))

        return result

    def _get_l10n_be_economic_unemployment_split(self):
        """
        This method computes the economic unemployment split. In Belgium, if you take a there is a public holiday
        in the first 14 days of economic umemployment for employees it must be paid
        Examples (as of 2026):
            For an employee, the salary of the public holiday is to be paid in the employee's payslip if it falls
            within the first 14 days of their economic unemployment
        Returns an *ordered* list of tuples where the key is the work entry type and the value the number of days
        """
        self.ensure_one()
        version = self.employee_id.sudo()._get_version(date=self.date_from)
        is_worker = version.is_worker()
        if is_worker:
            return self._get_l10n_be_economic_unemployment_split_worker()
        else:
            return self._get_l10n_be_economic_unemployment_split_employee()

    def _get_l10n_be_economic_unemployment_split_employee(self):
        """
        Splits the unemployment leave of an employee on the public holidays the employer still covers.
        Only the holidays falling in the first 14 calendar days of the unemployment are covered,
        the ones after that stay plain economic unemployment days paid by the ONEM.
        """
        # Day 1 is the first day of the leave, so the 14 day window ends 13 days later
        last_covered_date = min(self.request_date_from + relativedelta(days=13), self.request_date_to)
        public_holiday_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday')
        public_holiday_leaves = self.env['resource.calendar.leaves'].search([
            ('work_entry_type_id', '=', public_holiday_work_entry_type.id),
            ('date_from', '<=', last_covered_date + relativedelta(days=1)),
            ('date_to', '>=', self.request_date_from),
        ],
        order="date_from asc")
        leave_tz = ZoneInfo(self.tz)
        # Intervals are half open, so every segment stops on the day after its own last day
        unemployment_start = self.request_date_from
        unemployment_end = self.request_date_to + relativedelta(days=1)
        covered_end = last_covered_date + relativedelta(days=1)
        public_holiday_leaves_tuples = []
        for leave in public_holiday_leaves:
            # Stored datetimes are naive UTC, make them aware before reading their local date
            start = leave.date_from.replace(tzinfo=UTC).astimezone(leave_tz).date()
            end = leave.date_to.replace(tzinfo=UTC).astimezone(leave_tz).date() + relativedelta(days=1)
            # Keep only the part of the holiday that really overlaps the covered window
            start, end = max(start, unemployment_start), min(end, covered_end)
            if start < end:
                public_holiday_leaves_tuples.append((
                    start, end,
                    self.env.ref('hr_work_entry.l10n_be_work_entry_type_public_holiday_temporary_unemployment'),
                ))
        public_holiday_intervals = Intervals(public_holiday_leaves_tuples)
        economic_unemployment_intervals = Intervals([(unemployment_start, unemployment_end, self.work_entry_type_id)])
        remaining_economic_intervals = economic_unemployment_intervals - public_holiday_intervals
        merged_leave_intervals = sorted(
            list(remaining_economic_intervals) + list(public_holiday_intervals),
            key=lambda interval: interval[0]
        )
        if not merged_leave_intervals:
            return [(self.work_entry_type_id, self._get_calendar_days())]
        # Every segment is bounded now, so its duration is just the number of calendar days it spans
        return [(work_entry_type, (end - start).days) for start, end, work_entry_type in merged_leave_intervals]

    def _get_l10n_be_economic_unemployment_split_worker(self):
        """
        This method splits either a 137.00 | 151.00 | 152.00 (all temporary unemployment) that overlaps one or multiple public holidays into subsegments.
        The public holidays are converted from 006.00 into 086.00 or 006.11 depending on the amount
        of days of unemployment for the worker in the current year.

        In times of temporary unemployment for a worker and on a public holiday day, the employer covers for ONSS. (006.11)
        But when it becomes to long, some days are exceptions and employee may pay only the taxable part (086.00).
        There's a quota table that depends on the work regime and the total of unemployment days since the beginning of the year.

        Example:
            public_holiday : 25th of December
            137.00 : from 20th of December until 28th of December

            After validation, the leave should be divided into three segments:
                - 20/12 -> 24/12 - 137.00
                - 25/12 -> 25/12 - 086.00 or 006.11
                - 26/12 -> 28/12 - 137.00

        In order to decide between 006.11 and 086.00, we first need to gather the sum of work entries for
            - 137.00 + 152.00 + 151.00
            - 086.00
        This gives a quota that gives a quantity of 086.00 can be allocated. If that amount is greater than 0,
        we opt for 086.00, otherwise we allocate 006.11.

        Returns an *ordered* list of tuples where the key is the work entry type and the value the number of days
        """
        self.ensure_one()
        employee = self.employee_id
        if not employee.version_id.is_worker():
            # relevant only for workers
            raise ValidationError(self.env._("This method only applies for workers."))

        def _split_on_public_holidays(public_holidays):
            """ Splits (virtually) the current leave into subsegments (depending on public holidays) """
            segment_leaves = self.env['hr.leave']

            def _add(start, end, is_ph):
                nonlocal segment_leaves
                if start > end:
                    return

                leave = self.env['hr.leave'].new({
                    'employee_id': self.employee_id.id,
                    'date_from': start,
                    'date_to': end,
                    # default work entry type - used to differentiate whether it's public holiday or not
                    # the value will be reevaluated later in the process
                    'work_entry_type_id': work_entry_types_hashmap['006.00']
                        if is_ph else work_entry_types_hashmap['137.00'],
                })
                segment_leaves |= leave

            current_date_from = self.date_from
            for ph in public_holidays:
                _add(current_date_from, ph.date_from - timedelta(seconds=1), False)
                _add(ph.date_from, ph.date_to, True)

                current_date_from = ph.date_to + timedelta(seconds=1)

            _add(current_date_from, self.date_to, False)

            return segment_leaves

        relevant_work_entry_type_codes = {
            '086.00',     # temporary unemployment - public holiday - no onss
            '006.11',     # temporary unemployment - public holiday - with onss
            '137.00',    # temporary unemployment - normal day
            '152.00',     # temporary unemployment - normal day
            '151.00',     # temporary unemployment - normal day
            '006.00',     # public holiday
        }
        relevant_work_entry_types = self.env['hr.work.entry.type'].search([
            ('country_id.code', '=', 'BE'),
            ('code', 'in', relevant_work_entry_type_codes),
        ])
        unemployment_work_entry_types = relevant_work_entry_types.filtered(lambda we: we.code in {'151.00', '152.00', '137.00'})
        work_entry_types_hashmap = relevant_work_entry_types.grouped('code')

        public_holidays = self.env['resource.calendar.leaves'].search([
            ('work_entry_type_id', '=', work_entry_types_hashmap['006.00'].id),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('company_id', '=', employee.company_id.id),
            '|',
                ('calendar_id', '=', False),
                ('calendar_id', '=', employee.resource_calendar_id.id),
        ])

        years_covered = {self.date_from.year, self.date_to.year}
        min_date_fetch_leaves = datetime.combine(date(min(years_covered), 1, 1), datetime.min.time())

        # relevant codes = unemployment + 207
        previous_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('date_to', '>=', min_date_fetch_leaves),
            ('date_from', '<', self.date_from),
            ('state', '=', 'validate'),
            ('work_entry_type_id', 'in', (unemployment_work_entry_types | work_entry_types_hashmap['006.11']).ids),
        ])

        previous_leaves = self._virtual_strip(previous_leaves, min_date_fetch_leaves, self.date_from)
        previous_leaves = self._virtual_split(previous_leaves)

        current_leave_split = _split_on_public_holidays(public_holidays)
        current_leave_split = self._virtual_split(current_leave_split)

        all_leaves_durations = (previous_leaves | current_leave_split)._get_durations()
        segment_calendar_days = {leave.id: leave._get_calendar_days() for leave in current_leave_split}

        segments = []
        previous_leaves_by_year = previous_leaves.grouped(lambda l: l.date_from.year)
        current_leave_split_by_year = current_leave_split.grouped(lambda l: l.date_from.year)
        # in case the current_leave is straddling two years
        for current_year in years_covered:
            # compute YTD temporary unemployment and 006.11
            counter = Counter()
            for leave in previous_leaves_by_year.get(current_year, self.env['hr.leave']):
                counter[leave.work_entry_type_id.code] += all_leaves_durations.get(leave.id, (0, 0))[0]

            unemployment_days = sum(counter[t.code] for t in unemployment_work_entry_types)
            amount_086_days_allocated = counter['086.00']

            # progress into this leave - increment the amount of temporary unemployment
            # and allocate 006.11 or 086.00 depending on the just-in-time quota
            for segment_leave in current_leave_split_by_year.get(current_year, self.env['hr.leave']):
                working_days = all_leaves_durations.get(segment_leave.id, (0, 0))[0]
                calendar_days = segment_calendar_days.get(segment_leave.id)

                is_ph = (segment_leave.work_entry_type_id == work_entry_types_hashmap['006.00'])
                if is_ph:
                    amount_086_available = self._get_amount_leave086_exemptions(unemployment_days) - amount_086_days_allocated
                    # Public holiday on multiple days is an edge case that is not supposed to happen in Belgium
                    if calendar_days > 1:
                        raise UserError(self.env._("Public holiday is not meant to be more than one day long."))
                    if amount_086_available > 0:
                        work_entry_type = work_entry_types_hashmap['086.00']
                        amount_086_days_allocated += 1
                    else:
                        work_entry_type = work_entry_types_hashmap['006.11']
                else:
                    unemployment_days += working_days
                    work_entry_type = self.work_entry_type_id

                segments.append((work_entry_type, calendar_days))
        previous_leaves.invalidate_recordset()
        current_leave_split.invalidate_recordset()

        return segments

    def _action_validate(self, check_state=True):
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        res_model_id = self.env.ref('hr_holidays.model_hr_leave').id
        all_l10n_be_concerned_leaves = self.filtered(
            lambda leave: leave.company_id.country_code == 'BE'
                          and leave.employee_id
                          and leave.date_from
                          and leave.date_to
                          and any([
                leave.work_entry_type_id.code == '013.00',    # Sick leave
                leave.work_entry_type_id.code == '009.00',    # Work accident leave
                leave.work_entry_type_id.code == '137.20',  # Temporary unemployment for employee and artists
                leave.work_entry_type_id.code in {
                    '137.00',    # Economic unemployment
                    '152.00',     # Temporary unemployment due to technical incident
                    '151.00',     # Temporary unemployment due to bad weather
                    } and leave.employee_id.version_id.is_worker(),
            ])
        ).sorted('request_date_from')

        l10n_be_concerned_leaves_by_employee = all_l10n_be_concerned_leaves.grouped('employee_id')
        res = True
        for _, l10n_be_concerned_leaves in l10n_be_concerned_leaves_by_employee.items():
            for l10n_be_concerned_leave in l10n_be_concerned_leaves:
                match l10n_be_concerned_leave.work_entry_type_id.code:
                    case '013.00':
                        leave_split = l10n_be_concerned_leave._get_l10n_be_sick_leave_split()
                        l10n_be_concerned_leave._check_8_weeks_sto()
                    case '009.00':
                        leave_split = l10n_be_concerned_leave._get_l10n_be_work_accident_leave_split()
                    case '137.20' | '151.00' | '152.00' | '137.00':
                        leave_split = l10n_be_concerned_leave._get_l10n_be_economic_unemployment_split()
                    case _:
                        leave_split = []
                new_leaves = l10n_be_concerned_leave._create_leaves_from_split(leave_split)
                res &= super(HrLeave, new_leaves)._action_validate(check_state=check_state)

        non_be_leaves = self - all_l10n_be_concerned_leaves
        res &= super(HrLeave, non_be_leaves)._action_validate(check_state=check_state)

        for leave in self:
            wet_code = leave.sudo().work_entry_type_id.code
            if leave.employee_id.company_id.country_id.code == "BE" and wet_code in self._get_drs_work_entry_type_codes():
                drs_link = "https://www.socialsecurity.be/site_fr/employer/applics/drs/index.htm"
                drs_link = '<a href="%s" target="_blank">%s</a>' % (drs_link, drs_link)
                user_ids = leave.employee_id.hr_responsible_id.ids
                note = self.env._('%(employee)s is in %(work_entry_type)s. Fill in the appropriate eDRS here: %(link)s',
                   employee=leave.employee_id.name,
                   work_entry_type=leave.work_entry_type_id.name,
                   link=drs_link)
                activity_vals = []
                for user_id in user_ids:
                    activity_vals.append({
                        'activity_type_id': activity_type_id,
                        'automated': True,
                        'note': note,
                        'user_id': user_id,
                        'res_id': leave.id,
                        'res_model_id': res_model_id,
                    })
                # TDE TODO: batch schedule with record-based note
                self.env['mail.activity'].create(activity_vals)
            if leave.employee_id.company_id.country_id.code == "BE" and wet_code in ['040.27', '040.28', '039.23']:
                cp200 = self.env.ref("l10n_be_hr_payroll.l10n_be_joint_committee_200")
                cp302 = self.env.ref("l10n_be_hr_payroll.l10n_be_joint_committee_302")
                voluntary_threshold_codes = {
                    (cp200, '039.23'): 'cp200_voluntary_overtime_no_onss_threshold',
                    (cp200, 'OTHER'): 'cp200_voluntary_overtime_threshold',
                    (cp302, '039.23', True): 'cp302_voluntary_overtime_no_onss_threshold_white_cash_register',
                    (cp302, 'OTHER', True): 'cp302_voluntary_overtime_threshold_white_cash_register',
                    (cp302, '039.23', False): 'cp302_voluntary_overtime_no_onss_threshold_not_white_cash_register',
                    (cp302, 'OTHER', False): 'cp302_voluntary_overtime_threshold_not_white_cash_register',
                }
                key = (
                    leave.employee_id.l10n_be_joint_committee_id,
                    wet_code if wet_code == '039.23' else 'OTHER',
                )
                if leave.employee_id.l10n_be_joint_committee_id == cp302:
                    key += (leave.employee_id.company_id.l10n_be_cash_register_active,)
                threshold_code = voluntary_threshold_codes.get(key)
                if threshold_code:
                    threshold = self.env['hr.rule.parameter']._get_parameter_from_code(threshold_code, leave.request_date_from)
                    wet_refs = (
                        self.env.ref("hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_net")
                        if wet_code == "039.23"
                        else (
                            self.env.ref("hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_150")
                            + self.env.ref("hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_200")
                        )
                    )
                    declared_hours = sum(self.env['hr.leave'].search([
                        ('id', '!=', leave.id),
                        ('employee_id', '=', leave.employee_id.id),
                        ('request_date_from', '>=', date(leave.request_date_from.year, 1, 1)),
                        ('request_date_to', '<=', date(leave.request_date_from.year, 12, 31)),
                        ('work_entry_type_id', 'in', wet_refs.ids),
                        ('state', '=', 'validate'),
                    ]).mapped('number_of_hours'))
                    if declared_hours + leave.number_of_hours > threshold:
                        raise ValidationError(
                            self.env._(
                                "Voluntary Threshold Exceeded: %(employee_name)s has already %(declared_hours)s hours of %(wet_name)s. Validating this new time of %(amount)s hours would exceed the threshold of %(threshold)s hours.",
                                employee_name=leave.employee_id.name,
                                declared_hours=round(declared_hours, 2),
                                wet_name=', and '.join(wet_refs.mapped('name')) + (' combined' if len(wet_refs) > 1 else ''),
                                amount=round(leave.number_of_hours, 2),
                                threshold=threshold,
                            ),
                        )
        return res

    def _get_extra_default_leave_values_for_split(self):
        self.ensure_one()
        return {
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': self.id,
        }

    def _get_drs_work_entry_type_codes(self):
        drs_work_entry_types = [
            '146.00',  # Breast Feeding
            '123.00',  # Long Term Sick
            '128.00',  # Maternity
            '128.05',  # Paternity Time Off (Legal)
            '142.99',  # Youth Time Off
            '009.00',  # Work Accident
        ]
        return drs_work_entry_types

    def _get_max_duration(self, code, jc):
        durations = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'leave_durations_by_jc', raise_if_not_found=False) or {}
        duration_per_jc = durations.get(code)
        if not duration_per_jc:
            return False
        return duration_per_jc.get(jc.egov3_code if jc else None, duration_per_jc.get(None))

    def _check_max_duration_exceeded(self):
        """ The legal duration depends either on the option picked on the time off
        (circumstantial leaves all share a single time type) or, for the time types
        that kept a dedicated code, on that code. """
        self.ensure_one()
        jc = self.sudo().employee_id.l10n_be_joint_committee_id
        codes = self.sudo().category_options_ids.mapped('code')
        if self.work_entry_type_id.code:
            codes.append(self.work_entry_type_id.code)
        for code in codes:
            max_duration = self._get_max_duration(code, jc)
            if max_duration:
                return self.number_of_days > max_duration, jc, max_duration
        return False, jc, False

    def action_l10n_be_correct_without_certificate(self):
        """ Only the first day of a sick time off may be flagged without certificate:
        keep that day on the request and move the remainder to a new one. """
        for leave in self:
            option = leave.sudo().category_options_ids.filtered(lambda c: c.code == 'MISSING_CERTIFICATE')
            if leave.number_of_days <= 1 or not option:
                continue
            remainder = leave._split_leaves(leave.request_date_from + timedelta(days=1))
            remainder.sudo().category_options_ids = [(3, option.id)]

    def _get_amount_leave086_exemptions(self, amount_unemployment_days):
        if not (0 <= amount_unemployment_days <= 366):
            raise UserError(self.env._("Number of unemployment days must be between 0 and 366. Current value : %s") % amount_unemployment_days)

        calendar = self.employee_id.version_id.resource_calendar_id
        match calendar.days_per_week:
            case 5.0:
                leave207_quota_table = self.env['hr.rule.parameter']._get_parameter_from_code(
                    'l10n_be_workers_leave086_quota_5_days_regime')
            case 6.0:
                leave207_quota_table = self.env['hr.rule.parameter']._get_parameter_from_code(
                    'l10n_be_workers_leave086_quota_6_days_regime')
            case _:
                raise UserError(self.env._("The working regime must be equal to 5.0 or 6.0 days per week."))

        for unemployment_days_range, leave086_available in leave207_quota_table:
            min_days, max_days = unemployment_days_range
            if min_days <= amount_unemployment_days <= max_days:
                return leave086_available

        # unreachable code - panic
        raise ValidationError(
            self.env._(
                "Configuration error: The unemployment quota table is incomplete. "
                "No matching range found for %s days."
            ) % amount_unemployment_days
        )

    def _virtual_split(self, leaves):
        """ Splits leaves (virtually) leaping over two years into to subsegments"""
        straddling = leaves.filtered(lambda leave: leave.date_from.year != leave.date_to.year)
        result = leaves - straddling

        for leave in straddling:
            year_from, year_to = leave.date_from.year, leave.date_to.year

            year_from_part = self.env['hr.leave'].new({
                'employee_id': leave.employee_id.id,
                'date_from': leave.date_from,
                'date_to': date(year_from, 12, 31),
                'work_entry_type_id': leave.work_entry_type_id.id,
            })
            year_to_part = self.env['hr.leave'].new({
                'employee_id': leave.employee_id.id,
                'date_from': date(year_to, 1, 1),
                'date_to': leave.date_to,
                'work_entry_type_id': leave.work_entry_type_id.id,
            })
            result |= year_from_part | year_to_part

        return result

    def _virtual_strip(self, leaves, min_datetime, max_datetime):
        """ Strips leaves (virtually) into boundaries """
        result = self.env['hr.leave']

        for leave in leaves:
            new_date_from = max(leave.date_from, min_datetime)
            new_date_to = min(leave.date_to, max_datetime)
            if new_date_from > new_date_to:
                continue
            if new_date_from == leave.date_from and new_date_to == leave.date_to:
                result |= leave
            else:
                result |= self.env['hr.leave'].new({
                    'employee_id': leave.employee_id.id,
                    'date_from': new_date_from,
                    'date_to': new_date_to,
                    'work_entry_type_id': leave.work_entry_type_id.id,
                })

        return result

    def _check_8_weeks_sto(self):
        """
        This method checks if an employee has 8 weeks of consecutive sick leaves to
        allow the payroll officer to contact the occupational therapy
        """
        for leave in self:
            origin = leave
            sick_days = leave._get_calendar_days()
            while origin.l10n_be_sickness_relapse_origin_leave_id:
                origin = origin.l10n_be_sickness_relapse_origin_leave_id
                sick_days += origin._get_calendar_days()
            if sick_days < 56:
                continue
            employee = leave.employee_id
            date_deadline = origin.request_date_from + relativedelta(months=6)
            if employee.activity_ids.filtered(
                lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO' and a.date_deadline == date_deadline
            ):
                continue
            employee.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=date_deadline,
                summary=self.env._('Contact occupational medicine for %(employee)s', employee=employee.name),
                note=self.env._('%(employee)s has been sick for 8 consecutive weeks: contact the occupational medicine to assess their work capacity.', employee=employee.name),
                user_id=employee.hr_responsible_id.id or self.env.user.id,
                technical_usage='l10n_be_hr_payroll_8_weeks_STO',
            )
