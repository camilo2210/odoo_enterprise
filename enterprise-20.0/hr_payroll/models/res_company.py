# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _selection_payroll_closing_date(self):
        selections = []
        for day in range(22, 31):
            label = f"{day} of the pay month"
            selections.append((day, label))
        selections.append((31, "Last day of the pay month"))
        for day in range(1, 10):
            label = f"{day} of the next month"
            selections.append((day, label))
        return selections

    first_payrun_date = fields.Date(
        "First Payrun Month",
        help="When do you plan on starting Odoo for your Payroll?",
        compute="compute_fields_from_parent",
        store=True,
        readonly=False,
        recursive=True,
    )
    payroll_closing_date = fields.Selection(
        selection='_selection_payroll_closing_date',
        string="Payroll Closing Date",
        compute="compute_fields_from_parent",
        store=True,
        readonly=False,
        recursive=True,
    )

    ytd_reset_day = fields.Integer(
        default=1,
        string='YTD Reset Day of the month',
        help="""Day where the YTD will be reset every year. If zero or negative, then the first day of the month will be selected instead.
        If greater than the last day of a month, then the last day of the month will be selected instead.""")
    ytd_reset_month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December')],
        default='1', string='YTD Reset Month')
    payslip_generate_and_send_trigger = fields.Selection(
        [
            ('on_confirmed', 'When Confirmed'),
            ('on_paid', 'When Paid'),
            ('never', 'Manually'),
        ],
        default='on_confirmed',
        string='Payslips Generate and Send Trigger',
    )
    deferred_time_off_manager = fields.Many2one('res.users')
    selected_payroll_structure_id = fields.Many2one('hr.payroll.structure.type')

    payroll_config_ids = fields.One2many('payroll.config.settings', 'company_id', string='Payroll Configurations', copy=False)
    current_payroll_config_id = fields.Many2one(
        'payroll.config.settings',
        string="Current Payroll Configuration",
        compute='_compute_current_payroll_config_id',
        compute_sudo=True,
    )

    @api.depends('parent_id', 'parent_id.first_payrun_date', 'parent_id.payroll_closing_date')
    def compute_fields_from_parent(self):
        fields_to_copy = ['first_payrun_date', 'payroll_closing_date']
        for company in self:
            for field_to_copy in fields_to_copy:
                if company.parent_id and not company[field_to_copy]:
                    company[field_to_copy] = company.parent_id[field_to_copy]

    @api.constrains('ytd_reset_day', 'ytd_reset_month')
    def _check_valid_reset_date(self):
        for company in self:
            # We try if the date exists in 2023, which is not a leap year.
            max_possible_day = calendar.monthrange(2023, int(company.ytd_reset_month))[1]
            if company.ytd_reset_day < 1 or company.ytd_reset_day > max_possible_day:
                raise ValidationError(self.env._("The YTD reset day must be a valid day of the month : since the current month is %(month)s, it should be between 1 and %(day)s.",
                    month=company._fields['ytd_reset_month']._description_selection(self.env)[int(company.ytd_reset_month) - 1][1],
                    day=max_possible_day
                ))

    @api.depends('payroll_config_ids.date_version', 'active')
    def _compute_current_payroll_config_id(self):
        today = fields.Date.context_today(self)
        config_by_company = dict(self.env['payroll.config.settings']._read_group(
            domain=[('company_id', 'in', self.ids), ('date_version', '<=', today)],
            groupby=['company_id'],
            aggregates=['id:recordset'],
        ))
        for company in self:
            configs = config_by_company.get(company)
            new_current_version = False
            if configs:
                new_current_version = max(configs, key=lambda c: c.date_version)
            elif company.payroll_config_ids:
                new_current_version = company.payroll_config_ids[0]
            # To not trigger any computation if still the same version
            if company.current_payroll_config_id != new_current_version:
                company.current_payroll_config_id = new_current_version

    def _get_payroll_config(self, date=None):
        """
        Return the payroll configuration that should be used for the given date.
        If no valid configuration is found, we return the very first configuration of the company.
        """
        self.ensure_one()
        if not date:
            date = fields.Date.context_today(self)
        configs = self.payroll_config_ids
        date_configs = configs.filtered_domain([('date_version', '<=', date)])
        return max(date_configs, key=lambda v: v.date_version) if date_configs else configs[:1]

    def create_payroll_config(self, date_version=None):
        if isinstance(date_version, str):
            date_version = fields.Date.to_date(date_version)
        elif isinstance(date_version, datetime):
            date_version = date_version.date()

        vals_list = []
        for company in self:
            if company.payroll_config_ids:
                last_config = company.payroll_config_ids[-1]
                vals_list.append({
                    **last_config.copy_data()[0],
                    'date_version': date_version or company.create_date,
                })
            else:
                vals_list.append({
                    'company_id': company.id,
                    'date_version': date_version or company.create_date,
                })

        payroll_configs = self.env['payroll.config.settings'].create(vals_list)
        for company, payroll_config in zip(self, payroll_configs):
            company.payroll_config_ids |= payroll_config
        return payroll_configs

    def get_last_ytd_reset_date(self, target_date):
        self.ensure_one()
        last_ytd_reset_date = date(target_date.year, int(self.ytd_reset_month), self.ytd_reset_day)
        if last_ytd_reset_date > target_date:
            last_ytd_reset_date += relativedelta(years=-1)
        return last_ytd_reset_date

    def _get_monthly_payroll_next_closing_date(self):
        """Return the company's pay run closing date.
        :rtype date | None

        Logic:
        - If payrun_closing_day is between [1..9], the closing date is in the next month.
        - If payrun_closing_day is between [22..31] the closing date is in the current month.
        - If today is past the computed closing date, return the closing date of the next month.
        """
        self.ensure_one()
        if not self.payroll_closing_date:
            return None
        today = fields.Date.context_today(self)
        if first_payrun_date := self.first_payrun_date:
            if today < first_payrun_date:
                today = first_payrun_date

        payrun_closing_day = int(self.payroll_closing_date)
        month_offset = 1 if payrun_closing_day <= 9 and payrun_closing_day <= today.day else 0

        closing_date = today + relativedelta(months=month_offset, day=payrun_closing_day)
        if today > closing_date:
            closing_date += relativedelta(months=1, day=payrun_closing_day)

        return closing_date

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies_without_payroll_config = companies.filtered(lambda c: not c.payroll_config_ids)
        if companies_without_payroll_config:
            companies_without_payroll_config.sudo().create_payroll_config()
        return companies
