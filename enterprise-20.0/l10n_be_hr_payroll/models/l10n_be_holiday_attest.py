from bisect import bisect_right
from collections import defaultdict
from datetime import date

from babel.dates import format_date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round
from odoo.tools.misc import get_lang


# ONVA minimum equivalent-day thresholds for earning 1 through 20 legal vacation days on a five-day schedule.
ONVA_ASSIMILATED_DAY_THRESHOLDS = (
    10, 20, 39, 48, 64, 77, 87, 97, 106, 125, 135, 144, 154, 163, 182, 192, 202, 212, 221, 231,
)


class L10nBeHolidayAttest(models.Model):
    _name = "l10n.be.holiday.attest"
    _description = "CP200: Holiday Attestation"
    _rec_name = "display_name"

    # Employee data
    employee_id = fields.Many2one(comodel_name="hr.employee", ondelete="cascade", index="btree_not_null", required=True)
    company_id = fields.Many2one(related="employee_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    version_id = fields.Many2one(comodel_name="hr.version", compute="_compute_version_id", store=True, index=True)
    l10n_be_daily_wage = fields.Monetary(related="version_id.l10n_be_daily_wage")
    attest_type = fields.Selection(
        selection=[
            ("employee", "Employee"),
            ("worker", "Worker"),
        ],
        string="Worked As",
        required=True,
        default="employee",
        help="Type of the previous occupation on the holiday certificate. "
             "Worker holiday pay is paid by the holiday fund; recovery only applies if the person is now an employee.",
    )

    # Data input from a physical certificate
    date_from = fields.Date(
        string="From",
        required=True,
        default=lambda self: date(fields.Date.context_today(self).year - 1, 1, 1),
    )
    date_to = fields.Date(
        string="To",
        required=True,
        default=lambda self: date(fields.Date.context_today(self).year - 1, 12, 31),
    )
    year = fields.Integer(compute="_compute_year")
    prev_assimilated_days = fields.Integer(
        string="Assimilated day(s)",
        help="Days worked and assimilated (e.g. sick leave, public holidays) at the previous employer.",
        compute="_compute_prev_assimilated_days",
        store=True,
        readonly=False,
    )
    prev_work_hours_per_week = fields.Float(
        string="Q",
        default=38,
        help="""Working ratio at previous employer.
        Q: Hours per week worked by the employee at their previous employer.
        S: Reference working hours per week at the previous employer's company.""",
    )
    prev_reference_work_hours_per_week = fields.Float(
        string="S",
        default=38,
        help="""Working ratio at previous employer.
        Q: Hours per week worked by the employee at their previous employer.
        S: Reference working hours per week at the previous employer's company.""",
    )
    prev_work_time_rate = fields.Float(
        string="Work Time Rate",
        help="Decimal ratio of hours worked to reference hours, e.g. 0.9 for 36h/40h.",
        compute="_compute_prev_work_time_rate",
    )
    prev_work_days_per_week = fields.Float(
        string="Working day(s) per week",
        default=5,
        required=True,
        help="Number of working days per week at the previous employer e.g. 5 days",
    )
    prev_simple_holiday_pay_paid = fields.Monetary(
        string="Simple Holiday Pay",
        help="The amount of simple holiday pay paid by the previous employer",
        required=True,
        default=0,
    )
    prev_double_holiday_pay_paid = fields.Monetary(
        string="Double Holiday Pay",
        required=True,
        default=0,
        help="The amount of double holiday pay paid by the previous employer",
    )
    prev_days_earned = fields.Float(
        string="Remaining Holiday(s)",
        help="Total days of holiday entitlement earned at the previous employer",
    )

    # Computed Limits/Caps
    work_time_rate_change_ratio = fields.Float(
        help="Ratio of the employee's current work time rate to their previous one. Used to scale leave days and pay amounts when their schedule has changed.",
        compute="_compute_work_time_rate_change_ratio",
    )
    limit_hours = fields.Float(
        string="Maximum Recoverable Hour(s)",
        compute="_compute_limit_hours",
        store=True,
        help="The number of leave hours this employee is entitled to, adjusted for potentially changing working schedules and capped at the legal limit.",
    )

    simple_holiday_pay_cap = fields.Monetary(
        string="Simple holiday pay to recover",
        compute="_compute_simple_holiday_pay_cap",
        help="The amount of simple holiday pay to recover, adjusted for potentially changing working schedules and capped at the legal limit.",
    )
    double_holiday_pay_cap = fields.Monetary(
        string="Double holiday pay to recover",
        compute="_compute_double_holiday_pay_cap",
        help="The amount of double holiday pay to recover, adjusted for potentially changing working schedules and capped at the legal limit.",
    )

    hours_to_allocate = fields.Float(
        string="Holiday hour(s) to allocate",
        compute="_compute_hours_to_allocate",
    )
    days_to_allocate = fields.Float(
        string="Holiday(s) to allocate",
        compute="_compute_days_to_allocate",
    )
    leave_allocation_id = fields.Many2one(
        comodel_name="hr.leave.allocation",
        ondelete="cascade",
    )
    allocation_to_link_id = fields.Many2one(
        comodel_name="hr.leave.allocation",
        ondelete="set null",
        domain="[('id', 'in', linkable_allocation_ids)]",
        store=False,
    )
    linkable_allocation_ids = fields.Many2many(
        comodel_name="hr.leave.allocation",
        compute="_compute_linkable_allocation_ids",
    )

    # Computed fields for display in the views
    allocation_warning_message = fields.Char(compute="_compute_allocation_warning")
    allocation_conversion_message = fields.Text(compute="_compute_allocation_conversion_message")

    simple_holiday_pay_amount_recovered = fields.Monetary(
        help="Total SHP amount recovered across all payslips for this attestation.",
        compute="_compute_simple_holiday_pay_amount_recovered",
    )
    double_holiday_pay_amount_recovered = fields.Monetary(
        help="Total DHP amount recovered across all payslips for this attestation.",
        compute="_compute_double_holiday_pay_amount_recovered",
    )
    prev_total_holiday_pay_paid = fields.Monetary(
        string="Total paid",
        compute="_compute_prev_total_holiday_pay_paid",
        inverse="_inverse_prev_total_holiday_pay_paid",
    )

    attestation_warning_message = fields.Char(compute="_compute_attestation_warning")
    has_contract_wage = fields.Boolean(compute="_compute_has_contract_wage")
    is_worker = fields.Boolean(compute="_compute_is_worker")

    issues = fields.Json(compute='_compute_issues', groups="hr.group_hr_user,hr_payroll.group_hr_payroll_user")

    # -----------
    # Constraints
    # -----------

    _check_prev_work_days_per_week = models.Constraint(
        "check(prev_work_days_per_week >= 1 and prev_work_days_per_week <= 7)",
        "Working days per week must be between 1 and 7.",
    )

    # --------
    # Computes
    # --------

    @api.depends_context("lang")
    @api.depends("date_from", "date_to", "employee_id")
    def _compute_display_name(self):
        locale = get_lang(self.env).code
        for attestation in self:
            if not attestation.employee_id or not attestation.date_from or not attestation.date_to:
                attestation.display_name = self.env._("Holiday Attestation")
            else:
                attestation.display_name = self.env._(
                    "%(employee_name)s Holiday Attestation: %(date_from)s - %(date_to)s",
                    employee_name=attestation.employee_id.name,
                    date_from=format_date(attestation.date_from, locale=locale),
                    date_to=format_date(attestation.date_to, locale=locale),
                )

    @api.depends("employee_id", "year")
    def _compute_version_id(self):
        """
        Pin the version to the holiday year (attestation.year + 1) so leave is priced at the salary the employee earns
        when they actually take it, not the older attestation-year salary. Today's version is used if we are currently
        inside that year, otherwise it is clamped to the year's boundaries.
        """
        today = fields.Date.today()
        for attestation in self:
            employee = attestation.employee_id._origin
            if not employee.version_ids or not attestation.year:
                attestation.version_id = False
                continue

            holiday_year_start = date(attestation.year + 1, 1, 1)
            holiday_year_end = date(attestation.year + 1, 12, 31)
            reference_end = max(min(today, holiday_year_end), holiday_year_start)
            attestation.version_id = employee._get_version(reference_end)

    @api.depends("date_from")
    def _compute_year(self):
        for attestation in self:
            attestation.year = attestation.date_from.year if attestation.date_from else False

    @api.depends("date_from", "date_to", "prev_work_days_per_week")
    def _compute_prev_assimilated_days(self):
        """
        Rough estimate used as an editable default, the user is expected to correct it from the actual certificate.
        """
        for attestation in self:
            if not attestation.date_to or not attestation.date_from:
                attestation.prev_assimilated_days = 0
                continue
            delta_days = (attestation.date_to - attestation.date_from).days + 1
            attestation.prev_assimilated_days = int(delta_days * attestation.prev_work_days_per_week / 7.0)

    @api.depends("prev_work_hours_per_week", "prev_reference_work_hours_per_week")
    def _compute_prev_work_time_rate(self):
        for attestation in self:
            if not attestation.prev_reference_work_hours_per_week:
                attestation.prev_work_time_rate = 0
                continue
            attestation.prev_work_time_rate = min(1, attestation.prev_work_hours_per_week / attestation.prev_reference_work_hours_per_week)

    @api.depends("version_id", "prev_work_hours_per_week", "prev_work_time_rate")
    def _compute_work_time_rate_change_ratio(self):
        """
        Ratio current/previous work time rate, used to scale leave days and pay amounts when the employee's schedule
        changed between employers.
        """
        for attestation in self:
            if not attestation.version_id or not attestation.prev_work_hours_per_week or not attestation.prev_work_time_rate:
                attestation.work_time_rate_change_ratio = 0
                continue
            current_work_time_rate = attestation.version_id.resource_calendar_id.work_time_rate

            attestation.work_time_rate_change_ratio = current_work_time_rate / attestation.prev_work_time_rate

    @api.depends(
        "prev_assimilated_days",
        "prev_work_days_per_week",
        "prev_work_time_rate",
        "version_id",
        "version_id.resource_calendar_id.hours_per_week",
        "version_id.reference_calendar_id.hours_per_week",
        "version_id.company_id.resource_calendar_id.hours_per_week",
        "year",
        "attest_type",
    )
    def _compute_limit_hours(self):
        """
        4 statutory weeks of the employee's current hours/week, prorated by how much of the year was actually
        worked (assimilated days) at the previous employer.
        """
        for attestation in self:
            if not attestation.version_id or not attestation.prev_work_days_per_week:
                attestation.limit_hours = 0
                continue
            current_hours_per_week = attestation.version_id._l10n_be_get_hours_per_week(attestation.year + 1)
            if attestation.attest_type == "worker":
                equivalent_days = round(
                    attestation.prev_assimilated_days * 5 * attestation.prev_work_time_rate
                    / attestation.prev_work_days_per_week,
                )
                attestation.limit_hours = (
                    bisect_right(ONVA_ASSIMILATED_DAY_THRESHOLDS, equivalent_days)
                    * current_hours_per_week / 5
                )
            else:
                attestation.limit_hours = (
                    attestation.prev_assimilated_days
                    * attestation._maximum_legal_vacation_weeks()
                    * current_hours_per_week
                ) / (attestation.prev_work_days_per_week * 52.0)

    @api.depends(
        "l10n_be_daily_wage",
        "prev_assimilated_days",
        "prev_simple_holiday_pay_paid",
        "work_time_rate_change_ratio",
        "attest_type",
        "version_id",
        "date_from",
    )
    def _compute_simple_holiday_pay_cap(self):
        """
        Compute the maximum simple holiday pay (SHP) amount recoverable from the previous employer's certificate.

        Schedule changes are prorated if the employee works more or less. When the employee now works less,
        the certificate amount is reduced. When the employee now works more, the theoretical ceiling is reduced.
        Worker certificates deduct the holiday-fund solidarity contribution. There is no recovery while the
        person is still a worker (the employer does not pay them during holidays).
        """
        for attestation in self:
            if not attestation.version_id or attestation.version_id.is_worker() or not attestation.work_time_rate_change_ratio:
                attestation.simple_holiday_pay_cap = 0
                continue
            ratio_working_less = min(1, attestation.work_time_rate_change_ratio)
            ratio_working_more = min(1, 1 / attestation.work_time_rate_change_ratio)

            theoretical_cap = attestation.l10n_be_daily_wage * attestation.prev_assimilated_days * 0.0767
            paid_amount = attestation.prev_simple_holiday_pay_paid
            if attestation.attest_type == "worker":
                paid_amount = attestation._apply_holiday_fund_solidarity_contribution(paid_amount)

            attestation.simple_holiday_pay_cap = min(
                # Prorate certificate amount if working less now
                paid_amount * ratio_working_less,
                # Prorate theoretical cap if working more now
                theoretical_cap * ratio_working_more,
            )

    @api.depends(
        "has_contract_wage",
        "prev_assimilated_days",
        "prev_double_holiday_pay_paid",
        "prev_work_days_per_week",
        "version_id",
        "work_time_rate_change_ratio",
        "attest_type",
        "date_from",
    )
    def _compute_double_holiday_pay_cap(self):
        for attestation in self:
            attestation.double_holiday_pay_cap = attestation._get_double_holiday_pay_cap()

    @api.depends("date_from", "date_to")
    def _compute_issues(self):
        for attestation in self:
            issues = {}
            if attestation.date_from > attestation.date_to:
                issues[0] = {
                    "message": self.env._("The start date must be before or equal to the end date."),
                    "level": "danger",
                }
            if attestation.date_from and attestation.date_to and attestation.date_from.year != attestation.date_to.year:
                issues[len(issues)] = {
                    "message": self.env._("The attestation's start date and end date must be in the same calendar year."),
                    "level": "danger",
                }
            attestation.issues = issues

    def _get_double_holiday_pay_cap(self, reference_date=None):
        """
        Compute the maximum double holiday pay (DHP) amount recoverable from the previous employer's certificate.

        The theoretical ceiling is 92% of gross monthly wage scaled by the fraction of year worked at the previous
        employer. This cap is prorated the same way as the simple holiday pay when the employee's schedule has changed.

        :param reference_date: An anchor for the variable-revenue look-back window. Defaults to the end of the holiday
            year (attestation year + 1) clamped to today to estimate a number for the form. The double holiday payslip
            passes its own period so the variable revenue is averaged over the months preceding the computation.
        :return: The recoverable DHP amount, rounded to the company currency's precision.
        """
        self.ensure_one()
        if not self.version_id or self.version_id.is_worker() or not self.work_time_rate_change_ratio or not self.prev_work_days_per_week:
            return 0

        if reference_date is None:
            reference_date = min(date.today(), date(self.year + 1, 12, 31))
        variable_revenue = self.employee_id._origin._l10n_be_get_last_year_average_variable_revenues(reference_date)

        dhp_cap_based_on_prev_assimilated_days = (
            0.92  # Double holiday pay rate
            * (self.version_id._l10n_be_get_monthly_wage(reference_date.year) + variable_revenue)
            * min(1, self.prev_assimilated_days / (52 * self.prev_work_days_per_week))
        )

        ratio_working_less = min(1, self.work_time_rate_change_ratio)
        ratio_working_more = min(1, 1 / self.work_time_rate_change_ratio)
        paid_amount = self.prev_double_holiday_pay_paid
        if self.attest_type == "worker":
            paid_amount = self._apply_holiday_fund_solidarity_contribution(paid_amount)
        # Round to currency precision so the recovered amount matches the per-certificate cap shown on the form and
        # summing several certificates does not accumulate sub-cent drift.
        return self.currency_id.round(
            min(
                # Prorate certificate amount if working less now
                paid_amount * ratio_working_less,
                # Prorate theoretical cap if working more now
                dhp_cap_based_on_prev_assimilated_days * ratio_working_more,
            ),
        )

    @api.depends(
        "leave_allocation_id.number_of_hours",
        "limit_hours",
        "prev_days_earned",
        "prev_work_days_per_week",
        "prev_work_hours_per_week",
        "prev_reference_work_hours_per_week",
        "version_id",
        "version_id.resource_calendar_id.hours_per_week",
        "version_id.reference_calendar_id.hours_per_week",
        "version_id.company_id.resource_calendar_id.hours_per_week",
        "year",
    )
    def _compute_hours_to_allocate(self):
        """
        Entitlement capped at the lower of the previous and current employer's absolute hours/week --
        not a percentage-of-reference comparison, a flat floor (an employee moving from
        20h/week to 40h/week keeps "4 weeks of 20 hours, or 10 full days", capped at the old, lower
        absolute rate; one moving from 38h/week to 17h/week gets "4 weeks of 17 hours", capped at the
        new, lower one).
        Days are derived from hours divided by the current employer's hours/day,
        so a change in days/week (e.g. 5 to 4) is naturally absorbed there.
        """
        for attestation in self:
            if attestation.leave_allocation_id:
                attestation.hours_to_allocate = attestation.leave_allocation_id.number_of_hours
                continue
            if not attestation.version_id or not attestation.prev_work_days_per_week:
                attestation.hours_to_allocate = 0
                continue
            prev_effective_hours_per_week = min(
                attestation.prev_work_hours_per_week,
                attestation.prev_reference_work_hours_per_week,
            )
            current_actual_hours_per_week = attestation.version_id._l10n_be_get_hours_per_week(attestation.year + 1)
            weeks_equivalent = attestation.prev_days_earned / attestation.prev_work_days_per_week
            attestation.hours_to_allocate = min(
                attestation.limit_hours,
                weeks_equivalent * min(prev_effective_hours_per_week, current_actual_hours_per_week),
            )

    @api.depends("hours_to_allocate", "leave_allocation_id.number_of_days", "version_id")
    def _compute_days_to_allocate(self):
        """
        Day count actually used to size the leave allocation, derived from hours_to_allocate (see there),
        rounded down to the nearest half-day like the allocation wizard.
        Once a leave allocation is linked it becomes
        the source of truth, as schedule change wizards keep it in sync directly.
        """
        for attestation in self:
            if attestation.leave_allocation_id:
                attestation.days_to_allocate = attestation.leave_allocation_id.number_of_days
                continue
            if not attestation.version_id:
                attestation.days_to_allocate = 0
                continue
            hours_per_day = attestation.version_id.resource_calendar_id.hours_per_day
            if not hours_per_day:
                attestation.days_to_allocate = 0
                continue
            attestation.days_to_allocate = float_round(
                attestation.hours_to_allocate / hours_per_day,
                precision_rounding=0.5,
                rounding_method="DOWN",
            )

    @api.depends("attest_type", "days_to_allocate", "hours_to_allocate", "prev_days_earned", "version_id", "year")
    def _compute_allocation_conversion_message(self):
        for attestation in self:
            if not attestation.version_id or float_compare(attestation.days_to_allocate, attestation.prev_days_earned, precision_digits=2) == 0:
                attestation.allocation_conversion_message = False
                continue
            attestation.allocation_conversion_message = self.env._(
                "%(entered_days).2f remaining day(s) give %(allocated_days).2f paid day(s) "
                "(%(allocated_hours).2f hours) on the current %(hours_per_week)g-hour, %(days_per_week)g-day workweek, after applying %(limit)s.",
                entered_days=attestation.prev_days_earned,
                allocated_hours=attestation.hours_to_allocate,
                allocated_days=attestation.days_to_allocate,
                hours_per_week=attestation.version_id._l10n_be_get_hours_per_week(attestation.year + 1),
                days_per_week=attestation.version_id._l10n_be_get_days_per_week(),
                limit=self.env._("ONVA limits") if attestation.attest_type == "worker" else self.env._("the employee legal entitlement cap"),
            )

    @api.depends("employee_id", "year")
    def _compute_linkable_allocation_ids(self):
        # version_id can still be empty here (e.g. a new, unsaved employee): version_id.is_worker()
        # would crash on that empty recordset via _get_work_entry_type_for_allocation below.
        valid_attestations = self.filtered(lambda a: a.employee_id and a.year and a.version_id)
        (self - valid_attestations).linkable_allocation_ids = False
        if not valid_attestations:
            return

        employees = valid_attestations.employee_id
        holiday_years = valid_attestations.mapped("year")  # holiday year = year + 1

        work_entry_type_by_employee_type = {
            employee_type: self._get_work_entry_type_for_allocation(employee_type)
            for employee_type in {a.version_id for a in valid_attestations}
        }
        all_work_entry_types = self.env["hr.work.entry.type"].union(*work_entry_type_by_employee_type.values())

        allocations = self.env["hr.leave.allocation"].search([
            ("employee_id", "in", employees.ids),
            ("date_from", ">=", date(min(holiday_years) + 1, 1, 1)),
            ("date_from", "<=", date(max(holiday_years) + 1, 12, 31)),
            ("work_entry_type_id", "in", all_work_entry_types.ids),
            ("state", "!=", "refuse"),
            ("employee_company_id", "in", self.company_id.ids),
        ])

        allocations_by_employee = defaultdict(lambda: self.env["hr.leave.allocation"])
        for allocation in allocations:
            allocations_by_employee[allocation.employee_id.id] |= allocation

        for attestation in valid_attestations:
            holiday_year = attestation.year + 1
            legal_leave_work_entry_type = work_entry_type_by_employee_type[attestation.version_id]
            already_linked_allocations = attestation.employee_id.l10n_be_holiday_attest_ids.leave_allocation_id
            allocation_candidates = allocations_by_employee[attestation.employee_id._origin.id].filtered(
                lambda a: (
                    a.work_entry_type_id == legal_leave_work_entry_type
                    and a.employee_company_id == attestation.company_id
                    and date(holiday_year, 1, 1) <= a.date_from <= date(holiday_year, 12, 31)
                ),
            )
            attestation.linkable_allocation_ids = allocation_candidates - already_linked_allocations

    @api.depends("allocation_to_link_id", "days_to_allocate")
    def _compute_allocation_warning(self):
        for attestation in self:
            if (not attestation.allocation_to_link_id) or attestation.allocation_to_link_id.leaves_taken <= attestation.days_to_allocate:
                attestation.allocation_warning_message = ""

            else:
                attestation.allocation_warning_message = self.env._(
                    "The employee has already taken %(existing_days)s day(s) of leave while the attestation will only provide %(attestation_days)s day(s) of leave.",
                    existing_days=attestation.allocation_to_link_id.leaves_taken,
                    attestation_days=attestation.days_to_allocate,
                )

    @api.depends("employee_id", "simple_holiday_pay_cap", "year")
    def _compute_simple_holiday_pay_amount_recovered(self):
        """
        Display-only tracker for how much of simple_holiday_pay_cap has been already been recovered through payslips.
        When an employee has multiple attestations for the same year, recovery is attributed in date order so each cap
        is drawn down before the next.
        """
        relevant_structures = [
            self.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary").id,
            self.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees").id,
        ]
        payslips = self.env["hr.payslip"].search([
            ("employee_id", "in", self.employee_id.ids),
            ("struct_id", "in", relevant_structures),
            ("company_id", "in", self.company_id.ids),
            ("state", "in", ["validated", "paid"]),
        ])
        line_values = payslips._get_line_values(["HolPayRec", "HolPayReg"])
        payslips_by_employee = defaultdict(lambda: self.env["hr.payslip"])
        for payslip in payslips:
            payslips_by_employee[payslip.employee_id] |= payslip

        for attestation in self:
            employee_payslips = payslips_by_employee[attestation.employee_id].filtered(
                lambda p: p.date_from.year == attestation.year + 1 and p.company_id == attestation.company_id,
            )
            prior_employee_attestations = attestation.employee_id.l10n_be_holiday_attest_ids.filtered(
                lambda a: a.year == attestation.year and (a.date_from, a.date_to) < (attestation.date_from, attestation.date_to),
            )
            sum_prior_simple_holiday_pay_cap = sum(prior_employee_attestations.mapped("simple_holiday_pay_cap"))

            line_values = employee_payslips._get_line_values(["HolPayRec", "HolPayReg"], compute_sum=True)
            sum_payslip_shp_recovery = line_values["HolPayRec"]["sum"]["total"]
            sum_payslip_shp_regularization = line_values["HolPayReg"]["sum"]["total"]
            total_recovered = sum_payslip_shp_regularization - sum_payslip_shp_recovery

            attestation.simple_holiday_pay_amount_recovered = max(
                0,
                min(
                    total_recovered - sum_prior_simple_holiday_pay_cap,
                    attestation.simple_holiday_pay_cap,
                ),
            )

    @api.depends("employee_id", "double_holiday_pay_cap", "year")
    def _compute_double_holiday_pay_amount_recovered(self):
        """
        Display-only tracker for how much of double holiday pay cap has been already been recovered through payslips.
        When an employee has multiple attestations for the same year, recovery is attributed in date order so each cap
        is drawn down before the next.
        """
        relevant_structures = [
            self.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday").id,
        ]
        payslips = self.env["hr.payslip"].search([
            ("employee_id", "in", self.employee_id.ids),
            ("struct_id", "in", relevant_structures),
            ("company_id", "in", self.company_id.ids),
            ("state", "in", ["validated", "paid"]),
        ])

        line_values = payslips._get_line_values(["DOUBLERECOVERY"])

        payslips_by_employee = defaultdict(lambda: self.env["hr.payslip"])
        for payslip in payslips:
            payslips_by_employee[payslip.employee_id] |= payslip

        for attestation in self:
            holiday_year = attestation.year + 1
            employee_payslips = payslips_by_employee[attestation.employee_id].filtered(
                lambda p: p.date_from.year == holiday_year and p.company_id == attestation.company_id,
            )
            prior_employee_attestations = attestation.employee_id.l10n_be_holiday_attest_ids.filtered(
                lambda a: a.year == attestation.year and (a.date_from, a.date_to) < (attestation.date_from, attestation.date_to),
            )
            sum_prior_double_holiday_cap = sum(prior_employee_attestations.mapped("double_holiday_pay_cap"))
            line_values = employee_payslips._get_line_values(["DOUBLERECOVERY"], compute_sum=True)
            total_recovered = line_values["DOUBLERECOVERY"]["sum"]["total"]

            attestation.double_holiday_pay_amount_recovered = max(
                0,
                min(
                    total_recovered - sum_prior_double_holiday_cap,
                    attestation.double_holiday_pay_cap,
                ),
            )

    @api.depends("prev_simple_holiday_pay_paid", "prev_double_holiday_pay_paid")
    def _compute_prev_total_holiday_pay_paid(self):
        for attestation in self:
            attestation.prev_total_holiday_pay_paid = attestation.prev_simple_holiday_pay_paid + attestation.prev_double_holiday_pay_paid

    @api.onchange("prev_total_holiday_pay_paid")
    def _inverse_prev_total_holiday_pay_paid(self):
        for attestation in self.filtered(lambda attest: attest.attest_type == "worker"):
            total = attestation.prev_total_holiday_pay_paid
            half = attestation.currency_id.round(total / 2)
            attestation.prev_simple_holiday_pay_paid = half
            attestation.prev_double_holiday_pay_paid = total - half

    @api.depends(
        "version_id",
        "version_id.resource_calendar_id.calendar_type",
        "version_id.reference_calendar_id",
    )
    def _compute_attestation_warning(self):
        for attestation in self:
            if not attestation.version_id:
                attestation.attestation_warning_message = self.env._(
                    "Please save the employee record before adding a holiday attestation.",
                )
            elif attestation.version_id.sudo()._is_flexible() and not attestation.version_id.reference_calendar_id:
                attestation.attestation_warning_message = self.env._(
                    "The employee's contract has no working schedule configured. Please set a working schedule on the contract before adding an attestation.",
                )
            else:
                attestation.attestation_warning_message = ""

    @api.depends("version_id.wage", "version_id.hourly_wage", "version_id.wage_type")
    def _compute_has_contract_wage(self):
        for attestation in self:
            attestation.has_contract_wage = bool(attestation.version_id._get_contract_wage())

    @api.depends("version_id", "version_id.l10n_be_worker_code_id")
    def _compute_is_worker(self):
        for attestation in self:
            attestation.is_worker = bool(attestation.version_id and attestation.version_id.is_worker())

    # ----------
    # Constrains
    # ----------

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for attestation in self:
            if attestation.date_from > attestation.date_to:
                raise ValidationError(self.env._("The start date must be before or equal to the end date."))

            if attestation.date_from.year != attestation.date_to.year:
                raise ValidationError(self.env._("The attestation's start date and end date must be in the same calendar year."))

    # ---------
    # Overrides
    # ---------

    @api.model_create_multi
    def create(self, vals_list):
        attestations = super().create(vals_list)
        attestations_with_warning = attestations.filtered(lambda a: a.attestation_warning_message)
        if attestations_with_warning:
            raise UserError("\n".join(attestations_with_warning.mapped("attestation_warning_message")))

        seen_allocations = set()
        for attestation in attestations:
            if attestation.days_to_allocate > 0:
                if attestation.allocation_to_link_id and attestation.allocation_to_link_id.id not in seen_allocations:
                    attestation.allocation_to_link_id.number_of_days = attestation.days_to_allocate
                    # Explicit, since a tracked type's existing number_of_hours otherwise stays
                    # stale instead of following the resize (see _compute_number_of_hours override).
                    attestation.allocation_to_link_id.number_of_hours = attestation.hours_to_allocate
                    attestation.leave_allocation_id = attestation.allocation_to_link_id
                    seen_allocations.add(attestation.allocation_to_link_id.id)
                elif not attestation.leave_allocation_id:
                    attestation.action_create_allocation()

        return attestations

    # -------
    # Actions
    # -------
    def _get_work_entry_type_for_allocation(self, version):
        if version.is_worker():
            xmlid = "hr_work_entry.l10n_be_work_entry_type_worker_time_off"
        else:
            xmlid = "hr_work_entry.be_work_entry_type_legal_leave"
        work_entry_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not work_entry_type:
            raise UserError(self.env._("There is no time type linked to the Paid Time Off type."))
        return work_entry_type

    def action_create_allocation(self):
        """
        Create a legal leave allocation for the holiday year associated with this attestation.

        :raises UserError: if the legal leave time type cannot be found.
        :return: the newly created hr.leave.allocation record.
        """
        self.ensure_one()
        if self.leave_allocation_id:
            raise UserError(self.env._("An allocation already exists for this holiday attestation."))

        legal_leave_work_entry_type = self._get_work_entry_type_for_allocation(self.version_id)
        leave_allocation_year = self.year + 1

        leave_allocation = self.env["hr.leave.allocation"].create({
            "name": f"{legal_leave_work_entry_type.name} {leave_allocation_year}",
            "employee_id": self.employee_id.id,
            "work_entry_type_id": legal_leave_work_entry_type.id,
            "number_of_days": self.days_to_allocate,
            # For the 3 BE hours-tracked types this sticks instead of being re-derived from
            # number_of_days (see HrLeaveAllocation._compute_number_of_hours), so the allocation
            # keeps the true hours-first entitlement instead of losing it to day rounding.
            "number_of_hours": self.hours_to_allocate,
            "date_from": date(leave_allocation_year, 1, 1),
            "date_to": date(leave_allocation_year, 12, 31),
            "state": "confirm",
        })

        self.leave_allocation_id = leave_allocation.id

        return leave_allocation

    def action_open_allocation(self):
        """
        Opens the linked leave allocation.
        """
        self.ensure_one()

        if not self.leave_allocation_id:
            raise UserError(self.env._("There is no leave allocation linked to this holiday attestation."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.leave.allocation",
            "res_id": self.leave_allocation_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_shp_recovery_payslips(self):
        """
        Open a list view of all payslips for this employee in the holiday year that contain a non-zero simple holiday
        pay recovery.
        """
        self.ensure_one()

        holiday_year = self.year + 1
        payslips = self.env["hr.payslip"].search([
            ("employee_id", "=", self.employee_id.id),
            ("date_from", ">=", date(holiday_year, 1, 1)),
            ("date_to", "<=", date(holiday_year, 12, 31)),
            ("state", "in", ["validated", "paid"]),
        ])

        # keep only payslips with SHP recovery
        line_values = payslips._get_line_values(["HolPayRec"])

        payslip_ids = payslips.filtered(lambda p: line_values["HolPayRec"][p.id]["total"]).ids

        return {
            "name": self.env._("Simple Holiday Recoveries"),
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "target": "new",
            "domain": [("id", "in", payslip_ids)],
        }

    def action_open_dhp_recovery_payslips(self):
        """
        Open a list view of all double holiday pay payslips for this employee in the holiday year that contain
        a non-zero DOUBLERECOVERY line.
        """
        self.ensure_one()

        holiday_year = self.year + 1
        structure = self.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday")

        payslips = self.env["hr.payslip"].search([
            ("employee_id", "=", self.employee_id.id),
            ("struct_id", "=", structure.id),
            ("date_from", ">=", date(holiday_year, 1, 1)),
            ("date_to", "<=", date(holiday_year, 12, 31)),
            ("state", "in", ["validated", "paid"]),
        ])

        line_values = payslips._get_line_values(["DOUBLERECOVERY"])

        payslip_ids = payslips.filtered(lambda p: line_values["DOUBLERECOVERY"][p.id]["total"]).ids

        return {
            "name": self.env._("Double Holiday Recoveries"),
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            "view_mode": "list,form",
            "target": "new",
            "domain": [("id", "in", payslip_ids)],
        }

    # ---------------------
    # Other Business method
    # ---------------------

    def _get_number_of_months(self):
        self.ensure_one()
        if self.date_from.month == self.date_to.month:
            days_in_month = (self.date_from + relativedelta(day=31)).day
            return (self.date_to.day - self.date_from.day + 1) / days_in_month

        whole_months = self.date_to.month - self.date_from.month - 1

        days_in_start_month = (self.date_from + relativedelta(day=31)).day
        start_month_fraction = (days_in_start_month - self.date_from.day + 1) / days_in_start_month

        days_in_end_month = (self.date_to + relativedelta(day=31)).day
        end_month_fraction = self.date_to.day / days_in_end_month

        return whole_months + start_month_fraction + end_month_fraction

    def _maximum_legal_vacation_weeks(self):
        """
        Returns the maximum number of statutory vacation weeks an employee is entitled to under Belgian law (CP200).
        """
        return 4.0

    def _apply_holiday_fund_solidarity_contribution(self, amount):
        """Deduct the holiday-fund solidarity contribution from worker certificate amounts."""
        self.ensure_one()
        if self.attest_type != "worker":
            return amount
        reference_date = date(self.year + 1, 1, 1) if self.year else fields.Date.context_today(self)
        rate = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "l10n_be_holiday_fund_solidarity_rate",
            date=reference_date,
        )
        return amount * (1 - rate)
