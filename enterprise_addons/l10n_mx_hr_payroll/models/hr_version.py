# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_mx_holiday_bonus_rate = fields.Float(string="MX: Holiday Bonus Rate", groups="hr_payroll.group_hr_payroll_user", tracking=1)

    l10n_mx_christmas_bonus = fields.Float(string="Christmas bonus", default=15.0, groups="hr_payroll.group_hr_payroll_user")

    l10n_mx_payment_period_vouchers = fields.Selection([
        ('last_day_of_month', 'Last Day of the Month'),
        ('in_period', 'In the period'),
    ], default="last_day_of_month", required=True, groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_mx_meal_voucher_amount = fields.Monetary(string="MX: Meal Vouchers", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_mx_transport_amount = fields.Monetary(string="MX: Transport Amount", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_mx_gasoline_amount = fields.Monetary(string="MX: Gasoline Amount", groups="hr_payroll.group_hr_payroll_user", tracking=1)

    l10n_mx_savings_fund = fields.Monetary(string="MX: Savings Fund", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_mx_infonavit = fields.One2many(
        'l10n.mx.hr.infonavit', 'version_id', string="MX: Infonavit", groups="hr.group_hr_user", tracking=1)
    l10n_mx_fonacot = fields.One2many(
        'l10n.mx.hr.fonacot', 'version_id', string="MX: Fonacot", groups="hr.group_hr_user", tracking=1)

    l10n_mx_min_wage_zone = fields.Selection(
        selection=[
            ("zsmg", "General Zone"),
            ("zlfn", "Northern Border Zone")
        ],
        string="Minimum Wage Zone",
        required=True,
        default="zsmg",
        groups="hr_payroll.group_hr_payroll_user",
    )

    l10n_mx_is_seventh_day = fields.Boolean(
        string="MX: Seventh Day",
        help="Check this box to separately break down the seventh day in the payroll calculation.",
        groups="hr_payroll.group_hr_payroll_user",
    )

    _check_christmas_bonus_percentage = models.Constraint(
         'CHECK (0 <= l10n_mx_holiday_bonus_rate AND l10n_mx_holiday_bonus_rate <= 1.0)',
         'The Christmas Bonus rate must be between 0 and 100',
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "MX":
            whitelisted_fields += [
                "l10n_mx_fonacot",
                "l10n_mx_gasoline_amount",
                "l10n_mx_holiday_bonus_rate",
                "l10n_mx_infonavit",
                "l10n_mx_meal_voucher_amount",
                "l10n_mx_payment_period_vouchers",
                "l10n_mx_savings_fund",
                "l10n_mx_transport_amount",
            ]
        return whitelisted_fields

    def _preprocess_work_hours_data(self, work_data, date_from, date_to):
        if (
            len(self) != 1
            or not self.has_static_work_entries()
            or self.country_code != 'MX'
        ):
            return

        payslip = self.env['hr.payslip'].search([
            ('date_from', '<=', date_from),
            ('date_to', '>=', date_to),
            ('employee_id', '=', self.employee_id.id),
        ], limit=1)

        calendar = payslip._get_out_of_contract_calendar(self) if payslip else self.resource_calendar_id
        date_start = max(date_from, self.date_start or date_from)
        date_end = min(date_to, self.date_end or date_to)

        is_wrong_duration = payslip.is_wrong_duration if payslip else False
        if date_start != date_from or date_end != date_to or is_wrong_duration:
            effective_days = (date_end - date_start).days + 1
        else:
            effective_days = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_mx_schedule_table', date_to)[self.schedule_pay]

        total_hours = effective_days * calendar.hours_per_day
        work_time = sum(hours for (work_entry, _options), hours in work_data.items() if not work_entry.is_extra_hours)
        remain_hours = total_hours - work_time

        if self.l10n_mx_is_seventh_day and self.schedule_pay in ('weekly', '14_days'):
            seventh_day_work_entry_type = self.env.ref('hr_work_entry.mx_work_entry_type_seventh_day', raise_if_not_found=False)
            if seventh_day_work_entry_type:
                work_data[seventh_day_work_entry_type, self.env['hr.salary.rule.category']] = remain_hours
                return

        attendance_work_entry_type = self.env['hr.work.entry.type'].browse(self._get_default_work_entry_type_id())
        if attendance_work_entry_type.exists():
            work_data[attendance_work_entry_type, self.env['hr.salary.rule.category']] += remain_hours
