# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, WEEKLY

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import single_email_re

auto_mobile_re = re.compile(r"^\+\d{1,3}-\d{1,29}$")


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_hk_surname = fields.Char(
        string="Surname",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_given_name = fields.Char(
        string="Given Name",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_name_in_chinese = fields.Char(
        string="Name in Chinese",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_passport_place_of_issue = fields.Char(
        string="Place of Issue",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_spouse_identification_id = fields.Char(
        string="Spouse Identification No",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_spouse_passport_id = fields.Char(
        string="Spouse Passport No",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_spouse_passport_place_of_issue = fields.Char(
        string="Spouse Place of Issue",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_rentals_count = fields.Integer(
        compute='_compute_l10n_hk_rentals_count',
        groups="hr.group_hr_user",
    )

    l10n_hk_mpf_exempt = fields.Boolean(
        related='version_id.l10n_hk_mpf_exempt',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_registration_status = fields.Selection(
        related='version_id.l10n_hk_mpf_registration_status',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_contribution_start = fields.Selection(
        related="version_id.l10n_hk_mpf_contribution_start",
        groups="hr_payroll.group_hr_payroll_user",
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_scheme_id = fields.Many2one(
        related='version_id.l10n_hk_mpf_scheme_id',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('employer_account_number', '!=', False)]",
        inherited=True,
        readonly=False,
    )
    l10n_hk_payroll_group_id = fields.Many2one(
        related='version_id.l10n_hk_payroll_group_id',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        inherited=True,
        readonly=False,
    )
    l10n_hk_member_class_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_id',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_account_number = fields.Char(
        related='version_id.l10n_hk_mpf_account_number',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_staff_number = fields.Char(
        related='version_id.l10n_hk_staff_number',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_scheme_join_date = fields.Date(
        related='version_id.l10n_hk_mpf_scheme_join_date',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_scheme_group_count = fields.Integer(
        related='version_id.l10n_hk_scheme_group_count',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
    l10n_hk_previous_employment_date = fields.Date(
        string="Previous Date Of Employment",
        help="Fill this information in case of intra_group transfer.",
        groups='hr.group_hr_user',
        tracking=True,
    )
    l10n_hk_visa_issue_date = fields.Date(
        string="Visa Issue Date",
        help="Fill this information for expatriate employees.",
        groups='hr.group_hr_user',
        tracking=True,
    )
    l10n_hk_member_class_ct_eevc_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_ct_eevc_id',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
    l10n_hk_member_class_ct_ervc_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_ct_ervc_id',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
    l10n_hk_member_class_ct_ervc2_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_ct_ervc2_id',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )

    # Autopay fields
    l10n_hk_autopay_account_type = fields.Selection(
        selection=[
            ('bban', 'Bank Code + Account Number + Beneficiary Name'),
            ('svid', 'FPS ID'),
            ('emal', 'Email address + / Bank Code'),
            ('mobn', '(Country Code) Mobile Phone Number + / Bank Code'),
            ('hkid', 'HKID + Beneficiary Name'),
        ],
        default='bban',
        string='Autopay Payment Type',
        groups='hr.group_hr_user',
    )
    l10n_hk_autopay_svid = fields.Char(string='FPS Identifier', groups="hr.group_hr_user")
    l10n_hk_autopay_email = fields.Char(string='Autopay Email Address', groups="hr.group_hr_user")
    l10n_hk_autopay_mobile = fields.Char(string='Autopay Mobile Number', groups="hr.group_hr_user")
    l10n_hk_autopay_ref = fields.Char(string='Autopay Reference', groups="hr.group_hr_user")
    l10n_hk_leaving_hk = fields.Boolean(related='version_id.l10n_hk_leaving_hk', inherited=True, readonly=False, groups="hr.group_hr_user")

    l10n_hk_internet = fields.Monetary(readonly=False, related="version_id.l10n_hk_internet", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_hk_rental_id = fields.Many2one(related="version_id.l10n_hk_rental_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_hk_rental_valid_up_to_date = fields.Date(related="version_id.l10n_hk_rental_valid_up_to_date", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('l10n_hk_autopay_email')
    def _check_l10n_hk_autopay_email(self):
        for employee in self:
            if employee.l10n_hk_autopay_email and not single_email_re.match(employee.l10n_hk_autopay_email):
                raise ValidationError(employee.env._('The "Autopay Email Address" field must be filled with a single correct email address.'))

    @api.constrains('l10n_hk_autopay_mobile')
    def _check_l10n_hk_auto_mobile(self):
        for employee in self:
            if employee.l10n_hk_autopay_mobile and not auto_mobile_re.match(employee.l10n_hk_autopay_mobile):
                raise ValidationError(employee.env._('The "Autopay Mobile Number" must match the format "+xxx-xxxxxxxx".'))

    @api.onchange("l10n_hk_postal_state_id")
    def _onchange_l10n_hk_postal_state_id(self):
        if self.l10n_hk_postal_state_id:
            self.l10n_hk_postal_country_id = self.l10n_hk_postal_state_id.country_id

    @api.depends('l10n_hk_surname', 'l10n_hk_given_name')
    def _compute_legal_name(self):
        hk_employees = self.filtered(lambda e: e.company_id.country_code == 'HK' and (e.l10n_hk_surname or e.l10n_hk_given_name))
        for employee in hk_employees:
            employee.legal_name = ' '.join(filter(None, [employee.l10n_hk_surname, employee.l10n_hk_given_name]))

        super(HrEmployee, self - hk_employees)._compute_legal_name()

    @api.model
    def _get_years_of_service(self, period_start_date, period_end_date):
        """
        Calculates years of service according to the HK statutory methodology.

        This involves:
        1. Counting the number of full years of service.
        2. Prorating the remaining incomplete year by dividing the remaining days of service
           by the actual number of days in that specific annual cycle (365 or 366).
        :return: a float representing the number of years of service.
        """
        if period_start_date > period_end_date:
            return 0

        full_years = relativedelta(period_end_date, period_start_date).years
        last_anniversary_date = period_start_date + relativedelta(years=full_years)

        remaining_days = (period_end_date - last_anniversary_date).days + 1

        # The divisor is the total number of days in the 12-month cycle of the
        # incomplete year. For example, if the last anniversary was May 1, 2027,
        # this cycle is May 1, 2027, to April 30, 2028.
        next_anniversary_date = last_anniversary_date + relativedelta(years=1)
        days_in_pro_rata_year = (next_anniversary_date - last_anniversary_date).days

        return full_years + (remaining_days / days_in_pro_rata_year)

    def _compute_l10n_hk_rentals_count(self):
        employees_rentals_count = dict(self.env["l10n_hk.rental"]._read_group(
            domain=[("employee_id", "in", self.ids)],
            groupby=["employee_id"],
            aggregates=["__count"],
        ))
        for employee in self:
            employee.l10n_hk_rentals_count = employees_rentals_count.get(employee, 0)

    def _get_proxy_type(self):
        self.ensure_one()
        if self.l10n_hk_autopay_account_type == "bban":
            return self.primary_bank_account_id.sanitized_account_number
        else:
            return self[f"l10n_hk_autopay_{self.l10n_hk_autopay_account_type}"]

    def action_open_rentals(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('l10n_hk_hr_payroll.action_l10n_hk_rental')
        action.update({
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'default_employee_id': self.id,
                'search_default_employee_id': self.id,
                'search_default_filter_is_confirmed': True,
                'search_default_filter_is_draft': True,
            },
        })
        return action

    def _l10n_hk_get_468_rule_employees(self):
        """
        Evaluates non-continuous employees against the Hong Kong '4-68 Rule' for continuous contracts.

        Functional Context:
        Under HK law, an employee earns continuous status if they maintain an unbroken streak of
        4 "qualifying weeks". A week legally qualifies if the employee worked:
          - 17+ hours in that specific week, OR
          - 68+ hours in total across that week and the 3 preceding weeks.

        To evaluate this, the method analyzes a 7-week period (4 target weeks + 3 historical
        lookback weeks) to calculate the rolling totals and determine the current unbroken streak.
        :return:
            - approaching_employees: Streak of exactly 3 qualifying weeks
            - met_employees: Streak of 4 qualifying weeks or more
        """
        today = fields.Datetime.today()

        period_start = today - timedelta(weeks=4, days=today.weekday())
        period_end = period_start + timedelta(weeks=4, days=-1)

        # We need up to three weeks before the period to look back at the worked hours before that.
        lookback_start = period_start - timedelta(weeks=3)

        hk_companies = self.env.companies.filtered(lambda c: c.country_id.code == "HK")
        candidates = self.env["hr.employee"].search([
            ("company_id", "in", hk_companies.ids),
            ("employee_type_id.code", "=", "NON_CONTINUOUS"),
            ("first_contract_date", "!=", False),
            ("first_contract_date", "<=", period_start + timedelta(weeks=1)),
        ])
        if not candidates:
            return None, None

        work_entries_vals = candidates.generate_work_entries(lookback_start, period_end)
        versions = candidates._get_versions_with_contract_overlap_with_period(
            lookback_start.date(), period_end.date()
        ).grouped('employee_id')

        met_employees, approaching_employees = [], []
        for employee in candidates:
            employee_versions = versions.get(employee)
            if not employee_versions:
                continue  # just as a safety measure

            streak = 0
            weekly_hours = []
            for i, dt in enumerate(rrule(WEEKLY, dtstart=lookback_start, until=period_end)):
                week_start = dt.date()
                week_end = week_start + timedelta(days=6)
                work_hours = employee_versions.get_work_hours(week_start, week_end, work_entries_vals)
                weekly_hours.append(sum(work_hours.values()))

                four_weeks_totals = sum(weekly_hours[max(i - 3, 0): i + 1])
                if weekly_hours[i] >= 17 or four_weeks_totals >= 68:
                    streak += 1
                else:
                    streak = 0

            if streak >= 4:
                met_employees.append(employee.id)
            elif streak == 3:
                approaching_employees.append(employee.id)

        return self.browse(approaching_employees), self.browse(met_employees)
