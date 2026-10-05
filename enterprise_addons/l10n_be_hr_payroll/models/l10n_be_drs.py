# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from dateutil.relativedelta import relativedelta
from odoo.addons.l10n_be_hr_payroll.models.utils import format_amount
from odoo.exceptions import ValidationError

from odoo import api, fields, models

LANG_CODE = {
    'nl_NL': '1',
    'fr_FR': '2',
    'de_DE': '3',
    'nl_BE': '1',
    'fr_BE': '2',
    'de_BE': '3',
}


class L10nBeDrs(models.Model):
    _name = 'l10n.be.drs'
    _description = 'DRS'
    _inherit = 'l10n.be.onss.batch.declaration'

    def _get_year_selection(self):
        current_year = fields.Date.context_today(self).year
        next_year = current_year + 1
        return [
            (str(current_year), current_year),
            (str(next_year), next_year),
        ]

    name = fields.Char(compute='_compute_name', store=True, readonly=True)
    sector = fields.Selection([
        ('work_accident', 'Work Accidents (Fedris)'),
        ('unemployment', 'Unemployment (ONEM/RVA)'),
        ('compensation', 'Benefits & Compensation (INAMI/RIZIV)'),
    ], string="Sector", required=True)
    risk_id = fields.Many2one(comodel_name='l10n.be.drs.risk', compute="_compute_risk", inverse="_inverse_risk",
        store=True, readonly=False, required=True, domain="[('id', 'in', allowed_risk_ids)]")
    identification = fields.Char(related="risk_id.identification")
    code = fields.Char(related="risk_id.code")
    allowed_risk_ids = fields.Many2many(comodel_name='l10n.be.drs.risk', compute="_compute_allowed_risks",
        export_string_translation=False)

    # Employee
    employee_id = fields.Many2one(comodel_name="hr.employee", string="Employee", required=True, index='btree',
        domain="[('company_id', 'in', allowed_company_ids), ('company_id.partner_id.country_id.code', '=', 'BE')]")

    # Employer
    company_id = fields.Many2one(related="employee_id.company_id", default=None)
    payroll_config_id = fields.Many2one(comodel_name='payroll.config.settings', compute='_compute_payroll_config')
    company_onss_number = fields.Char(compute='_compute_payroll_config')

    # Technical
    is_automatically_created = fields.Boolean()

    # WECH009 Specifics
    leave_allocation_id = fields.Many2one('hr.leave.allocation', index='btree_not_null')
    holiday_hours = fields.Float(compute='_compute_holiday_hours', readonly=False, store=True,
        help="Total amount of hours allocated to the employee")

    # WECH010 Specifics
    month = fields.Selection([
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
        ('12', 'December')
    ], default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Integer(default=lambda self: fields.Date.context_today(self).year)

    @api.depends('risk_id', 'employee_id')
    def _compute_name(self):
        for drs in self:
            ref_date = drs.create_date or fields.Datetime.now()
            drs.name = f'{ref_date.strftime('%Y%m%d%H%M%S%f')}'

    @api.depends('sector')
    def _compute_risk(self):
        for drs in self:
            if drs.sector != drs.risk_id.sector:
                drs.risk_id = False

    def _inverse_risk(self):
        for drs in self:
            if drs.risk_id.sector and not drs.sector:
                drs.sector = drs.risk_id.sector

    @api.onchange('risk_id')
    def _onchange_risk(self):
        for drs in self:
            if drs.risk_id.sector and not drs.sector:
                drs.sector = drs.risk_id.sector

    @api.depends('sector')
    def _compute_allowed_risks(self):
        all_risks = self.env["l10n.be.drs.risk"].search([])
        risks_per_sector = all_risks.grouped('sector')
        for drs in self:
            drs.allowed_risk_ids = risks_per_sector.get(drs.sector) if drs.sector else all_risks

    @api.depends('employee_id')
    def _compute_wage(self):
        for drs in self:
            version_id = drs.employee_id._get_version(drs.create_date)
            drs.wage_type = '1' if version_id.wage_type == "hourly" else '4'
            drs.wage = format_amount(version_id[version_id._get_contract_wage_field()], width=10)

    @api.depends('company_id', 'month', 'year')
    def _compute_payroll_config(self):
        for drs in self:
            if not drs.company_id:
                drs.payroll_config_id = False
            elif drs.year and drs.month:
                drs.payroll_config_id = drs.company_id._get_payroll_config(date(int(drs.year), int(drs.month), 1))
            else:
                drs.payroll_config_id = drs.company_id.current_payroll_config_id
            drs.company_onss_number = drs.payroll_config_id.onss_registration_number

    @api.depends('leave_allocation_id')
    def _compute_holiday_hours(self):
        for drs in self:
            if drs.leave_allocation_id:
                drs.holiday_hours = drs.leave_allocation_id.number_of_hours

    # =======================================
    # MIXIN OVERRIDES
    # =======================================

    def _get_declaration_type(self):
        self.ensure_one()
        return self.identification

    def _get_base_schema_url(self):
        return "https://www.socialsecurity.be/docu_xml/drs/onem/"

    def _get_base_schema_filename(self):
        self.ensure_one()
        return f'scen{int(self.identification[4:])}/{self.identification}_'

    def _get_declaration_template_xmlid(self):
        self.ensure_one()
        return f'l10n_be_hr_payroll.{self.identification.lower()}_xml_export'

    def _get_rendering_data(self):
        self.ensure_one()
        errors = []
        if not self.company_onss_number:
            errors.append(self.env._("No ONSS registration number was found for company %s. Please provide at least one.", self.company_id.name))
        if not self.employee_id._is_niss_valid():
            errors.append(self.env._('Invalid NISS number for %s', self.employee_id.name))
        if not self.payroll_config_id.l10n_be_employer_category_id:
            errors.append(self.env._('Missing Employer Category for %s', self.company_id.name))
        if self.employee_id.lang not in LANG_CODE:
            errors.append(self.env._("Employee's language must be either Dutch, French or German"))

        version = self.employee_id._get_version(self.create_date)
        if not version.l10n_be_joint_committee_id:
            errors.append(self.env._("%(emp)s is missing a joint commitee.", emp=self.employee_id.name))
        first_occupation_date = version._get_occupation_dates()[-1][1]
        date_from, date_to = self._get_first_last_day_of_month()
        day_list = self._get_nature_of_day_list()
        if self.identification == 'WECH010' and not day_list:
            errors.append(self.env._(
                "%(emp)s didn't take any paid or youth/senior leaves during that month, thus a declaration for that month is unnecessary.",
                emp=self.employee_id.name,
            ))
        attestation_status = '1' if self.state == 'refused' else '0'
        if errors:
            raise ValidationError("\n\n".join(errors))
        result = {
            'data': self,
            'first_occupation_date': first_occupation_date,
            'attestation_status': attestation_status,
            'declaration_lang': LANG_CODE.get(self.employee_id.lang, '2'),
            'contact_first_name': '',  # temporarily disabled as it is optional
            'contact_last_name': '',
            'contact_phone': '',
            'contact_email': '',
            'employer_class': self.payroll_config_id.l10n_be_employer_category_id.dmfa_code,
            'l10n_be_company_number': format_amount(self.payroll_config_id.l10n_be_company_number or 0, width=10, hundredth=False),
            'onss_registration_number': format_amount(self.company_onss_number or 0, width=9, hundredth=False),
            'risk_code': self.risk_id.code,
            'apprenticeship': 1 if version.l10n_be_dimona_category == 'alt' else False,
            'holiday_start_month': self.create_date.strftime('%Y-%m'),
            'remuneration_time_unit': '1' if version.wage_type == 'hourly' else '4',
            'declaration_comment': '',  # optionnal, not implemented yet
            'sector': '1' if self.payroll_config_id.l10n_be_employer_category_id.sector == 'private' else '2',
            'wage': format_amount(version[version._get_contract_wage_field()], width=10),
            'number_of_days_per_week': format_amount(version.resource_calendar_id.days_per_week, width=3),
            'number_of_hours_per_week': format_amount(version.resource_calendar_id.hours_per_week, width=4),
            'reference_number_of_hours_per_week': format_amount(version._get_reference_calendar().hours_per_week, width=4),
            'worker_code': version.l10n_be_worker_code_id.dmfa_code,
            'worker_status': version.l10n_be_worker_status,
            'committee': version.l10n_be_joint_committee_id.egov3_code,
            # WECH010
            'date_from': date_from.strftime('%Y-%m-%d'),
            'date_to': date_to.strftime('%Y-%m-%d'),
            'nature_of_day_list': day_list,
        }
        return result

    # =======================================
    # WECH010
    # =======================================

    def _get_first_last_day_of_month(self):
        self.ensure_one()
        if not self.year or not self.month:
            return (False, False)
        date_from = date(self.year, int(self.month), 1)
        date_to = date_from + relativedelta(day=31)
        return (date_from, date_to)

    def _get_nature_of_day_list(self):
        self.ensure_one()
        if self.identification != 'WECH010':
            return False
        day_dict = {}
        date_from, date_to = self._get_first_last_day_of_month()
        work_entries = self.employee_id.generate_work_entries(date_from, date_to)
        for work_entry in work_entries:
            nature_code = work_entry['work_entry_type_id'].l10n_be_drs_nature
            if nature_code not in ('3.1', '3.4'):  # Legal Time Off or Youth/Senior Time Off
                continue
            if (work_entry['date'], nature_code) in day_dict:
                day_dict[work_entry['date'], nature_code].hours_amount += round(work_entry['duration'] * 100)
            else:
                day_dict[work_entry['date'], nature_code] = {
                    'date': work_entry['date'].strftime('--%m-%d'),
                    'nature_code': nature_code,
                    'hours_amount': round(work_entry['duration'] * 100),
                }
        return day_dict.values()
