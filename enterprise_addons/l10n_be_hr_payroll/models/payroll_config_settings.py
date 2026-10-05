# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.business_data import split_vat


class PayrollConfigSettings(models.Model):
    _inherit = 'payroll.config.settings'

    onss_registration_number = fields.Char(string="ONSS Registration Number", help="9-digit code given by ONSS",
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_employer_category_id = fields.Many2one('l10n.be.employer.category', string="Employer Category", index='btree_not_null')
    l10n_be_employer_category_code = fields.Char(related="l10n_be_employer_category_id.egov3_code")
    l10n_be_allowed_worker_code_ids = fields.Many2many(related="l10n_be_employer_category_id.allowed_worker_code_ids")

    l10n_be_nace_code_id = fields.Many2one(
        'l10n.be.nace.code', string="NACE Code", index='btree_not_null',
        help="Mandatory for all staff members of provincial and local public administrations. Mandatory for staff members of the Flemish, French and German-speaking Communities occupying a position allocated by the Maribel Social Fund for the public sector.",
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_company_number = fields.Char('Company Number', compute='_compute_l10n_be_company_number', store=True, readonly=False)
    l10n_be_revenue_code = fields.Char('Revenue Code', compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_ffe_employer_type = fields.Selection([
        ('O', 'O - Employer belonging to a category excluded from Closure Fund contributions'),
        ('N', 'N - Employer individually exempt, although the category is normally subject to contributions'),
        ('C', 'C - Employer subject to the commercial Closure Fund contribution'),
        ('B', 'B - Employer subject to the non‑commercial Closure Fund contribution'),
    ], string="Business Closure Fund Employer Type", help="FFE code for the employer type", default="C",
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_holiday_pay_fund_name = fields.Char(string="Holiday Pay Fund")
    l10n_be_holiday_pay_fund_number = fields.Char(string="Holiday Pay Fund Number")
    l10n_be_SEPPT_name = fields.Char("External Service for Prevention and Protection at Work Name")
    l10n_be_SEPPT_number = fields.Char("External Service for Prevention and Protection at Work Number")
    employee_accident_insurance_name = fields.Char("Accident Insurance (Employee) Name")
    employee_accident_insurance_number = fields.Char("Accident Insurance (Employee) Number")
    worker_accident_insurance_name = fields.Char("Accident Insurance (Worker) Name")
    worker_accident_insurance_number = fields.Char("Accident Insurance (Worker) Number")
    group_insurance_name = fields.Char("Group Insurance Name")
    group_insurance_number = fields.Char("Group Insurance Number")
    l10n_be_main_joint_committee = fields.Many2one('l10n.be.joint.committee', string="Main Joint Committee", context={'active_test': False})
    onss_importance_code = fields.Selection(string="Company Size",
        help="ONSS Company Size",
        selection=[
            ('1', '1 to 4 employees'),
            ('2', '5 to 9 employees'),
            ('3', '10 to 19 employees'),
            ('4', '20 to 49 employees'),
            ('5', '50 to 99 employees'),
            ('6', '100 to 199 employees'),
            ('7', '200 to 499 employees'),
            ('8', '500 to 999 employees'),
            ('9', '1000+ employees'),
        ],
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_in_difficulty = fields.Boolean(
        string="In Difficulty",
        help="The Federal Minister of Employment may grant companies recognition as a company in difficulty",
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_at_risk_groups_contribution = fields.Boolean(
        string="At-Risk Groups Contribution",
        help="The contribution for 'at-risk groups' is a specific employer contribution paid to the ONSS "
             "(National Social Security Office) in Belgium, "
             "intended to finance training and professional integration initiatives for certain categories of workers.",
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_ipa_reduction = fields.Boolean(
        string="IPA Reduction",
        help="Small and Middle company in defined Joint Committee are eligible to a Withholding Tax Exemption of 0.12%",
        compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_employee_retirement_fund = fields.Selection([
        ('0', '0 - Contribution due'),
        ('1', '1 - Increased contribution'),
        ('2', '2 - Solidarity contribution'),
        ('8', '8 - Contribution not due'),
        ('9', '9 - Not applicable'),
    ], string="Employee Retirement Fund")
    l10n_be_worker_retirement_fund = fields.Selection([
        ('0', '0 - Contribution due'),
        ('1', '1 - Increased contribution'),
        ('2', '2 - Solidarity contribution'),
        ('8', '8 - Contribution not due'),
        ('9', '9 - Not applicable'),
    ], string="Worker Retirement Fund")
    l10n_be_sector = fields.Selection([
        ('private', 'Private'),
        ('public_federal_regional', 'Public (Federal/Regional)'),
        ('public_other', 'Public (Other)'),
    ], string="Sector", compute='_compute_fields_from_parent', store=True, readonly=False)
    l10n_be_has_employees = fields.Boolean(related='company_id.l10n_be_has_employees')
    l10n_be_has_workers = fields.Boolean(related='company_id.l10n_be_has_workers')
    l10n_be_declaration_frequency = fields.Selection(
        [("monthly", "Monthly"), ("quarterly", "Quarterly")],
        string="Declaration Frequency",
        default="monthly",
        compute='_compute_fields_from_parent', store=True, readonly=False)

    hospital_insurance_amount_child = fields.Float(string="Hospital Insurance Amount per Child")
    hospital_insurance_amount_adult = fields.Float(string="Hospital Insurance Amount Per Adult")
    hospital_insurance_employee_contribution = fields.Float(
        string="Hospital Insurance Contribution by Employee",
        help="Default value for new employees")
    ambulatory_insurance_employee_contribution = fields.Float(
        string="Ambulatory Insurance Contribution by Employee",
        help="Default value for new employees",
    )
    ambulatory_insurance_amount_child = fields.Float(string="Ambulatory Insurance Amount Per Child")
    ambulatory_insurance_amount_adult = fields.Float(string="Ambulatory Insurance Amount Per Adult")
    exemption_sme_status = fields.Selection([
        ('startup', "Startup / early stage"),
        ('micro', "Micro Entreprise")
    ], string="SME Status", compute='_compute_fields_from_parent', store=True, readonly=False)

    allowed_joint_committee_ids = fields.Many2many('l10n.be.joint.committee', compute="_compute_allowed_joint_committee_ids", string="Allowed Joint Committees for Employees", context={'active_test': False})

    l10n_be_reduction_for_first_hires = fields.Boolean(string="Reduction for First Hires")

    l10n_be_first_hire_reduction_window_cap = fields.Integer(default=999)
    l10n_be_second_hire_reduction_window_cap = fields.Integer(default=20)
    l10n_be_third_hire_reduction_window_cap = fields.Integer(default=20)
    l10n_be_fourth_hire_reduction_window_cap = fields.Integer(default=20)
    l10n_be_fifth_hire_reduction_window_cap = fields.Integer(default=20)
    l10n_be_sixth_hire_reduction_window_cap = fields.Integer(default=20)

    l10n_be_first_hire_reductions_used_outside_odoo = fields.Integer(default=0)
    l10n_be_second_hire_reductions_used_outside_odoo = fields.Integer(default=0)
    l10n_be_third_hire_reductions_used_outside_odoo = fields.Integer(default=0)
    l10n_be_fourth_hire_reductions_used_outside_odoo = fields.Integer(default=0)
    l10n_be_fifth_hire_reductions_used_outside_odoo = fields.Integer(default=0)
    l10n_be_sixth_hire_reductions_used_outside_odoo = fields.Integer(default=0)

    l10n_be_first_hire_reduction_eligibility_date = fields.Date()
    l10n_be_second_hire_reduction_eligibility_date = fields.Date()
    l10n_be_third_hire_reduction_eligibility_date = fields.Date()
    l10n_be_fourth_hire_reduction_eligibility_date = fields.Date()
    l10n_be_fifth_hire_reduction_eligibility_date = fields.Date()
    l10n_be_sixth_hire_reduction_eligibility_date = fields.Date()

    _check_hospital_insurance_employee_contribution = models.Constraint(
        "CHECK(hospital_insurance_employee_contribution >= 0)",
        "The hospital insurance employee contribution can not be negative.",
    )

    @api.depends('company_id.vat')
    def _compute_l10n_be_company_number(self):
        for record in self:
            if record.company_id.vat and record.company_id.country_code == 'BE':
                vat_country, vat_number = split_vat(record.company_id.vat, default_country_code='BE')
                record.l10n_be_company_number = vat_number if vat_country == 'BE' else record.company_id.vat

    def _get_reductions_used_outside_odoo_fields(self):
        return ['l10n_be_second_hire_reductions_used_outside_odoo', 'l10n_be_third_hire_reductions_used_outside_odoo', 'l10n_be_fourth_hire_reductions_used_outside_odoo', 'l10n_be_fifth_hire_reductions_used_outside_odoo', 'l10n_be_sixth_hire_reductions_used_outside_odoo']

    def _get_reduction_window_caps_fields(self):
        return ['l10n_be_second_hire_reduction_window_cap', 'l10n_be_third_hire_reduction_window_cap', 'l10n_be_fourth_hire_reduction_window_cap', 'l10n_be_fifth_hire_reduction_window_cap', 'l10n_be_sixth_hire_reduction_window_cap']

    @api.constrains('l10n_be_company_number')
    def _check_l10n_be_company_number(self):
        for company in self.filtered(lambda c: c.l10n_be_company_number):
            number = company.l10n_be_company_number
            if not number.isdecimal() or len(number) != 10 or (not number.startswith('0') and not number.startswith('1')):
                raise ValidationError(self.env._("The company number should contain digits only, starts with a '0' or a '1' and be 10 characters long."))
            if (97 - (int(number[:-2]) % 97)) != int(number[-2:]):
                raise ValidationError(self.env._("The checksum digits of the company number are not correct."))

    @api.onchange('l10n_be_company_number')
    def _onchange_l10n_be_company_number(self):
        if self.l10n_be_company_number:
            self.l10n_be_company_number = re.sub(r'\D', '', self.l10n_be_company_number)

    @api.onchange('onss_registration_number')
    def _onchange_onss_registration_number(self):
        if self.onss_registration_number:
            self.onss_registration_number = re.sub(r'\D', '', self.onss_registration_number)

    @api.constrains('onss_registration_number')
    def _check_onss_registration_number(self):
        for company in self.filtered(lambda c: c.onss_registration_number):
            clean_number = company.onss_registration_number.replace('-', '').replace(' ', '')
            clean_number = re.sub(r'\D', '', company.onss_registration_number)
            if company.onss_registration_number != clean_number:
                company.onss_registration_number = clean_number

            if not clean_number.isdecimal() or len(clean_number) != 9:
                raise ValidationError(self.env._("The ONSS registration number should contain digits only and be 9 characters long."))
            if int(clean_number) % 97 != 96:
                raise ValidationError(self.env._("The checksum of the ONSS registration number is not correct."))

    @api.constrains(lambda self: (*self._get_reductions_used_outside_odoo_fields(), *self._get_reduction_window_caps_fields()))
    def _check_first_hire_caps(self):
        for config in self:
            for field in self._get_reductions_used_outside_odoo_fields():
                if config[field] > 13 or config[field] < 0:
                    raise ValidationError(self.env._('Reductions used must be between 0 and 13'))
            for field in self._get_reduction_window_caps_fields():
                if config[field] > 20 or config[field] < 0:
                    raise ValidationError(self.env._('Max Hire Cap must be between 0 and 20'))

    def _get_fields_to_copy_from_parent(self):
        return super()._get_fields_to_copy_from_parent() + [
            "l10n_be_nace_code_id",
            "l10n_be_company_number",
            "l10n_be_revenue_code",
            "l10n_be_ffe_employer_type",
            "onss_registration_number",
            "onss_importance_code",
            "exemption_sme_status",
            "l10n_be_in_difficulty",
            "l10n_be_at_risk_groups_contribution",
            "l10n_be_ipa_reduction",
            "l10n_be_sector",
            "l10n_be_declaration_frequency",
        ]

    def _get_branch_editable_fields(self):
        return super()._get_branch_editable_fields() + [
            "l10n_be_employer_category_id",
            "l10n_be_main_joint_committee",
            "l10n_be_employee_retirement_fund",
            "l10n_be_worker_retirement_fund",
            "employee_accident_insurance_name",
            "employee_accident_insurance_number",
            "worker_accident_insurance_name",
            "worker_accident_insurance_number",
            "hospital_insurance_amount_child",
            "hospital_insurance_amount_adult",
            "hospital_insurance_employee_contribution",
            "ambulatory_insurance_amount_child",
            "ambulatory_insurance_amount_adult",
            "group_insurance_name",
            "group_insurance_number",
            "l10n_be_SEPPT_name",
            "l10n_be_SEPPT_number",
        ]

    @api.depends('parent_id')
    def _compute_fields_from_parent(self):
        fields_to_copy = self._get_fields_to_copy_from_parent()
        for config in self:
            for field_to_copy in fields_to_copy:
                config[field_to_copy] = config.parent_id[field_to_copy] if config.parent_id else config[field_to_copy]

    @api.depends('l10n_be_employer_category_id')
    def _compute_allowed_joint_committee_ids(self):
        for config in self:
            if config.l10n_be_employer_category_id:
                config.allowed_joint_committee_ids = config.l10n_be_employer_category_id.allowed_joint_committee_ids
            else:
                config.allowed_joint_committee_ids = (
                    self.env["l10n.be.joint.committee"]
                    .with_context(active_test=False)
                    .search([("selectable", "=", True)])
                )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        if any(vals.get('l10n_be_employer_category_id', False) for vals in vals_list):
            self.env.ref('l10n_be_hr_payroll.ir_cron_fetch_onss_rates')._trigger()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get('l10n_be_employer_category_id', False):
            self.env.ref('l10n_be_hr_payroll.ir_cron_fetch_onss_rates')._trigger()
        if vals.get('l10n_be_main_joint_committee', False):
            joint_committee = self.env['l10n.be.joint.committee'].with_context(active_test=False).browse(vals.get('l10n_be_main_joint_committee'))
            joint_committee.active = True
        return res

    def action_open_hr_payroll_localization_form(self):
        return {
            'name': self.env._('Payroll Localization'),
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.config.settings',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'path': 'company-data',
        }
