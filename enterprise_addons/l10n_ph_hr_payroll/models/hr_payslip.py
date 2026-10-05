# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # All of these fields are precomputed, but manually editable, to keep full control over the payslip.
    l10n_ph_hr_payroll_is_final_slip = fields.Boolean(
        string="Is Final Slip",
        compute='_compute_l10n_ph_hr_payroll_is_final_pay',
        store=True,
        readonly=False,
    )
    l10n_ph_hr_payroll_includes_13th_month = fields.Boolean(
        string="Includes 13th month",
        compute='_compute_l10n_ph_hr_payroll_includes_13th_month',
        store=True,
        readonly=False,
    )
    l10n_ph_hr_payroll_includes_tax_annualization = fields.Boolean(
        string="Includes Tax Annualization",
        compute='_compute_l10n_ph_hr_payroll_includes_tax_annualization',
        store=True,
        readonly=False,
    )
    l10n_ph_hr_payroll_includes_separation_pay = fields.Boolean(
        string="Includes Separation Pay",
        compute='_compute_l10n_ph_hr_payroll_includes_separation_pay',
        store=True,
        readonly=False,
    )
    l10n_ph_hr_payroll_includes_retirement_pay = fields.Boolean(
        string="Includes Retirement Pay",
        compute='_compute_l10n_ph_hr_payroll_includes_retirement_pay',
        store=True,
        readonly=False,
    )

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_ph_hr_payroll', [
                'data/hr_rule_parameters_data.xml',
                'data/hr_salary_rule_category_data.xml',
                'data/hr_salary_rule_data.xml',
                'data/hr_salary_rule_de_minimis_data.xml',
            ])]

    @api.depends('date_from', 'date_to', 'version_id', 'country_code')
    def _compute_l10n_ph_hr_payroll_is_final_pay(self):
        """
        Check if this payslip is the employee's final pay.

        This is True if the employee's departure date falls within the payslip's date range.
        """
        for slip in self:
            if slip.country_code != 'PH':
                slip.l10n_ph_hr_payroll_is_final_slip = False
            else:
                is_final_payslip = slip.version_id.departure_date and (slip.date_from <= slip.version_id.departure_date <= slip.date_to)
                slip.l10n_ph_hr_payroll_is_final_slip = is_final_payslip

    @api.depends('date_to', 'country_code', 'l10n_ph_hr_payroll_is_final_slip')
    def _compute_l10n_ph_hr_payroll_includes_13th_month(self):
        """
        Check if the 13th-month pay should be included in this payslip.

        We usually include it in two cases:
        1. It's the final payslip for a leaving employee.
        2. It's the late-December payroll run (after Dec 20th).
        """
        for slip in self:
            if slip.country_code != 'PH':
                slip.l10n_ph_hr_payroll_includes_13th_month = False
            else:
                if slip.l10n_ph_hr_payroll_is_final_slip:
                    included = True  # We always want to provide the accumulated 13th month in the final payslip.
                else:
                    included = slip.date_to.month == 12 and slip.date_to.day > 20
                slip.l10n_ph_hr_payroll_includes_13th_month = included

    @api.depends('date_to', 'country_code', 'l10n_ph_hr_payroll_is_final_slip')
    def _compute_l10n_ph_hr_payroll_includes_tax_annualization(self):
        """
        Check if the tax annualization should be included in this payslip.

        We usually include it in two cases:
        1. It's the final payslip for a leaving employee.
        2. It's the late-December payroll run (after Dec 20th).
        """
        for slip in self:
            if slip.country_code != 'PH':
                slip.l10n_ph_hr_payroll_includes_tax_annualization = False
            else:
                if slip.l10n_ph_hr_payroll_is_final_slip:
                    included = True  # Always done right when the employee is leaving the company.
                else:
                    included = slip.date_to.month == 12 and slip.date_to.day > 20
                slip.l10n_ph_hr_payroll_includes_tax_annualization = included

    @api.depends('country_code', 'version_id', 'l10n_ph_hr_payroll_is_final_slip')
    def _compute_l10n_ph_hr_payroll_includes_separation_pay(self):
        """
        Check if this payslip should include separation (severance) pay.

        We include it if this is the final payslip and the departure reason qualifies
        for severance (like redundancy or retrenchment).
        """
        for slip in self:
            if slip.country_code != 'PH':
                slip.l10n_ph_hr_payroll_includes_separation_pay = False
            else:
                departure_reason = slip.version_id.departure_reason_id
                if slip.l10n_ph_hr_payroll_is_final_slip and departure_reason:
                    slip.l10n_ph_hr_payroll_includes_separation_pay = departure_reason.l10n_ph_hr_payroll_terminal_pay_type in ('severance_full', 'severance_half')
                else:
                    slip.l10n_ph_hr_payroll_includes_separation_pay = False

    @api.depends('country_code', 'version_id', 'l10n_ph_hr_payroll_is_final_slip')
    def _compute_l10n_ph_hr_payroll_includes_retirement_pay(self):
        """
        Check if this payslip should include retirement pay.

        We include it if this is the final payslip and the departure reason qualifies
        for retirement.
        """
        for slip in self:
            if slip.country_code != 'PH':
                slip.l10n_ph_hr_payroll_includes_retirement_pay = False
            else:
                departure_reason = slip.version_id.departure_reason_id
                if slip.l10n_ph_hr_payroll_is_final_slip:
                    slip.l10n_ph_hr_payroll_includes_retirement_pay = departure_reason.l10n_ph_hr_payroll_terminal_pay_type == 'retirement'
                else:
                    slip.l10n_ph_hr_payroll_includes_retirement_pay = False

    def _get_localdict(self, work_entries=None):
        """
        Add Philippines-specific variables into the salary rule evaluation context (localdict).

        We inject these variables so the salary rules can access them easily:
        - YTD benefits (to track the ₱90k tax-free limit).
        - Used De Minimis amounts (to check against daily/monthly/annual limits).
        - Unused leave balances (for monetization on final pay).
        - YTD Gross and Withheld Tax (for year-end tax annualization).
        """
        res = super()._get_localdict(work_entries)
        if self.country_code == 'PH':
            last_ytd_payslip = self._get_last_ytd_payslips().get(self, self.env['hr.payslip'])
            line_values = last_ytd_payslip._get_line_values(set(self.struct_id.rule_ids.mapped('code')), ['ytd'])

            ytd_ob = line_values.get('OB', {}).get(last_ytd_payslip.id, {}).get('ytd', 0.0)
            res.update({
                "ytd_other_benefits": ytd_ob,
                "unused_leaves": 0.0,
                "de_minimis_used_amount": self._l10n_ph_hr_payroll_prepare_de_minimis_used_amount_information(),
            })

            # For employees joining in the middle of the year, we need to take into account their previous employment
            # benefits for the 90 000 tax-free cap. We only pick this if this is the joining year.
            if prev_employment := self.employee_id._l10n_ph_get_previous_employment(self.date_to):
                res['ytd_other_benefits'] += prev_employment.nontax_13th_month

            if self.l10n_ph_hr_payroll_is_final_slip:
                allocations = self.env["hr.leave.allocation"].search([
                    ("state", "=", "validate"),
                    ("work_entry_type_id.amount_rate", "!=", 0),
                    ("employee_id", "=", self.employee_id.id),
                    ("date_from", "<=", self.version_id.date_end or self.date_to),
                ])
                res['unused_leaves'] = sum(a.number_of_days - a.leaves_taken for a in allocations)
            if self.l10n_ph_hr_payroll_includes_tax_annualization:
                # We need to know the ytd taxable wages to recalculate the tax on an annual basis.
                res.update({
                    'ytd_gross': line_values.get("GROSS", {}).get(last_ytd_payslip.id, {}).get("ytd", 0.0),
                    'ytd_wthh_tax': line_values.get("WITHH_TAX", {}).get(last_ytd_payslip.id, {}).get("ytd", 0.0),
                })
        return res

    def _l10n_ph_hr_payroll_prepare_de_minimis_used_amount_information(self):
        """
        Calculate how much of each De Minimis benefit the employee has already used.

        BIR De Minimis limits reset on different schedules (like monthly for rice,
        annually for clothing). This method figures out how much they've already
        received during the current active period so we don't over-grant tax-free limits.
        """
        self.ensure_one()
        caps = self._rule_parameter('l10n_ph_hr_payroll_de_minimis_cap', raise_if_not_found=False)
        if not caps:  # in case the cap was removed, return an empty defaultdict which will act as 'no caps'
            return defaultdict(float)

        # We won't need anything earlier than the current year.
        previous_payslips = self.env['hr.payslip'].search([
            ('company_id', '=', self.company_id.id),
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_to', '<', self.date_from),
            ('date_from', '>=', self.date_from.replace(month=1, day=1)),
            ('id', '!=', self.id),
        ])
        results = defaultdict(float)
        for rule_code, cap_details in caps.items():
            from_date = self._l10n_ph_hr_payroll_get_payslip_schedule_start_for_benefits(cap_details['schedule'])
            if not from_date:  # e.g. Daily schedule
                continue

            filtered_payslips = previous_payslips.filtered(lambda p: p.date_from >= from_date)
            if rule_code != 'DM_LEAVE_MONETIZATION':
                amount = filtered_payslips._get_line_values([rule_code], compute_sum=True)[rule_code]['sum']['total']
                results[rule_code] += amount
            else:
                # Special case: Leave monetization caps are based on days, not monetary value.
                amount = sum(payslip._get_input_line_amount('DM_LEAVE_MONETIZATION') for payslip in filtered_payslips)
                results[rule_code] += amount
        return results

    def _l10n_ph_hr_payroll_get_payslip_schedule_start_for_benefits(self, benefit_schedule):
        """
        Get the start date of the current period for a specific benefit schedule.

        This helps us figure out the cut-off date when summing up past De Minimis benefits
        (e.g., getting the first day of the current month, half-year, or year).

        Note: Daily limits aren't handled here because daily allowances (like meal caps)
        are calculated directly on the payslip based on days worked.
        """
        self.ensure_one()
        match benefit_schedule:
            case 'monthly':
                return self.date_from.replace(day=1)
            case 'semi-annually':
                if self.date_from.month <= 6:
                    return self.date_from.replace(month=1, day=1)
                else:
                    return self.date_from.replace(month=7, day=1)
            case 'annually':
                return self.date_from.replace(month=1, day=1)
            case _:
                return None

    def _l10n_ph_hr_payroll_get_worked_day_rates(self, version, code):
        """
        Calculate the premium rates for a worked day based on its tags.

        In the Philippines, payroll premiums compound. For example, Night Shift applies
        on top of Overtime, which applies on top of Holiday or Rest Day pay.

        This method parses a work entry code (like 'WORK100_RH_NS_OVERTIME'), figures out
        the total multipliers, and splits the extra pay into separate Holiday, Overtime,
        and Night Shift buckets so our tax reporting is accurate.
        """
        self.ensure_one()
        work_entry_code_rate = self._rule_parameter("l10n_ph_hr_payroll_worked_day_rates", raise_if_not_found=False)
        if not work_entry_code_rate:  # This would lead to a non-compliancy with the law, but this avoids a traceback in such case.
            return {
                "l10n_ph_hr_payroll_holiday_rate": 0.0,
                "l10n_ph_hr_payroll_overtime_rate": 0.0,
                "l10n_ph_hr_payroll_night_shift_rate": 0.0,
            }

        # Statutory rates differ based on employee rank (e.g., managers are typically exempt from OT/NSD).
        version_employee_level = version.l10n_ph_hr_payroll_employee_rank or "rank_and_file"

        # Split the string to evaluate the compound conditions (e.g., ['WORK100', 'RH', 'NS', 'OVERTIME'])
        tags = code.split("_")

        day_factor = 1.0
        is_holiday = False

        # DOLE dictates a flat 150% rate for Special Non-Working Holidays on a Rest Day,
        # overriding the standard mathematical compounding (130% * 130% = 169%).
        if "SNW" in tags and "REST" in tags:
            day_factor = work_entry_code_rate["HOLIDAY_RATES"]["SNW_REST"][version_employee_level]
            is_holiday = True
        else:
            for hol in ["SNW", "RH", "DH"]:
                if hol in tags:
                    day_factor = work_entry_code_rate["HOLIDAY_RATES"][hol][version_employee_level]
                    is_holiday = True

            if "LEAVE" in tags and is_holiday:
                # If unworked, strip the statutory "services rendered" premium (+100%).
                # max() ensures unworked special non-working holidays safely evaluate to 1.0 instead of 0.3.
                day_factor = max(1.0, day_factor - 1.0)

            if "REST" in tags:
                # Regular Holidays (200%) falling on a Rest Day (130%) legally compound to 260%.
                day_factor *= work_entry_code_rate["BASE_RATES"]["REST"][version_employee_level]

        # Overtime premiums scale based on the base shift: 25% for ordinary days, 30% for premium days.
        ot_factor = 1.0
        if "OVERTIME" in tags or "040.00" in tags:
            if is_holiday or "REST" in tags:
                ot_factor = work_entry_code_rate["PREMIUM_RATES"]["OT_HOL"][version_employee_level]
            else:
                ot_factor = work_entry_code_rate["PREMIUM_RATES"]["OT_REG"][version_employee_level]

        # Night Shift Differential is a flat statutory 10%, but it compounds on top of everything else.
        ns_factor = 1.0
        if "NS" in tags:
            ns_factor = work_entry_code_rate["PREMIUM_RATES"]["NS"][version_employee_level]

        # Isolate the premiums from the base 1.0 multiplier.
        # Overtime isolates against the escalated Holiday day_factor.
        # Night Shift isolates against the combined Holiday + Overtime factors.
        current_hour_base = day_factor * ot_factor
        return {
            "l10n_ph_hr_payroll_holiday_rate": max(0.0, day_factor - 1.0),
            "l10n_ph_hr_payroll_overtime_rate": max(0.0, day_factor * (ot_factor - 1.0)),
            "l10n_ph_hr_payroll_night_shift_rate": max(0.0, current_hour_base * (ns_factor - 1.0)),
        }

    def _get_worked_day_lines_values(self, version, work_entries_vals):
        """
        Format the aggregated work entry hours into Payslip Worked Day Lines.

        Our engine dynamically replaces standard scheduled work entries with the
        correct statutory ones (e.g., swapping a normal attendance for a 'Rest Day
        Attendance') using the `_l10n_ph_hr_payroll_get_work_hours` method.

        This method takes those dynamically swapped work entry types and formats
        them into the final payslip lines. It also safely handles floating-point
        rounding by pushing any decimal offsets into the largest work entry to
        ensure the total days match perfectly.
        """
        self.ensure_one()
        if self.struct_id.country_id.code != "PH":
            return super()._get_worked_day_lines_values(version, work_entries_vals)

        res = []
        hours_per_day = self._get_worked_day_lines_hours_per_day(version)

        # This returns the dynamically replaced work entry types and codes
        work_hours = version._l10n_ph_hr_payroll_get_work_hours(self.date_from, self.date_to, work_entries_vals)

        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
        add_days_rounding = 0

        for (work_entry_type, code), hours in work_hours_ordered:
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            if (work_entry_type, code) == biggest_work:
                days += add_days_rounding
            day_rounded = self._round_days(work_entry_type, days)
            add_days_rounding += days - day_rounded

            res.append({
                "version_id": version.id,
                "sequence": work_entry_type.sequence,
                "work_entry_type_id": work_entry_type.id,
                "number_of_days": day_rounded,
                "number_of_hours": hours,
                # Inject the segregated statutory multipliers directly into the line
                **self._l10n_ph_hr_payroll_get_worked_day_rates(version, code),
            })

        return sorted(res, key=lambda d: d["sequence"])

    def _l10n_ph_hr_payroll_get_property_inputs_value(self, codes):
        """
        Fetch the input line amounts of specific salary rules for the current payslip.
        """
        self.ensure_one()
        rules = self.env['hr.salary.rule'].search([('code', 'in', codes), ('struct_ids', 'in', self.struct_id.id)])

        inputs_values = defaultdict(float)
        for rule in rules:
            inputs_values[rule.code] = self._get_input_line_amount(rule.code)
        return inputs_values

    def _l10n_ph_hr_payroll_aggregate_totals(self, line_values=None):
        """
        Sum up salary rules and their categories across a batch of payslips.

        This prepares the raw payroll data for BIR tax reporting (like Form 1601-C).
        We specifically separate amounts between Minimum Wage Earners (MWE) and
        regular earners (NMWE) because the BIR requires them to be reported in
        completely different tax buckets.
        """
        rules_totals = defaultdict(float)
        categories_totals = defaultdict(lambda: defaultdict(float))

        if not line_values:
            line_values = self._get_line_values(set(self.line_ids.mapped("code")), compute_sum=True)

        category_mapping = self.struct_id._l10n_ph_hr_payroll_get_rules_per_categories()

        # BIR Reporting requirement: Total taxable salary for non-MWE employees whose withheld tax is 0.
        tax_rules = category_mapping.get("TAX", {})
        gross_rules = category_mapping.get("GROSS", {})

        is_mwe = {p.id: p.version_id.l10n_ph_hr_payroll_minimum_wage_earner for p in self}
        for payslip in self:
            tax_total = sum(
                line_values.get(rule_code, {}).get(payslip.id, {}).get("total", 0.0)
                for rule_code in tax_rules
            )

            if not tax_total and not is_mwe[payslip.id]:
                categories_totals["TAXABLE_EXEMPT"]["total"] += sum(
                    line_values.get(rule_code, {}).get(payslip.id, {}).get("total", 0.0)
                    for rule_code in gross_rules
                )

        # Aggregate amounts per category, split by MWE and non-MWE
        for category_code, rule_codes in category_mapping.items():
            for rule_code in rule_codes:
                for payslip in self:
                    total = line_values.get(rule_code, {}).get(payslip.id, {}).get("total", 0.0)
                    if not total:
                        continue

                    categories_totals[category_code]["mwe" if is_mwe[payslip.id] else "nmwe"] += total
                    categories_totals[category_code]["total"] += total

        # Keep rules_totals as a defaultdict defaulting to 0.0 for ease of writing rules.
        rules_totals.update({code: val["sum"]["total"] for code, val in line_values.items()})
        return rules_totals, categories_totals
