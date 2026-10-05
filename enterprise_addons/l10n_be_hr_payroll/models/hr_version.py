import json
import jwt
import re
import secrets
import string
import time
import logging

from collections import defaultdict
from cryptography.hazmat.primitives import serialization
from datetime import datetime, date, timedelta, UTC
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta
from requests import request
from requests.exceptions import HTTPError
from werkzeug.urls import url_quote, url_encode
import random

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import float_round, file_open, format_amount
from odoo.tools.float_utils import float_compare
from odoo.exceptions import ValidationError, UserError

EMPLOYER_ONSS = 0.2714

# Fields whose amount is the real cost of the benefit for the employer, while the
# benefit in kind taxed on the employee is a flat monthly amount defined by a rule
# parameter.
BIK_RULE_PARAMETERS = {
    'internet': 'bik_internet_amount',
    'mobile': 'bik_phone_sub_amount',
    'mobile_amount': 'bik_phone_amount',
    'laptop': 'bik_laptop_amount',
    'tablet': 'bik_tablet_amount',
}


with file_open('l10n_be_hr_payroll/data/dimona_api_data.json') as f_api_data:
    API_DATA = json.load(f_api_data)
DIMONA_TIMEOUT = 30

_logger = logging.getLogger(__name__)


class HrVersion(models.Model):
    _inherit = 'hr.version'

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        fields_description = super().fields_get(allfields, attributes)
        self._add_bik_amount_to_help(fields_description)
        return fields_description

    @api.model
    def _add_bik_amount_to_help(self, fields_description):
        """ Append the taxed benefit in kind to the tooltip of the fields above.

        The amounts are indexed over time through their rule parameter, so they
        are resolved at each call instead of being hardcoded in the field
        definitions.
        """
        # The rule parameters are Belgian, hence always expressed in euro, whatever
        # the currency of the company reading the tooltip.
        currency = self.env.ref('base.EUR', raise_if_not_found=False)
        if not currency:
            return
        for field_name, parameter_code in BIK_RULE_PARAMETERS.items():
            field_description = fields_description.get(field_name)
            if not field_description or 'help' not in field_description:
                continue
            amount = self.env['hr.rule.parameter']._get_parameter_from_code(parameter_code, raise_if_not_found=False)
            if not amount:
                continue
            field_description['help'] = "%s\n%s" % (
                field_description['help'],
                self.env._(
                    "Benefit in kind: %(amount)s / month.",
                    amount=format_amount(self.env, amount, currency),
                ),
            )

    @api.model
    def _get_available_vehicles_domain(self, driver_ids=None, vehicle_type='car'):
        domain = Domain.AND([
            Domain.OR([
                [('company_id', '=', False)],
                [('company_id', '=', self.company_id.id)],
            ]),
            [('model_id.vehicle_type', '=', vehicle_type)],
            Domain.OR([
                [('plan_to_change_vehicle', '=', True)],
                [('future_driver_id', 'in', driver_ids.ids if driver_ids else [])],
            ]),
            [('write_off_date', '=', False)],
        ])
        waiting_stage = self.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False)
        if waiting_stage:
            domain = Domain('state_id', '!=', waiting_stage.id) & domain
        return domain

    @api.model
    def _get_vehicles_without_current_drivers_domain(self, driver_ids=None, vehicle_type='car'):
        """
            This domain is identical to the one in _get_available_vehicles_domain. The difference is
            that it excludes vehicles that already have a driver or a future driver, even when
            driver is the employee under the contract or plans to change the car in the future.
        """
        domain = Domain([
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id),
            ('future_driver_id', '=', False),
            ('model_id.vehicle_type', '=', vehicle_type),
            ('driver_id', '=', False),
            ('write_off_date', '=', False),
        ])
        waiting_stage = self.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False)
        if waiting_stage:
            domain = Domain('state_id', '!=', waiting_stage.id) & domain
        return domain

    def _get_possible_model_domain(self, vehicle_type='car'):
        return [('can_be_requested', '=', True), ('vehicle_type', '=', vehicle_type)]

    allowed_joint_committee_ids = fields.Many2many(related="payroll_config_id.allowed_joint_committee_ids", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_reorganisation_measure_ids = fields.Many2many(related="resource_calendar_id.l10n_be_reorganisation_measure_ids", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_daily_wage = fields.Monetary(
        string="Daily Wage (Belgium)",
        compute="_compute_daily_wage",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_be_joint_committee_id = fields.Many2one(
        'l10n.be.joint.committee',
        string="Joint Committee",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        index='btree_not_null',
        domain=[('selectable', '=', 'True')],
        compute='_compute_l10n_be_joint_committee_id',
        store=True,
        readonly=False
    )
    l10n_be_egov3_code = fields.Char(related='l10n_be_joint_committee_id.egov3_code', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_worker_code_id = fields.Many2one(
        'l10n.be.worker.code',
        compute='_compute_l10n_be_worker_code_id',
        store=True,
        readonly=False,
        string="Sub-type",
        index='btree_not_null',
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_worker_code_is_single = fields.Boolean(
        compute='_compute_l10n_be_worker_code_is_single', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_work_exemption = fields.Selection(
        selection=[
            ('0', 'No Exemption'),
            ('2', 'Full Exemption for the Entire Quarter'),
            ('3', 'Full Exemption for the Entire Quarter granted before December 29th, 2017'),
            ('4', 'Full Exemption for the Entire Quarter under a Collective Labor Agreement granted before December 29th, 2017'),
            ('5', 'Full Exemption for the Entire Quarter and Training with a cost of ≥ 20% of Annual Gross Salary'),
            ('7', 'Exemption for the Entire Quarter up to less than a third of a Full-Time Occupation'),
            ('8', 'Exemption for the Entire Quarter up to less than a third of a Full-Time Occupation and Training with a cost of ≥ 20% of Annual Gross Salary'),
        ],
        string='Work Exemption',
        default='0',
        required=True,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_work_exemption_date = fields.Date(
        string='Exemption Start Date', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_work_exemption_training_situation = fields.Selection(
        selection=[
            ('0', 'No Training'),
            ('1', 'Mandatory Training'),
            ('2', 'Obligation to undergo vocational reclassification'),
        ],
        default='0',
        required=True,
        string='Training Situation',
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_work_exemption_training_date = fields.Date(
        string='Training Start Date',
        compute='_compute_l10n_be_work_exemption_training_date',
        store=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_employer_category_id = fields.Many2one(related="payroll_config_id.l10n_be_employer_category_id", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_employer_category_code = fields.Char(related="payroll_config_id.l10n_be_employer_category_code", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_allowed_worker_code_ids = fields.Many2many(related="payroll_config_id.l10n_be_allowed_worker_code_ids", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_part_time_status = fields.Selection([
        ('voluntary', 'Voluntary'),
        ('with_unemployment_rights_agr', 'Part-time with unemployment rights and eligible to AGR'),
        ('with_unemployment_rights_no_agr', 'Part-time with unemployment rights but not eligible to AGR'),
        ('without_unemployment_rights', 'Part-time without unemployment rights')],
        string="Part-time",
        default='voluntary',
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_starterjob = fields.Boolean(string="Starterjob",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1,
        help="""Only new employees who qualify for the first job agreement and fulfill specific conditions.\n Contact your social secretariat for more information.""")
    l10n_be_scale_seniority = fields.Integer(string="Seniority at Hiring", groups="hr.group_hr_user", tracking=1, help="Number of years that will be taken into account for the accruals and the notice period")
    l10n_be_scale_seniority_months = fields.Integer(groups="hr.group_hr_user", tracking=1, help="Number of months that will be taken into account for the accruals and the notice period")
    l10n_be_salary_scale_id = fields.Many2one(
        "l10n_be.salary.scale", string="Salary Scale", groups="hr_payroll.group_hr_payroll_user",
        domain="[('l10n_be_joint_committee', '=', l10n_be_joint_committee_id), '|', ('employer_category_id', '=', False), ('employer_category_id', '=', l10n_be_employer_category_id)]")
    display_l10n_be_scale = fields.Boolean(compute='_compute_display_be', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_sale_representative = fields.Boolean(string="Sales Representative", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_apprenticeship_contract_number = fields.Char(string='Apprenticeship Contract Number', help="The reference of the apprentice contract.", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_apprenticeship_contract_type = fields.Selection([
        ('approved', 'Approved Apprentice (Middle Classes Training)'),
        ('business_manager', 'Business Manager Trainee'),
        ('industrial', 'Industrial Apprenticeship Agreement'),
        ('professional_immersion', 'Professional Immersion Agreement'),
        ('dual_learning', 'Dual Learning (Flemish Region/Brussels)'),
        ('work_study', 'Work-Study Contract (Walloon Region/Brussels)')],
        string='Apprenticeship Contract Type', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_apprenticeship_contract_subtype = fields.Selection([
        ('basic', 'Basic'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced/Special')],
        string='Apprenticeship Contract Subtype', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_homeworking_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Flat amount per month that is awarded to the employee for expenses related to homeworking office.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('cp200_representation_fees_homeworking', raise_if_not_found=False))
    l10n_be_lsa_office_fees_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Percentage of the gross earned while working from home to be gained by the employee as a benefit. Note that the percentage of the gross to be considered gained while working from home should be defined on the payslip.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_office_fees', raise_if_not_found=False))
    l10n_be_lsa_office_fees_2022_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Percentage of the gross earned while working from home to be gained by the employee as a benefit. This is only awarded if it was already being awarded before June 1st 2022. Note that the percentage of the gross to be considered gained while working from home should be defined on the payslip.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_office_fees_2022', raise_if_not_found=False))
    l10n_be_lsa_phone_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance for a phone plan.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_phone', raise_if_not_found=False))
    l10n_be_lsa_internet_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance for an internet contract.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_internet', raise_if_not_found=False))
    l10n_be_lsa_pc_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance to cover the cost of PC and software.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_pc', raise_if_not_found=False))
    l10n_be_lsa_second_screen_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="For second PC screen used for business purpose without private computer",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_second_screen', raise_if_not_found=False))
    l10n_be_lsa_scanner_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="For a scanner used for business purpose without private computer",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_scanner', raise_if_not_found=False))
    l10n_be_lsa_car_management_garage_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance related to the rental of a garage for a company car.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_car_management_garage', raise_if_not_found=False))
    l10n_be_lsa_car_management_parking_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance related to the payment of parking for a company car.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_car_management_parking', raise_if_not_found=False))
    l10n_be_lsa_car_management_wash_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance related to the washing of a company car.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_car_management_wash', raise_if_not_found=False))
    l10n_be_lsa_travel_cost_loc_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the Lack of Convenience for an itinerant employee. Note that this is the amount per day, in the payslip you will have to specify the amount of days for which this benefit is awarded via the 'Travel Cost (Lack of Convenience)' Salary Input.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_travel_cost_loc', raise_if_not_found=False))
    l10n_be_lsa_travel_cost_meal_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the meals for an itinerant employee. Note that this is the amount per day, in the payslip you will have to specify the amount of days for which this benefit is awarded via the 'Travel Cost (Meal)' Salary Input.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_travel_cost_meal', raise_if_not_found=False))
    l10n_be_lsa_travel_cost_living_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the dinner and overnight stay for an itinerant employee. Note that this is the amount per day, in the payslip you will have to specify the amount of days for which this benefit is awarded via the 'Travel Cost (Living)' Salary Input.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_travel_cost_living', raise_if_not_found=False))
    l10n_be_lsa_service_travel_abroad_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to service trips abroad. The legal minimum depends both on the country and on the duration of the rtravel (can be found here https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/salary/particularcases/expensesreimbursement.html#voyages%20de%20service%20%C3%A0%20l'etranger), so no default it set.")
    l10n_be_lsa_working_tools_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the fact that the employee has to use personal tools for the job.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_working_tools', raise_if_not_found=False))
    l10n_be_lsa_buying_work_clothes_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the fact that the employee has to buy specific clothes for the job.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_buying_work_clothes', raise_if_not_found=False))
    l10n_be_lsa_work_clothes_maintenance_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the fact that working clothes must be cleaned more frequently than usual.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_work_clothes_maintenance', raise_if_not_found=False))
    l10n_be_lsa_personal_work_clothes_maintenance_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance related to the fact that personal clothes used for working must be cleaned more frequently than usual.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_personal_work_clothes_maintenance', raise_if_not_found=False))
    l10n_be_lsa_car_travel_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user", digits=(6, 5),
       help="Per km allowance that covers the cost of commuting by car from home to office. Note that this is only the amount per km, in the payslip you will have to specify how many kms were actually travelled in the period.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_car_travel', raise_if_not_found=False))
    l10n_be_lsa_bike_travel_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user", digits=(6, 5),
       help="Per km allowance that covers the cost of commuting by bike from home to office. Note that this is only the amount per km, in the payslip you will have to specify how many kms were actually travelled in the period.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_bike_travel', raise_if_not_found=False))
    l10n_be_lsa_bike_professional_travel_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user", digits=(6, 5),
       help="Per km allowance that covers the cost of commuting by bike from and to clients. Note that this is only the amount per km, in the payslip you will have to specify how many kms were actually travelled in the period.",
       default=lambda self: self.env['hr.rule.parameter']._get_parameter_from_code('representation_fees_bike_professional_travel', raise_if_not_found=False))
    l10n_be_lsa_daily_misc_base_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance that will be included in the Lump Sum Allowances")
    l10n_be_lsa_monthly_misc_base_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance that will be included in the Lump Sum Allowances")
    l10n_be_lsa_daily_misc_other_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Daily allowance that will be included in the Lump Sum Allowances (With Other Criteria)")
    l10n_be_lsa_monthly_pro_base_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance that will be prorated based on worked days and included in the Lump Sum Allowances")
    l10n_be_lsa_monthly_pro_other_amount = fields.Float(groups="hr_payroll.group_hr_payroll_user",
       help="Monthly allowance that will be prorated based on worked days and included in the Lump Sum Allowances (With Other Criteria)")

    # departure
    l10n_be_first_contract_id = fields.Many2one(related='departure_id.l10n_be_first_contract_id',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_first_contract_date = fields.Date(related='departure_id.l10n_be_first_contract_date',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_reason_code = fields.Integer(related='departure_id.l10n_be_reason_code',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_seniority_description = fields.Char(related='departure_id.l10n_be_seniority_description',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_thirteen_month_eligible = fields.Boolean(related='departure_id.l10n_be_thirteen_month_eligible',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_salary_december_2013 = fields.Selection(related='departure_id.l10n_be_salary_december_2013',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_salary_visibility = fields.Boolean(related='departure_id.l10n_be_salary_visibility',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_notice_duration_month_before_2014 = fields.Integer(related='departure_id.l10n_be_notice_duration_month_before_2014',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_notice_duration_week_after_2014 = fields.Integer(related='departure_id.l10n_be_notice_duration_week_after_2014',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_notice_duration = fields.Integer(related='departure_id.l10n_be_notice_duration',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_notice_period_start = fields.Date(related='departure_id.l10n_be_notice_period_start',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_notice_period_theoretical_end = fields.Date(related='departure_id.l10n_be_notice_period_theoretical_end',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_notice_respect = fields.Selection(related='departure_id.l10n_be_notice_respect',
        groups='hr_payroll.group_hr_payroll_user', readonly=False)
    l10n_be_payslip_n_ids = fields.Many2many(related='departure_id.l10n_be_payslip_n_ids',
        readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_payslip_n_description = fields.Char(related='departure_id.l10n_be_payslip_n_description',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_payslip_n1_ids = fields.Many2many(related='departure_id.l10n_be_payslip_n1_ids',
        readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_payslip_n1_description = fields.Char(related='departure_id.l10n_be_payslip_n1_description',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_net_n = fields.Monetary(related='departure_id.l10n_be_net_n',
        readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_net_n1 = fields.Monetary(related='departure_id.l10n_be_net_n1',
        readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_fictitious_remuneration_n = fields.Monetary(related='departure_id.l10n_be_fictitious_remuneration_n',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_fictitious_remuneration_n1 = fields.Monetary(related='departure_id.l10n_be_fictitious_remuneration_n1',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_gross_reference_remuneration_n = fields.Monetary(related='departure_id.l10n_be_gross_reference_remuneration_n',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_gross_reference_remuneration_n1 = fields.Monetary(related='departure_id.l10n_be_gross_reference_remuneration_n1',
        groups='hr_payroll.group_hr_payroll_user')
    l10n_be_time_off_line_ids = fields.One2many(related='departure_id.l10n_be_time_off_line_ids',
        readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_allowed_dimona_categories = fields.Json(compute='_compute_l10n_be_allowed_dimona_categories', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_professional_reclassification = fields.Selection(related='departure_id.l10n_be_professional_reclassification',
        readonly=False, groups='hr_payroll.group_hr_payroll_user')
    niss = fields.Char(related='employee_id.niss', readonly=False, groups='hr_payroll.group_hr_payroll_user')

    def _is_flex_dimona_category_restricted(self):
        self.ensure_one()
        egov3_code = self.l10n_be_egov3_code
        company_NACE_code = self.payroll_config_id.l10n_be_nace_code_id.egov3_code
        flex_job_cp_codes_except = ['143', '144', '145.01', '145.02', '145.03', '145.05', '145.06', '145.07', '320', '323']

        health_NACE_list = ['86101', '86102', '86103', '86104', '86109',
                            '86210', '86901', '86903', '86905', '86906',
                            '86909', '87101', '87109', '87301', '87302']

        bakery_NACE_list = ['10711', '10712', '47241']

        artisanal_chocolate_NACE = '47242'
        if self.country_code == 'BE':
            if egov3_code not in flex_job_cp_codes_except:
                return False
            if egov3_code == '330' and company_NACE_code in health_NACE_list:
                return False
            if egov3_code in ['118', '118.14'] and company_NACE_code == artisanal_chocolate_NACE:
                return False
            if egov3_code in ['118', '118.03'] and company_NACE_code in bakery_NACE_list:
                return False
        return True

    def _is_artist(self):
        self.ensure_one()
        return self.l10n_be_worker_code_id.dmfa_code in ['046', '047'] or self.l10n_be_worker_status in ['A1', 'A2']

    @api.depends('l10n_be_egov3_code', 'payroll_config_id.l10n_be_nace_code_id.egov3_code')
    def _compute_l10n_be_allowed_dimona_categories(self):
        selection_options = self._fields['l10n_be_dimona_category']._description_selection(self.env)
        all_keys = [sel[0] for sel in selection_options]
        for version in self.filtered(lambda v: v.country_code != 'BE'):
            version.l10n_be_allowed_dimona_categories = []
        for version in self.filtered(lambda v: v.country_code == 'BE'):
            if version._is_flex_dimona_category_restricted():
                version.l10n_be_allowed_dimona_categories = [k for k in all_keys if k != 'flx']
            else:
                version.l10n_be_allowed_dimona_categories = all_keys

    @api.depends('company_id', 'l10n_be_joint_committee_id')
    def _compute_display_be(self):
        for version in self:
            version.display_l10n_be_scale = (
                version.company_id.country_id.code == "BE"
                and version.l10n_be_joint_committee_id
                and version.l10n_be_joint_committee_id.egov3_code in ["200", "302"]
                if version.company_id
                else False
            )

    spouse_fiscal_status = fields.Selection([
        ('high_income', 'With High Income'),
        ('low_income', 'With Low Income'),
        ('without_income', 'Without Income'),
        ('high_pension', 'With High Pensions'),
        ('low_pension', 'With Low Pensions')
    ], string='Tax status for spouse', groups="hr.group_hr_user", default='high_income', required=False, tracking=1)
    disabled_spouse_bool = fields.Boolean(string='Disabled Spouse', help='if recipient spouse is declared disabled by law', groups="hr.group_hr_user", tracking=1)
    disabled_children_number = fields.Integer('Number of disabled children', groups="hr.group_hr_user", tracking=1)
    dependent_children = fields.Integer(compute='_compute_dependent_children', string='Considered number of dependent children', groups="hr.group_hr_user")
    l10n_be_dependent_children_attachment = fields.Integer(
        string="Dependent children", groups="hr.group_hr_user", tracking=1,
        help="""To benefit from this increase in the elusive or non-transferable quotas, the worker whose remuneration is subject to seizure or transfer, must declare it using a form, the model of which has been published in the Belgian Official Gazette. of 30 November 2006.

He must attach to this form the documents establishing the reality of the charge invoked.

Source: Opinion on the indexation of the amounts set in Article 1, paragraph 4, of the Royal Decree of 27 December 2004 implementing Articles 1409, § 1, paragraph 4, and 1409, § 1 bis, paragraph 4 , of the Judicial Code relating to the limitation of seizure when there are dependent children, MB, December 13, 2019.""")
    other_juniors_dependent = fields.Integer('Adult Dependent People', groups="hr.group_hr_user", tracking=1)
    other_dependents = fields.Integer('Dependent People', groups="hr.group_hr_user", tracking=1)
    other_disabled_juniors_dependent = fields.Integer('# disabled people', groups="hr.group_hr_user", tracking=1)
    other_senior_dependent = fields.Integer(string="Considered number of dependent seniors", help="Parent, grandparent, great-grandparent, brother and sister aged 66 or over , who are financially dependent on you and for whom a reduced autonomy of at least 9 points has been established.", groups="hr.group_hr_user")
    dependent_juniors = fields.Integer(compute='_compute_dependent_people', string="Considered number of dependent juniors", groups="hr.group_hr_user")
    l10n_be_withholding_tax_type = fields.Selection([('percentage', "%"), ('fixed', "€ / Month")], default='fixed', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_withholding_tax_amount = fields.Float(string="Withholding Tax", default=0.0, tracking=1, help="For company executive that want to have a fixed amount of withholding taxes every month.", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_withholding_tax_percentage = fields.Float(default=0.0, tracking=1, groups="hr_payroll.group_hr_payroll_user")
    fiscal_voluntarism_type = fields.Selection([('percentage', "%"), ('fixed', "€ extra/Month"), ('total_amount', "€ in total/month")], default='fixed', groups="hr_payroll.group_hr_payroll_user")
    fiscal_voluntarism_amount = fields.Float(
        string="Fiscal Voluntarism",
        default=0.0,
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user",
        help="Extra withholding taxes paid by the employee that can be defined:\n"
            "  • as extra rate (%) of the computed withholding tax\n"
            "  • as an additional amount per month (\"€ extra/month\")\n"
            "  • as a total amount (\"€ in total /month\") to pay each month if less was computed."
    )
    fiscal_voluntarism_percentage = fields.Float(default=0.0, tracking=1, groups="hr_payroll.group_hr_payroll_user")
    # Transport
    transport_mode_car = fields.Boolean('Uses company car', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    car_id = fields.Many2one(
        'fleet.vehicle', string='Company Car',
        tracking=1, compute="_compute_car_id", store=True, index='btree_not_null', readonly=False,
        domain=lambda self: [('company_id', 'in', (False, self.env.company.id)), ('vehicle_type', '=', 'car')],
        groups='fleet.fleet_group_manager,hr.group_hr_user,hr_payroll.group_hr_payroll_user')
    car_atn = fields.Monetary(
        string='Car BIK', help='Benefit in Kind (Company Car)', tracking=1,
        compute='_compute_car_atn_and_costs', store=True, compute_sudo=True, groups="hr_payroll.group_hr_payroll_user",
    )
    temporary_car_total_depreciated_cost = fields.Float(
        compute='_compute_car_atn_and_costs', store=True, compute_sudo=True, groups="hr_payroll.group_hr_payroll_user"
    )
    available_cars_amount = fields.Integer(
        compute='_compute_available_cars_amount', string='Number of available cars', groups="hr.group_hr_user", compute_sudo=True
    )
    has_new_car = fields.Boolean('Requested a new car', groups="hr.group_hr_user", tracking=1)
    new_car_model_id = fields.Many2one(
        'fleet.vehicle.model', string="New Company Car", domain=lambda self: self._get_possible_model_domain(),
        groups='hr.group_hr_user', tracking=1)
    # Useful on sign to use only one box to sign the contract instead of 2
    car_model_name = fields.Char(compute='_compute_car_model_name', compute_sudo=True,
                                 groups='hr.group_hr_user')
    acquisition_date = fields.Date(related='car_id.acquisition_date', readonly=False, groups="fleet.fleet_group_manager")
    car_value = fields.Float(related="car_id.car_value", readonly=False, groups="fleet.fleet_group_manager")
    fuel_type = fields.Selection(selection=lambda self: self.env['fleet.vehicle']._fields['fuel_type']._description_selection(self.env), compute="_compute_fuel_type", readonly=False, groups="fleet.fleet_group_manager")
    co2 = fields.Float(related="car_id.co2", readonly=False, groups="fleet.fleet_group_manager")
    driver_id = fields.Many2one('res.partner', related="car_id.driver_id", readonly=False, groups="fleet.fleet_group_manager")
    car_open_contracts_count = fields.Integer(compute='_compute_car_open_contracts_count', groups="fleet.fleet_group_manager")
    recurring_cost_amount_depreciated = fields.Float(
        groups="fleet.fleet_group_manager",
        compute='_compute_recurring_cost_amount_depreciated',
        inverse="_inverse_recurring_cost_amount_depreciated", tracking=1)
    transport_mode_bike = fields.Boolean('Uses Bike', groups='hr.group_hr_user', tracking=1)
    bike_id = fields.Many2one(
        'fleet.vehicle', string="Company Bike",
        tracking=1,
        compute='_compute_bike_id', store=True, readonly=False, index='btree_not_null',
        domain=lambda self: [('company_id', 'in', (False, self.env.company.id)), ('vehicle_type', '=', 'bike')],
        groups='fleet.fleet_group_manager')
    company_bike_depreciated_cost = fields.Float(
        compute='_compute_company_bike_depreciated_cost', store=True, compute_sudo=True,
        groups='hr.group_hr_user')
    new_bike = fields.Boolean(
        'Requested a new bike', compute='_compute_new_bike', store=True, readonly=False,
        groups='hr.group_hr_user')
    new_bike_model_id = fields.Many2one(
        'fleet.vehicle.model', string="New Bike",
        domain=lambda self: self._get_possible_model_domain(vehicle_type='bike'), index='btree_not_null',
        compute='_compute_new_bike_model_id', store=True, readonly=False, groups='hr.group_hr_user')
    train_transport_employee_kilometer = fields.Integer(
        'Train Ride', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    train_transport_periodicity = fields.Selection([
        ('yearly', 'Yearly'),
        ('monthly', 'Monthly'),
        ('railflex', 'Railflex')
    ], default='monthly', string="Train Subscription")
    bus_transport_employee_amount = fields.Monetary(
        'Bus cost', groups="hr_payroll.group_hr_payroll_user", tracking=1, help="Use \"Fixed price\" when the cost does not depend of the distance. Contact your social secretariat for more details.")
    bus_transport_employee_kilometer = fields.Integer(
        'Bus Ride', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    bus_transport_periodicity = fields.Selection([
        ('yearly', 'Yearly'),
        ('monthly', 'Monthly'),
        ('fixed', 'Fixed Price'),
    ], default='monthly')
    tram_transport_employee_amount = fields.Monetary(
        'Tram cost', groups="hr_payroll.group_hr_payroll_user", tracking=1, help="Use \"Fixed price\" when the cost does not depend of the distance. Contact your social secretariat for more details.")
    tram_transport_employee_kilometer = fields.Integer(
        'Tram Ride', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    tram_transport_periodicity = fields.Selection([
        ('yearly', 'Yearly'),
        ('monthly', 'Monthly'),
        ('fixed', 'Fixed Price'),
    ], default='monthly')
    metro_transport_employee_amount = fields.Monetary(
        'Metro cost', groups="hr_payroll.group_hr_payroll_user", tracking=1, help="Use \"Fixed price\" when the cost does not depend of the distance. Contact your social secretariat for more details.")
    metro_transport_employee_kilometer = fields.Integer(
        'Metro Ride', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    metro_transport_periodicity = fields.Selection([
        ('yearly', 'Yearly'),
        ('monthly', 'Monthly'),
        ('fixed', 'Fixed Price'),
    ], default='monthly')
    bike_transport_employee_kilometer = fields.Float(
        'Bike Ride', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    private_car_employee_kilometer = fields.Integer(
        'Private Car Ride', groups="hr_payroll.group_hr_payroll_user", tracking=1)

    warrant_value_employee = fields.Monetary(
        compute='_compute_commission_cost', string="Warrant monthly value for the employee", groups="hr_payroll.group_hr_payroll_user")

    meal_voucher_paid_by_employer = fields.Monetary(
        compute='_compute_meal_voucher_info', string="Meal Voucher Paid by Employer", groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_paid_monthly_by_employer = fields.Monetary(
        compute='_compute_meal_voucher_info', groups="hr_payroll.group_hr_payroll_user")

    def _get_default_employee_share(self):
        if self.env.company.country_id.code == 'BE':
            return self.env['hr.rule.parameter']._get_parameter_from_code('min_meal_voucher_employee_share', raise_if_not_found=False) or 1.09
        return 0.0

    meal_voucher_employee_share = fields.Monetary(string="MV Employee's Share", groups="hr_payroll.group_hr_payroll_user", help="Indicates how much employee will pay for meal voucher", default=_get_default_employee_share)
    is_meal_voucher_valid = fields.Boolean(default=True, compute="_compute_is_meal_voucher_valid", store=True, groups="hr_payroll.group_hr_payroll_user")
    company_car_total_depreciated_cost = fields.Monetary(
        compute='_compute_car_atn_and_costs', store=True, compute_sudo=True,
        groups="hr_payroll.group_hr_payroll_user", tracking=1
    )
    warrants_cost = fields.Monetary(
        compute='_compute_commission_cost', string="Warrant monthly cost for the employer", groups="hr_payroll.group_hr_payroll_user")
    yearly_commission = fields.Monetary(compute='_compute_commission_cost', groups="hr_payroll.group_hr_payroll_user")
    yearly_commission_cost = fields.Monetary(compute='_compute_commission_cost', groups="hr_payroll.group_hr_payroll_user")

    # Advantages
    commission_on_target = fields.Monetary(
        string="Commission",
        tracking=1,
        help="Monthly gross amount that the employee receives if the target is reached.",
        groups="hr_payroll.group_hr_payroll_user")
    fuel_card = fields.Monetary(
        string="Fuel Card",
        tracking=1,
        help="Monthly amount the employee receives on his fuel card.",
        groups="hr_payroll.group_hr_payroll_user")
    fuel_card_personal_use = fields.Monetary(
        string="Fuel Card - Personal use",
        tracking=1,
        help="part of the Fuel card budget dedicated to the personal use of the employee",
        groups="hr_payroll.group_hr_payroll_user")
    internet = fields.Monetary(
        string="Internet Subscription",
        tracking=1,
        help="The employee's internet subscription will be paid up to this amount.",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_monthly_misc_other_amount = fields.Monetary(
        string="Expense Fees",
        tracking=True,
        help="Monthly allowance that will be included in the Lump Sum Allowances (With Other Criteria)",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_child_bonus = fields.Monetary(
        string="Child Bonus",
        tracking=True,
        help="The monthly additional child bonus amount for this employee (Should not exceed 50€ per child)",
        groups="hr_payroll.group_hr_payroll_user")
    mobile = fields.Monetary(
        string="Mobile Subscription",
        tracking=1,
        help="The employee's mobile subscription will be paid up to this amount.",
        groups="hr_payroll.group_hr_payroll_user")
    mobile_amount = fields.Monetary(
        string="Mobile Phone",
        tracking=1,
        help="Cost ot a mobile phone provided by the employer.",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_sectorial_bonus_compensatory_amount = fields.Monetary(
        string="Sectoral Bonus Compensation",
        tracking=True,
        help="In case you compensated fully or partially the annual sectoral bonus with an equivalent benefit, fill in the value of the compensation here.",
        groups="hr_payroll.group_hr_payroll_user")
    has_laptop = fields.Boolean(
        string="Has Laptop",
        tracking=True,
        help="A benefit in kind is paid when the employee uses its laptop at home.",
        groups="hr_payroll.group_hr_payroll_user")
    laptop = fields.Monetary(
        string="Laptop",
        tracking=1,
        help="Cost ot a laptop provided by the employer.",
        groups="hr_payroll.group_hr_payroll_user")
    tablet = fields.Monetary(
        string="Tablet",
        tracking=1,
        help="Cost ot a tablet provided by the employer.",
        groups="hr_payroll.group_hr_payroll_user")
    electricity_amount = fields.Monetary(
        string="Electricity",
        tracking=1,
        help="Monthly amount the employee receives to cover his electricity costs at home.",
        groups="hr_payroll.group_hr_payroll_user")
    heating_amount = fields.Monetary(
        string="Heating",
        tracking=1,
        help="Monthly amount the employee receives to cover his heating costs at home.",
        groups="hr_payroll.group_hr_payroll_user"
    )
    housing_onss_amount = fields.Monetary(
        string="Housing (ONSS)",
        tracking=1,
        help="Monthly amount the employee receives to cover his housing costs, valued for the social contributions.",
        groups="hr_payroll.group_hr_payroll_user"
    )
    housing_fiscal_amount = fields.Monetary(
        string="Housing (Fiscal)",
        tracking=1,
        help="Monthly amount the employee receives to cover his housing costs, valued for the withholding taxes.",
        groups="hr_payroll.group_hr_payroll_user"
    )
    rent_amount = fields.Monetary(
        string="Reclassified Rents",
        tracking=1,
        help="Monthly amount the employee receives for reclassified rents.",
        groups="hr_payroll.group_hr_payroll_user"
    )
    pension_amount = fields.Monetary(
        string="Supplementary Pension",
        tracking=1,
        help="Monthly amount the employee receives for a self-employed supplementary pension.",
        groups="hr_payroll.group_hr_payroll_user"
    )
    has_bicycle = fields.Boolean(string="Bicycle to work", default=False, groups="hr.group_hr_user",
        help="Use a bicycle as a transport mode to go to work", tracking=1)
    meal_voucher_amount = fields.Monetary(
        string="Meal Vouchers",
        tracking=1,
        help="Amount the employee receives in the form of meal vouchers. "
             "It can either be per worked day, regardless of hours worked in a specific day. "
             "Or it can be prorated, then it's the amount of hours worked in the month divided by the average hours expected.",
        groups="hr_payroll.group_hr_payroll_user",
    )
    meal_voucher_calculation_method = fields.Selection(
        selection=[
            ('days', '/ worked day'),
            ('hours', '/ prorated'),
        ],
        string="Calculation Method",
        default='days',
        required=True,
        tracking=1,
        groups="hr_payroll.group_hr_payroll_user",
    )
    fixed_meal_voucher_days = fields.Integer(
        string="Fixed Meal Vouchers",
        tracking=1,
        help="For company executive that wants to have a fixed number of worked days to consider in the meal vouchers amount computation.",
        groups="hr_payroll.group_hr_payroll_user",
    )
    meal_voucher_average_monthly_amount = fields.Monetary(
        compute="_compute_meal_voucher_info", groups="hr_payroll.group_hr_payroll_user")
    eco_checks = fields.Monetary(
        "Eco Vouchers", groups="hr_payroll.group_hr_payroll_user", compute='_compute_eco_checks',
        help="Yearly amount the employee receives in the form of eco vouchers.")
    ip_wage_rate = fields.Float(string="IP percentage", help="Should be between 0 and 100 %", groups="hr_payroll.group_hr_payroll_user", tracking=1, digits="Payroll Rate")
    ip_value = fields.Float(compute='_compute_ip_value', groups="hr_payroll.group_hr_payroll_user")
    ip_artist = fields.Boolean(
        string="IP Artist", groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Owner of a certification of artistic work of the “plus” or ordinary type")
    ip_onss = fields.Boolean(
        string="IP ONSS", default=True, groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Forces the calculation of social security contributions")
    no_onss = fields.Boolean(string="No ONSS", groups="hr_payroll.group_hr_payroll_user", compute="_compute_no_onss", readonly=True)
    no_withholding_taxes = fields.Boolean(compute='_compute_no_withholding_taxes', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_resident_situation = fields.Selection([
        ('resident', 'Resident'),
        ('non_resident', 'Non-Resident'),
        ('cross_border', 'Cross-border worker')
    ], string='Resident Situation', default='resident', tracking=1, required=True, groups="hr_payroll.group_hr_payroll_user")
    is_non_resident = fields.Boolean(compute='_compute_is_non_resident', inverse='_inverse_is_non_resident', store=True)
    work_in_belgium_over_75 = fields.Boolean(string="Works in Belgium >= 75%", groups="hr_payroll.group_hr_payroll_user", default=True, tracking=1)
    rd_percentage = fields.Float("Time in R&D", groups="hr_payroll.group_hr_payroll_user", tracking=1, digits="Payroll Rate")
    l10n_be_is_aid_zone = fields.Boolean(
        string="Aid Zone",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1,
        help="The employee fills a position created in an aid zone and meets specific conditions. Contact your social secretariat for more information.",
    )
    l10n_be_impulsion_plan = fields.Selection([
        ('25yo', '< 25 years old'),
        ('12mo', '12 months +')], string="Impulsion Plan", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_worker_status = fields.Selection(
        string="Specific Status", selection='_get_l10n_be_worker_status', groups="hr_payroll.group_hr_payroll_user"
    )
    available_l10n_be_worker_status = fields.Json(compute='_compute_available_l10n_be_worker_status', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_risk_class = fields.Selection(
            string="Risk Class",
            selection=[
                ("001", "[001] Workers without travel"),
                ("002", "[002] Construction workers"),
                ("003", "[003] Concierges"),
                ("004", "[004] Cleaning and maintenance personnel"),
                ("005", "[005] Kitchen staff"),
                ("006", "[006] Drivers"),
                ("401", "[401] Non-Traveling Employees"),
                ("402", "[402] Employees with occasional external assignments"),
                ("403", "[403] Employees with frequent external assignments"),
                ("404", "[404] Sales representatives or traveling employees, couriers"),
                ("405", "[405] Employees with manual work and/or foremen"),
                ("406", "[406] Home-based employees"),
                ("407", "[407] Healthcare personnel"),
                ("408", "[408] Salesperson / Saleswoman"),
                ("409", "[409] Football players subject to the status of paid athletes"),
                ("410", "[410] Football players not subject to the status of paid athletes with a fixed annual salary of EUR 1,239.47 or more"),
                ("411", "[411] Football players not subject to the status of paid athletes with a fixed annual salary of less than EUR 1,239.47"),
                ("412", "[412] Sportsmen other than football players"),
            ],
            groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_be_is_retired = fields.Boolean(string="Retired", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_retirement_date = fields.Date(compute='_compute_retirement_date', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_contribute_to_fse = fields.Boolean(string="Allowed to Contribute (FSE)", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_early_retirement_status = fields.Boolean(
        string="Early Retirement Status",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1,
        help="The employee has a career of less than 45 years or has not reached the legal age for retirement")
    has_hospital_insurance = fields.Boolean(string="Hospital Insurance", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    insured_relative_children = fields.Integer(string="# Insured Children < 19 y/o", compute='_compute_hospital_insurance_fields', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=1)
    insured_relative_adults = fields.Integer(string="# Insured Children >= 19 y/o", compute='_compute_hospital_insurance_fields', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=1)
    insured_relative_spouse = fields.Boolean(string="Insured Spouse", compute='_compute_hospital_insurance_fields', store=True, readonly=False, groups="hr_payroll.group_hr_payroll_user", tracking=1)
    hospital_insurance_amount_per_child = fields.Float(string="Amount per Child", groups="hr_payroll.group_hr_payroll_user",
        default=lambda self: self.env.company.current_payroll_config_id.hospital_insurance_amount_child, tracking=1)
    hospital_insurance_amount_per_adult = fields.Float(string="Amount per Adult", groups="hr_payroll.group_hr_payroll_user",
        default=lambda self: self.env.company.current_payroll_config_id.hospital_insurance_amount_adult, tracking=1)
    hospital_insurance_employee_contribution = fields.Float(string="Hospital Insurance Contribution by Employee",
        groups="hr_payroll.group_hr_payroll_user",
        default=lambda self: self.env.company.current_payroll_config_id.hospital_insurance_employee_contribution,
        compute='_compute_hospital_insurance_fields',
        store=True,
        readonly=False,
        tracking=1)
    insurance_amount = fields.Float(compute='_compute_insurance_amount', string="Insurance Amount", groups="hr_payroll.group_hr_payroll_user")
    insured_relative_adults_total = fields.Integer(compute='_compute_insured_relative_adults_total', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_hospital_insurance_notes = fields.Text(
        string="Hospital Insurance: Additional Info", groups="hr_payroll.group_hr_payroll_user", tracking=1)

    # Group Insurance
    l10n_be_has_group_insurance = fields.Boolean(
        string="Group Insurance",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1,
    )
    l10n_be_group_insurance_rate = fields.Float(
        string="Group Insurance Sacrifice Rate", tracking=1,
        help="Should be between 0 and 100 %", groups="hr_payroll.group_hr_payroll_user", digits="Payroll Rate")
    l10n_be_group_insurance_amount = fields.Monetary(
        compute='_compute_l10n_be_group_insurance_amount', store=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_cost = fields.Monetary(
        compute='_compute_l10n_be_group_insurance_amount', store=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_company_contribution = fields.Float(
        string="Group Insurance Company Contribution", tracking=1, compute='_compute_group_insurance_fields', store=True, readonly=False,
        help="Company contribution for group insurance", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_company_contribution_unit = fields.Selection([
        ('percentage', '%'),
        ('amount', '€'),
    ], compute='_compute_group_insurance_fields', store=True, readonly=False, string="Company Contribution Unit", default='percentage', tracking=1, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_employee_contribution = fields.Float(
        string="Group Insurance Employee Contribution", tracking=1, compute='_compute_group_insurance_fields', store=True, readonly=False,
        help="Employee contribution for group insurance", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_employee_contribution_unit = fields.Selection([
        ('percentage', '%'),
        ('amount', '€'),
    ], compute='_compute_group_insurance_fields', store=True, readonly=False, string="Employee Contribution Unit", default='percentage', tracking=1, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_employee_voluntary = fields.Monetary(
        string="Group Insurance Employee Voluntary Amount", tracking=1, compute='_compute_group_insurance_fields', store=True, readonly=False,
        help="Employee voluntary amount for group insurance", groups="hr_payroll.group_hr_payroll_user")
    # Ambulatory Insurance
    l10n_be_ambulatory_insurance_employee_contribution = fields.Float(
        string="Ambulatory Insurance Contribution by Employee",
        default=lambda self: self.env.company.current_payroll_config_id.ambulatory_insurance_employee_contribution,
        groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_has_ambulatory_insurance = fields.Boolean(
        string="Ambulatory Insurance",
        groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_ambulatory_insured_children = fields.Integer(
        string="Ambulatory: # Insured Children < 19 y/o",
        compute='_compute_ambulatory_insurance_fields', store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_ambulatory_insured_adults = fields.Integer(
        string="Ambulatory: # Insured Children >= 19 y/o",
        compute='_compute_ambulatory_insurance_fields', store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_ambulatory_insured_spouse = fields.Boolean(
        string="Ambulatory: Insured Spouse",
        compute='_compute_ambulatory_insurance_fields', store=True, readonly=False,
        groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_ambulatory_amount_per_child = fields.Float(
        string="Ambulatory: Amount per Child", groups="hr_payroll.group_hr_payroll_user",
        default=lambda self: self.env.company.current_payroll_config_id.ambulatory_insurance_amount_child, tracking=1)
    l10n_be_ambulatory_amount_per_adult = fields.Float(
        string="Ambulatory: Amount per Adult", groups="hr_payroll.group_hr_payroll_user",
        default=lambda self: self.env.company.current_payroll_config_id.ambulatory_insurance_amount_adult, tracking=1)
    l10n_be_ambulatory_insurance_amount = fields.Float(
        compute='_compute_ambulatory_insurance_amount', string="Ambulatory: Insurance Amount",
        groups="hr_payroll.group_hr_payroll_user", compute_sudo=True)
    l10n_be_ambulatory_insured_adults_total = fields.Integer(
        compute='_compute_ambulatory_insured_adults_total',
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insurance_notes = fields.Text(
        string="Ambulatory Insurance: Additional Info", groups="hr_payroll.group_hr_payroll_user", tracking=1)

    l10n_be_mobility_budget = fields.Boolean(string="Mobility Budget", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_mobility_budget_amount = fields.Monetary(
        string="Mobility Budget Amount",
        compute="_compute_l10n_be_mobility_budget_amount",
        store=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1
    )
    l10n_be_mobility_budget_amount_monthly = fields.Monetary(
        string="Mobility Budget Monthly Amount",
        compute="_compute_l10n_be_mobility_budget_amount_monthly",
        groups="hr_payroll.group_hr_payroll_user"
    )
    l10n_be_canteen_cost = fields.Monetary(string="Canteen Cost", groups="hr_payroll.group_hr_payroll_user",
                                           tracking=True)
    l10n_be_time_credit = fields.Boolean(
        string="Credit time",
        compute='_compute_l10n_be_time_credit',
        groups="hr.group_hr_user",
        tracking=1,
        )

    l10n_be_dimona_planned_hours = fields.Integer("Student Planned Hours", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_be_dimona_planned_start_time = fields.Float(groups="hr_payroll.group_hr_payroll_user", default=0.0, tracking=1)
    l10n_be_dimona_planned_end_time = fields.Float(groups="hr_payroll.group_hr_payroll_user", default=8.0, tracking=1)
    l10n_be_flexi_hourly_wage = fields.Monetary('Flexi Hourly Wage', tracking=1, help="Employee's hourly gross wage.", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_flexi_monthly_wage = fields.Monetary('Flexi Monthly Wage', tracking=1, help="Employee's monthly gross wage.", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_refused_flexijob = fields.Boolean(string="Refused Flexi-job", default=False, groups="hr_payroll.group_hr_payroll_user", tracking=1, help="Flag to identify if a flexi-job dimona declaration has been refused by the ONSS with anomaly 460 or 510.")

    l10n_be_dimona_declaration_id = fields.Many2one('l10n.be.dimona.declaration', string="Dimona In Declaration", groups="hr_payroll.group_hr_payroll_user", index='btree_not_null', tracking=1)
    l10n_be_last_dimona_declaration_id = fields.Many2one('l10n.be.dimona.declaration', string="Last Dimona Declaration", groups="hr_payroll.group_hr_payroll_user", tracking=1)

    l10n_be_needs_dimona_in = fields.Boolean(compute="_compute_l10n_be_needs_dimona_in", store=True)
    l10n_be_needs_dimona_update = fields.Boolean()
    l10n_be_needs_dimona_out = fields.Boolean()
    l10n_be_needs_dimona_cancel = fields.Boolean()
    l10n_be_dimona_next_action = fields.Selection(
        selection=[
            ('in', 'Dimona In To Do'),
            ('progress', 'In Progress'),
            ('done', 'Dimona Done'),
            ('issue', 'Dimona Issue'),
            ('update', 'Dimona Update to Do'),
            ('out', 'Dimona Out To Do'),
            ('cancel', 'Dimona Cancel To Do'),
        ],
        string="Dimona",
        compute='_compute_l10n_be_dimona_next_action',
        inverse='_inverse_l10n_be_dimona_next_action',
        store=True,
        tracking=1)
    l10n_be_dimona_category = fields.Selection(
        selection='_get_l10n_be_dimona_category_selection',
        compute='_compute_l10n_be_dimona_category',
        store=True,
        readonly=False,
        string='DIMONA Category',
        help='Used as the worker type for DIMONA declaration to the ONSS. You can define this value directly on employee types to save time and avoid mistakes.',
        groups="hr_payroll.group_hr_payroll_user"
    )
    l10n_be_needs_flxwage_declaration = fields.Boolean(compute="_compute_needs_flxwage_declaration", string="Needs Flxwage Declaration", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_company_onss_certificate_id = fields.Many2one(related="company_id.onss_certificate_id", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_city_nis_code = fields.Char('City NIS Code', related="private_city_id.l10n_be_nis_code", help="Belgian National Institute of Statistics city code of the private address")
    l10n_be_country_nis_code = fields.Char('Country NIS Code', related="private_country_id.l10n_be_nis_code", help="Belgian National Institute of Statistics country code of the private address")
    l10n_be_in_position_years = fields.Integer(compute='_compute_l10n_be_in_position_seniority', help='Time worked at the current occupation')
    l10n_be_in_position_months = fields.Integer(compute='_compute_l10n_be_in_position_seniority')
    l10n_be_base_computed_seniority = fields.Integer()
    l10n_be_computed_seniority_years = fields.Integer(compute='_compute_l10n_be_computed_seniority', help='Seniority taken into account for the Pay Scale')
    l10n_be_computed_seniority_months = fields.Integer(compute='_compute_l10n_be_computed_seniority')
    private_car_reimbursed_amount = fields.Monetary(
        compute='_compute_private_car_reimbursed_amount', groups="hr_payroll.group_hr_payroll_user")
    train_transport_reimbursed_amount = fields.Monetary(
        string='Train Transport Reimbursed amount', groups="hr_payroll.group_hr_payroll_user",
        compute='_compute_train_transport_reimbursed_amount')
    bus_transport_reimbursed_amount = fields.Monetary(
        string='Public Transport (Bus) Reimbursed amount', groups="hr_payroll.group_hr_payroll_user",
        compute='_compute_bus_transport_reimbursed_amount')
    tram_transport_reimbursed_amount = fields.Monetary(
        string='Public Transport (Tram) Reimbursed amount', groups="hr_payroll.group_hr_payroll_user",
        compute='_compute_tram_transport_reimbursed_amount')
    metro_transport_reimbursed_amount = fields.Monetary(
        string='Public Transport (Metro) Reimbursed amount', groups="hr_payroll.group_hr_payroll_user",
        compute='_compute_metro_transport_reimbursed_amount')
    bike_reimbursed_amount = fields.Monetary(
        string='Bike Reimbursed amount', groups="hr_payroll.group_hr_payroll_user",
        compute='_compute_bike_transport_reimbursed_amount')
    l10n_be_location_unit = fields.Many2one(
        'hr.work.location', string="Location unit", compute="_compute_l10n_be_location_unit",
        store=True, groups="hr_payroll.group_hr_payroll_user", tracking=1, index='btree_not_null')
    l10n_be_working_region = fields.Selection(
        related='l10n_be_location_unit.competence', string="Working region", readonly=True,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_onss_reduction_unexperienced_employees_flander = fields.Boolean(
        string="ONSS Reduction for Unexperienced Employees",
        groups="hr_payroll.group_hr_payroll_user",
        help="Only for employee working in Flanders and registered on Ecaro by the VDAB. Consult your social secretariat for more informations.",
        tracking=1,
    )
    l10n_be_include_employee_in_281_30 = fields.Boolean(
        string="Include Employee in 281.30 Report",
        groups="hr_payroll.group_hr_payroll_user",
        help="Include this employee in the 281.30 report rather than 281.10 and 281.20 reports.",
        tracking=1,
    )
    l10n_be_capped_amount = fields.Monetary(string="Capped Amount", default=False, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_cafeteria_plan_salary_sacrifice = fields.Monetary(
        string="Salary Sacrifice",
        groups="hr_payroll.group_hr_payroll_user",
        help="Amount gross converted into benefits in a cafeteria plan",
        tracking=1,
    )
    l10n_be_cafeteria_plan_net_contribution = fields.Monetary(
        string="Net Contribution",
        groups="hr_payroll.group_hr_payroll_user",
        help="Net contribution for benefits cost",
        tracking=1,
    )

    _check_percentage_ip_rate = models.Constraint(
        'CHECK(ip_wage_rate >= 0 AND ip_wage_rate <= 1.0)',
        "The IP rate on wage should be between 0 and 100 %.",
    )
    _check_percentage_group_insurance_rate = models.Constraint(
        'CHECK(l10n_be_group_insurance_rate >= 0 AND l10n_be_group_insurance_rate <= 1.0)',
        "The group insurance salary sacrifice rate on wage should be between 0 and 100 %.",
    )
    _check_percentage_group_insurance_company_contribution = models.Constraint(
        "CHECK(l10n_be_group_insurance_company_contribution_unit != 'percentage' OR (l10n_be_group_insurance_company_contribution >= 0 AND l10n_be_group_insurance_company_contribution <= 1.0))",
        "The group insurance company contribution should be between 0 and 100 %.",
    )
    _check_percentage_group_insurance_employee_contribution = models.Constraint(
        "CHECK(l10n_be_group_insurance_employee_contribution_unit != 'percentage' OR (l10n_be_group_insurance_employee_contribution >= 0 AND l10n_be_group_insurance_employee_contribution <= 1.0))",
        "The group insurance employee contribution should be between 0 and 100 %.",
    )
    _check_l10n_be_withholding_tax_amount = models.Constraint(
        "CHECK(l10n_be_withholding_tax_amount >= 0)",
        'The withholding tax amount should be greater or equal than 0.'
    )
    _check_l10n_be_withholding_tax_percentage = models.Constraint(
        "CHECK(l10n_be_withholding_tax_percentage >= 0 AND l10n_be_withholding_tax_percentage <= 1.0)",
        'The withholding tax percentage should be between 0-100.'
    )
    _check_fiscal_voluntarism_amount = models.Constraint(
        "CHECK(fiscal_voluntarism_amount >= 0)",
        'The fiscal voluntarism amount should be greater or equal than 0.'
    )
    _check_fiscal_voluntarism_percentage = models.Constraint(
        "CHECK(fiscal_voluntarism_percentage >= 0 AND fiscal_voluntarism_percentage <= 1.0)",
        'The fiscal voluntarism percentage should be between 0-100.'
    )

    @api.constrains('children', 'disabled_children_number',
                    'other_senior_dependent', 'other_dependents', 'other_juniors_dependent',
                    'other_disabled_juniors_dependent', 'l10n_be_dependent_children_attachment')
    def _check_dependent(self):
        for version in self:
            validation_error_message = []
            negative_fields = {
                self.env._('Children'): version.children,
                self.env._('Disabled Children'): version.disabled_children_number,
                self.env._('Dependent Seniors'): version.other_senior_dependent,
                self.env._('Other Dependents'): version.other_dependents,
                self.env._('Other Dependents'): version.other_juniors_dependent,
                self.env._('Other Disabled Dependents'): version.other_disabled_juniors_dependent,
                self.env._('Dependent Children Attachment'): version.l10n_be_dependent_children_attachment,
            }
            negative = [name for name, val in negative_fields.items() if val < 0]
            if negative:
                validation_error_message.append(
                    self.env._("- The following fields cannot be negative: %s.\n", ', '.join(negative))
                )

            if version.disabled_children_number > version.children:
                validation_error_message.append(
                    self.env._(
                        "- Disabled Children (%(disabled_children)s) cannot exceed total Children (%(children)s).\n",
                        disabled_children=version.disabled_children_number, children=version.children
                    )
                )

            if version.other_disabled_juniors_dependent > version.other_juniors_dependent:
                validation_error_message.append(
                    self.env._(
                        "- Other Disabled Dependents (%(disabled_juniors)s) cannot exceed "
                        "Other Dependents (%(juniors_dependent)s).\n",
                        disabled_juniors=version.other_disabled_juniors_dependent,
                        juniors_dependent=version.other_juniors_dependent
                    )
                )

            if version.other_dependents > 0 and version.other_juniors_dependent > version.other_dependents:
                validation_error_message.append(
                    self.env._(
                        "- Other Dependents (%(juniors_dependent)s) cannot exceed "
                        "total Other Dependents (%(other_dependents)s).\n",
                        juniors_dependent=version.other_juniors_dependent, other_dependents=version.other_dependents
                    )
                )

            if version.other_dependents > 0:
                dependent_sum = (
                    (version.other_juniors_dependent or 0) +
                    (version.other_senior_dependent or 0) +
                    (version.children or 0)
                )
                if dependent_sum != version.other_dependents:
                    validation_error_message.append(
                        self.env._(
                            "- Total Dependents (%(total_dependents)s) must equal the sum of "
                            "Children (%(children)s), Other Dependents (%(other_dependents)s) and "
                            "Dependent Seniors (%(senior_dependents)s).\n",
                            total_dependents=version.other_dependents,
                            children=version.children,
                            other_dependents=version.other_juniors_dependent,
                            senior_dependents=version.other_senior_dependent,
                        )
                    )

            if validation_error_message:
                raise ValidationError("\n".join(validation_error_message))

    @api.constrains('l10n_be_dimona_category', 'contract_date_start', 'contract_date_end', 'l10n_be_dimona_planned_start_time', 'l10n_be_dimona_planned_end_time', 'wage_type')
    def _check_dimona_flx_rules(self):
        for version in self:
            if not version.is_flexi() or not version.contract_date_start:
                continue

            if not version.contract_date_end:
                raise ValidationError(self.env._("Contract end date must always be defined on a flexi-job."))

            start_q = (version.contract_date_start.month - 1) // 3
            end_q = (version.contract_date_end.month - 1) // 3

            if version.contract_date_start.year != version.contract_date_end.year or start_q != end_q:
                q_last_month = start_q * 3 + 3
                q_last_day = date(version.contract_date_start.year, q_last_month, 1) + relativedelta(day=31)
                raise ValidationError(self.env._("Occupation date of a flexi-job cannot overlap two quarters. Select an end date before %s", q_last_day.strftime('%d/%m/%Y')))

            if version.contract_date_start == version.contract_date_end:
                start_time = version.l10n_be_dimona_planned_start_time
                end_time = version.l10n_be_dimona_planned_end_time

                if start_time is False or end_time is False:
                    raise ValidationError(self.env._("For a same-day flexi-job, the planned start and end times must be defined."))
                if not (0 <= start_time <= 24) or not (0 <= end_time <= 24):
                    raise ValidationError(self.env._("For a same-day flexi-job, the planned times must be between 0 and 24 hours."))
                if start_time >= end_time:
                    raise ValidationError(self.env._("For a same-day flexi-job, the planned start time must be before the planned end time."))

    @api.constrains("l10n_be_group_insurance_rate")
    def _check_l10n_be_group_insurance_rate(self):
        for version in self:
            if version.l10n_be_group_insurance_rate and (version.l10n_be_group_insurance_rate < 0 or version.l10n_be_group_insurance_rate > 1.0):
                raise ValidationError(self.env._("Group insurance rate must be between 0 and 100 %."))

    @api.constrains('housing_onss_amount', 'housing_fiscal_amount')
    def _check_housing_amounts(self):
        """ The housing benefit in kind is only valid when both of its valuations are filled. """
        for version in self:
            # One amount alone means the officer forgot the other base, which would be silently untaxed
            if bool(version.housing_onss_amount) != bool(version.housing_fiscal_amount):
                raise ValidationError(self.env._(
                    "The Housing benefit in kind needs both amounts, the one submitted to the social"
                    " contributions (ONSS) and the one submitted to the withholding taxes (Fiscal).",
                ))

    @api.constrains('l10n_be_apprenticeship_contract_number')
    def _check_l10n_be_apprenticeship_contract_number(self):
        for version in self:
            if version.contract_date_start and version.employee_type_id.code == 'Apprenticeship' and not version.l10n_be_apprenticeship_contract_number:
                raise ValidationError(self.env._("You need to have Apprenticeship Contract Number to start an Apprenticeship contract."))

    @api.constrains('resource_calendar_id')
    def _check_hours_per_week_required(self):
        for version in self:
            if version.employee_id.company_id.country_id.code != 'BE':
                continue
            # resource_calendar_id can be transiently empty mid-write
            if version.resource_calendar_id and version._is_fully_flexible():
                raise ValidationError(self.env._("You must set 'Hours Per Week' when 'Working Hours' is Undefined."))

    @api.constrains(
        'insured_relative_children', 'has_hospital_insurance', 'insured_relative_adults',
        'insured_relative_spouse', 'hospital_insurance_amount_per_child',
        'hospital_insurance_amount_per_adult', 'hospital_insurance_employee_contribution')
    def _check_hospital_insurance_employee_contribution(self):
        for version in self:
            if version.hospital_insurance_employee_contribution < 0:
                raise ValidationError(self.env._('Hospital insurance employee contribution should be positive'))
            if version.hospital_insurance_employee_contribution > version.insurance_amount:
                raise ValidationError(self.env._('Hospital insurance employee contribution cannot be higher than the actual insurance amount'))

    @api.constrains(
        'l10n_be_ambulatory_insured_children', 'l10n_be_has_ambulatory_insurance', 'l10n_be_ambulatory_insured_adults',
        'l10n_be_ambulatory_insured_spouse', 'l10n_be_ambulatory_amount_per_child', 'l10n_be_ambulatory_amount_per_adult',
        'l10n_be_ambulatory_insurance_employee_contribution')
    def _check_l10n_be_ambulatory_insurance_employee_contribution(self):
        for version in self:
            if version.l10n_be_ambulatory_insurance_employee_contribution < 0:
                raise ValidationError(self.env._('Ambulatory insurance employee contribution should be positive'))
            if version.l10n_be_ambulatory_insurance_employee_contribution > version.l10n_be_ambulatory_insurance_amount:
                raise ValidationError(self.env._('Ambulatory insurance employee contribution cannot be higher than the actual insurance amount'))

    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template()
        if self.env.company.country_id.code == "BE":
            whitelisted_fields += [
                "car_atn",
                "commission_on_target",
                "employee_type_id",
                "fiscal_voluntarism_amount",
                "fiscal_voluntarism_type",
                "fiscal_voluntarism_percentage",
                "fuel_card",
                "has_hospital_insurance",
                "laptop",
                "tablet",
                "hourly_wage",
                "insurance_amount",
                "internet",
                "l10n_be_joint_committee_id",
                "l10n_be_worker_status",
                "insured_relative_adults",
                "insured_relative_children",
                "insured_relative_spouse",
                "ip_artist",
                "ip_onss",
                "ip_wage_rate",
                "l10n_be_ambulatory_insurance_amount",
                "l10n_be_ambulatory_insurance_notes",
                "l10n_be_ambulatory_insured_adults",
                "l10n_be_ambulatory_insured_children",
                "l10n_be_ambulatory_insured_spouse",
                "l10n_be_canteen_cost",
                "l10n_be_dimona_category",
                "l10n_be_impulsion_plan",
                "l10n_be_group_insurance_rate",
                "l10n_be_has_ambulatory_insurance",
                "l10n_be_hospital_insurance_notes",
                "l10n_be_mobility_budget",
                "l10n_be_mobility_budget_amount",
                "l10n_be_mobility_budget_amount_monthly",
                "is_meal_voucher_valid",
                "l10n_be_worker_code_id",
                "meal_voucher_amount",
                "meal_voucher_calculation_method",
                "meal_voucher_employee_share",
                "mobile",
                "mobile_amount",
                "no_withholding_taxes",
                "l10n_be_resident_situation",
                "rd_percentage",
                "l10n_be_lsa_monthly_misc_other_amount",
                "l10n_be_lsa_homeworking_amount",
                "l10n_be_lsa_office_fees_amount",
                "l10n_be_lsa_office_fees_2022_amount",
                "l10n_be_lsa_phone_amount",
                "l10n_be_lsa_internet_amount",
                "l10n_be_lsa_pc_amount",
                "l10n_be_lsa_second_screen_amount",
                "l10n_be_lsa_scanner_amount",
                "l10n_be_lsa_car_management_garage_amount",
                "l10n_be_lsa_car_management_parking_amount",
                "l10n_be_lsa_car_management_wash_amount",
                "l10n_be_lsa_travel_cost_loc_amount",
                "l10n_be_lsa_travel_cost_meal_amount",
                "l10n_be_lsa_travel_cost_living_amount",
                "l10n_be_lsa_service_travel_abroad_amount",
                "l10n_be_lsa_working_tools_amount",
                "l10n_be_lsa_buying_work_clothes_amount",
                "l10n_be_lsa_work_clothes_maintenance_amount",
                "l10n_be_lsa_personal_work_clothes_maintenance_amount",
                "l10n_be_lsa_car_travel_amount",
                "l10n_be_lsa_bike_travel_amount",
                "l10n_be_lsa_bike_professional_travel_amount",
                "l10n_be_lsa_daily_misc_base_amount",
                "l10n_be_lsa_monthly_misc_base_amount",
                "l10n_be_lsa_daily_misc_other_amount",
                "l10n_be_lsa_monthly_pro_base_amount",
                "l10n_be_lsa_monthly_pro_other_amount",
                "l10n_be_salary_scale_id",
                "l10n_be_is_sale_representative",
                "transport_mode_car",
                "wage",
                "wage_type",
                "bike_id",
                "car_id",
                "new_bike",
                "new_bike_model_id",
                "has_new_car",
                "new_car_model_id",
                "transport_mode_bike",
            ]
        return whitelisted_fields

    def _get_marital_status_selection(self):
        if self.env.company.country_id.code != "BE":
            return super()._get_marital_status_selection()
        return super()._get_marital_status_selection() + [
            ("separated", self.env._("Judicially Separated"))
        ]

    def _get_student_min_wage(self, salary_scale, age, wage_type='monthly', hours_per_week=None):
        self.ensure_one()

        student_scales = self.env['hr.rule.parameter']._get_parameter_from_code(f'cp_200_salary_scale_student_{salary_scale}', raise_if_not_found=False)
        if not student_scales:
            return 0

        applicable_age = max((a for a in student_scales if a <= age), default=None)
        if not applicable_age:
            return 0

        min_wage = student_scales.get(applicable_age)
        if wage_type == 'hourly' and hours_per_week:
            min_wage = self._calculate_min_hourly_wage(min_wage, hours_per_week)
        return min_wage

    def _get_employee_min_wage(self, reference_date=None, salary_scale=None, company_seniority=None, seniority=None, wage_type="monthly", hours_per_week=None):
        self.ensure_one()

        if reference_date is None:
            reference_date = date.today()
        if salary_scale is None:
            salary_scale = self.l10n_be_salary_scale_id.code
        if company_seniority is None or seniority is None:
            delta = relativedelta(reference_date, self.employee_id._get_first_contract_date())
            seniority = self.l10n_be_scale_seniority + delta.years + (self.l10n_be_scale_seniority_months + delta.months) // 12
            company_seniority = delta.years

        scales_first_year = self.env['hr.rule.parameter']._get_parameter_from_code(f'cp200_salary_scale_first_year_{salary_scale}', date=reference_date, raise_if_not_found=False)
        scales = self.env['hr.rule.parameter']._get_parameter_from_code(f'cp200_salary_scale_{salary_scale}', date=reference_date, raise_if_not_found=False)
        scales = scales if company_seniority else scales_first_year
        if not scales:
            return 0
        applicable_seniority = max((s for s in scales if s <= seniority), default=None)
        if applicable_seniority is None:
            return 0
        min_wage = scales.get(applicable_seniority)
        if wage_type == 'hourly' and hours_per_week:
            min_wage = self._calculate_min_hourly_wage(min_wage, hours_per_week)
        return min_wage

    def _calculate_min_hourly_wage(self, min_wage, hours_per_week):
        return (min_wage * 3) / 13 / hours_per_week

    def _get_min_wage_warning_message(self, scale_type, scale_value, min_wage, wage_fields):
        return self.env._(
            "The %(fields)s is under the minimum scale of %(amount)s€ for a %(type)s of %(value)s years.",
            fields=wage_fields,
            amount=round(min_wage, 2),
            type=scale_type,
            value=scale_value,
        )

    @api.depends('l10n_be_time_credit', 'resource_calendar_id.calendar_type',
                'resource_calendar_id.attendance_ids.work_entry_type_id.l10n_be_is_time_credit',
                'resource_calendar_id.attendance_ids.duration_hours',
                'reference_calendar_id.hours_per_week')
    def _compute_work_time_rate(self):
        fixed_time_credit_versions = self.filtered(
            lambda v: not v._is_flexible() and v.l10n_be_time_credit and v.resource_calendar_id.calendar_type == 'fixed'
        )
        for version in fixed_time_credit_versions:
            calendar = version.resource_calendar_id
            ref_calendar = version._get_reference_calendar()
            ref_hours = ref_calendar.hours_per_week if ref_calendar else 0

            relevant_attendances = calendar.attendance_ids.filtered(
                lambda a: a._is_work_period() or a.work_entry_type_id.l10n_be_is_time_credit
            )

            total_weekly_hours = sum(relevant_attendances.mapped('duration_hours'))
            version.work_time_rate = float_round(total_weekly_hours / ref_hours, precision_digits=2) if ref_hours else 0.0

        super(HrVersion, self - fixed_time_credit_versions)._compute_work_time_rate()

    @api.depends('l10n_be_work_exemption_date')
    def _compute_l10n_be_work_exemption_training_date(self):
        for version in self:
            version.l10n_be_work_exemption_training_date = version.l10n_be_work_exemption_date

    @api.depends(
        "company_id.resource_calendar_id.days_per_week",
        "company_id.resource_calendar_id.hours_per_day",
        "hourly_wage",
        "resource_calendar_id.calendar_type",
        "reference_calendar_id.days_per_week",
        "resource_calendar_id.attendance_ids",
        "resource_calendar_id.days_per_week",
        "resource_calendar_id.hours_per_day",
        "wage",
        "wage_type",
    )
    def _compute_daily_wage(self):
        for version in self:
            if version.wage_type == "hourly":
                version.l10n_be_daily_wage = version.hourly_wage * version.resource_calendar_id.hours_per_day
            else:
                weekly_wage = version._get_contract_wage() * 3 / 13
                days_per_week = version._l10n_be_get_days_per_week()
                version.l10n_be_daily_wage = weekly_wage / days_per_week if days_per_week else 0

    def _l10n_be_get_hours_per_week(self, year):
        """
        Weekly hours for BE payroll, robust across fixed, variable, no-schedule and reference-calendar configurations.

        Variable calendars store 0 in hours_per_week unless set manually, so the value is reconstructed from the
        attendances of the requested year when missing. Returns 0 only when no schedule can be resolved at all.
        """
        self.ensure_one()
        if self._is_flexible() and not self._is_fully_flexible():
            return self.resource_calendar_id.hours_per_week
        date_from, date_to = date(year, 1, 1), date(year, 12, 31)
        for calendar in (
            self.resource_calendar_id,
            self.reference_calendar_id,
            self.company_id.resource_calendar_id,
        ):
            if not calendar:
                continue
            hours = calendar.hours_per_week
            if not hours and calendar.calendar_type == "variable":
                hours = calendar._l10n_be_get_hours_per_week_for_period(date_from, date_to)
            if hours:
                return hours
        return 0.0

    def _l10n_be_get_days_per_week(self):
        self.ensure_one()
        for calendar in (
            self.resource_calendar_id,
            self.reference_calendar_id,
            self.company_id.resource_calendar_id,
        ):
            if calendar and calendar.days_per_week:
                return calendar.days_per_week
        return self.resource_calendar_id.days_per_week

    def _l10n_be_get_monthly_wage(self, year):
        """
        Gross monthly wage, scaled up from the hourly rate when the employee is paid by the hour.

        :param year: The year whose schedule prices the hours, as variable calendars can be resolved from
            the attendances of a given year.
        :return: The gross monthly wage, or 0 when no schedule can be resolved for an hourly employee.
        """
        self.ensure_one()
        if self.wage_type != "hourly":
            return self._get_contract_wage()
        return self.hourly_wage * self._l10n_be_get_hours_per_week(year) * 13 / 3

    @api.depends('meal_voucher_amount', 'meal_voucher_employee_share')
    def _compute_is_meal_voucher_valid(self):
        for version in self.filtered(lambda v: v.country_code == 'BE'):
            max_meal_voucher_amount = self.env['hr.rule.parameter']._get_parameter_from_code('max_meal_voucher_amount', raise_if_not_found=False)
            min_meal_voucher_employee_share = self.env['hr.rule.parameter']._get_parameter_from_code('min_meal_voucher_employee_share', raise_if_not_found=False)
            if not max_meal_voucher_amount or not min_meal_voucher_employee_share:
                version.is_meal_voucher_valid = False
                continue

            if version.meal_voucher_amount != 0 and (version.meal_voucher_amount > max_meal_voucher_amount or version.meal_voucher_amount < version.meal_voucher_employee_share or version.meal_voucher_employee_share < min_meal_voucher_employee_share):
                version.is_meal_voucher_valid = False
            else:
                version.is_meal_voucher_valid = True

    @api.depends('disabled_children_number', 'children')
    def _compute_dependent_children(self):
        for version in self:
            version.dependent_children = version.children + version.disabled_children_number

    @api.depends('l10n_be_resident_situation')
    def _compute_is_non_resident(self):
        for version in self:
            version.is_non_resident = version.l10n_be_resident_situation == 'non_resident'

    def _inverse_is_non_resident(self):
        for version in self.filtered(lambda v: v.country_code == 'BE'):
            sudo_version = version.sudo()
            if version.is_non_resident:
                sudo_version.l10n_be_resident_situation = 'non_resident'
            elif sudo_version.l10n_be_resident_situation == 'non_resident':
                sudo_version.l10n_be_resident_situation = 'resident'

    @api.depends('l10n_be_resident_situation')
    def _compute_no_withholding_taxes(self):
        for version in self:
            version.no_withholding_taxes = version.l10n_be_resident_situation == 'cross_border'

    @api.depends('other_juniors_dependent', 'other_disabled_juniors_dependent')
    def _compute_dependent_people(self):
        for version in self:
            # In the UI, we explicitely declare other_juniors_dependent as *including* other_disabled_juniors_dependent
            # However, as disabled must count for two, we sum the two fields here. This is not a mistake.
            version.dependent_juniors = version.other_juniors_dependent + version.other_disabled_juniors_dependent

    @api.depends('resource_calendar_id.attendance_ids.work_entry_type_id.l10n_be_is_time_credit')
    def _compute_l10n_be_time_credit(self):
        for version in self:
            time_credit = any(attendance.sudo().work_entry_type_id.l10n_be_is_time_credit for attendance in version.resource_calendar_id.attendance_ids)
            version.l10n_be_time_credit = time_credit

    @api.depends('l10n_be_joint_committee_id', 'work_time_rate')
    def _compute_eco_checks(self):
        eco_config = self.env['hr.rule.parameter']._get_parameter_from_code('eco_voucher_config', raise_if_not_found=False) or {}
        for version in self:
            jc = version.l10n_be_joint_committee_id
            if not jc or jc.egov3_code not in eco_config:
                version.eco_checks = 0
                continue
            jc_config = eco_config[jc.egov3_code]
            max_amount = jc_config['max_amount']
            work_time_rate = version.work_time_rate
            if 'amount_from_rate' in jc_config:
                # CP200 example: amount depends on work rate tiers
                amount = jc_config['amount_from_rate'][-1][1]  # default to last tier
                for rate_threshold, rate_amount in jc_config['amount_from_rate']:
                    if work_time_rate >= rate_threshold:
                        amount = rate_amount
                        break
                version.eco_checks = amount
            else:
                # Other JCs: max_amount * work_rate (capped at 100%)
                version.eco_checks = max_amount * min(1, work_time_rate)

    @api.depends('employee_type_id.l10n_be_joint_committee_id')
    def _compute_l10n_be_joint_committee_id(self):
        company_exec = self.env.ref("hr.contract_type_company_executive", raise_if_not_found=False)
        joint_committe_999 = self.env.ref("l10n_be_hr_payroll.l10n_be_joint_committee_999", raise_if_not_found=False)

        for version in self:
            if version.employee_type_id == company_exec:
                version.l10n_be_joint_committee_id = joint_committe_999
            else:
                version.l10n_be_joint_committee_id = version.employee_type_id.l10n_be_joint_committee_id or version.payroll_config_id.l10n_be_main_joint_committee

    def _get_l10n_be_available_worker_codes(self):
        self.ensure_one()
        return self.l10n_be_allowed_worker_code_ids.filtered(
            lambda c: not c.employee_type_ids or self.employee_type_id in c.employee_type_ids)

    @api.depends('l10n_be_allowed_worker_code_ids', 'employee_type_id')
    def _compute_l10n_be_worker_code_is_single(self):
        for version in self:
            version.l10n_be_worker_code_is_single = len(version._get_l10n_be_available_worker_codes()) == 1

    @api.depends('employee_type_id.l10n_be_worker_code_ids', 'structure_type_id', 'l10n_be_allowed_worker_code_ids')
    def _compute_l10n_be_worker_code_id(self):
        for version in self:
            if version.company_id.country_id.code != 'BE':
                continue
            available_codes = version._get_l10n_be_available_worker_codes()
            version.l10n_be_worker_code_id = (available_codes if len(available_codes) == 1 else None)\
                    or version.l10n_be_worker_code_id\
                    or self.env.ref("l10n_be_hr_payroll.l10n_be_worker_code_00495", raise_if_not_found=False)

    @api.depends('train_transport_employee_kilometer', 'l10n_be_joint_committee_id')
    def _compute_train_transport_reimbursed_amount(self):
        for version in self:
            version.train_transport_reimbursed_amount = version._get_train_transport_reimbursed_amount()

    @api.depends('bus_transport_employee_amount', 'bus_transport_periodicity', 'bus_transport_employee_kilometer',
        'l10n_be_joint_committee_id')
    def _compute_bus_transport_reimbursed_amount(self):
        for version in self:
            version.bus_transport_reimbursed_amount = version._get_public_transport_reimbursed_amount('bus')

    @api.depends('tram_transport_employee_amount', 'tram_transport_periodicity', 'tram_transport_employee_kilometer',
        'l10n_be_joint_committee_id')
    def _compute_tram_transport_reimbursed_amount(self):
        for version in self:
            version.tram_transport_reimbursed_amount = version._get_public_transport_reimbursed_amount('tram')

    @api.depends('metro_transport_employee_amount', 'metro_transport_periodicity', 'metro_transport_employee_kilometer',
        'l10n_be_joint_committee_id')
    def _compute_metro_transport_reimbursed_amount(self):
        for version in self:
            version.metro_transport_reimbursed_amount = version._get_public_transport_reimbursed_amount('metro')

    @api.depends('private_car_employee_kilometer', 'l10n_be_joint_committee_id')
    def _compute_private_car_reimbursed_amount(self):
        for version in self:
            version.private_car_reimbursed_amount = version._get_private_car_reimbursed_amount()

    @api.depends('bike_transport_employee_kilometer', 'l10n_be_joint_committee_id')
    def _compute_bike_transport_reimbursed_amount(self):
        for version in self:
            version.bike_reimbursed_amount = version._get_bike_reimbursed_amount()

    def _get_below_scale_warning_applicable_versions(self):
        today = fields.Date.context_today(self)
        valid_contract_templates = self.filtered(lambda v: not v.employee_id)
        valid_employee_versions = self.filtered(
            lambda v: v.employee_id and v.contract_date_start and v.contract_date_start <= today
                      and (not v.contract_date_end or v.contract_date_end >= today)
        )
        return (valid_contract_templates | valid_employee_versions).filtered(
            lambda v: v.company_id.country_id.code == 'BE'
                      and v.structure_type_id
                      and v.l10n_be_joint_committee_id.egov3_code != '999'
                      and (v.l10n_be_egov3_code != '200' or not v.l10n_be_is_sale_representative)
        )

    @api.depends('l10n_be_needs_dimona_in', 'l10n_be_needs_dimona_out', 'l10n_be_needs_dimona_update', 'l10n_be_needs_dimona_cancel', 'l10n_be_joint_committee_id')
    def _compute_l10n_be_dimona_next_action(self):
        for version in self:
            if version.l10n_be_joint_committee_id.egov3_code == '999':
                version.l10n_be_dimona_next_action = False
                continue
            if version.l10n_be_needs_dimona_in:
                version.l10n_be_dimona_next_action = 'in'
            elif version.l10n_be_needs_dimona_out:
                version.l10n_be_dimona_next_action = 'out'
            elif version.l10n_be_needs_dimona_update:
                version.l10n_be_dimona_next_action = 'update'
            elif version.l10n_be_needs_dimona_cancel:
                version.l10n_be_dimona_next_action = 'cancel'
            elif version.l10n_be_dimona_next_action == 'done':
                continue
            else:
                version.l10n_be_dimona_next_action = False

    def _inverse_l10n_be_dimona_next_action(self):
        for version in self:
            if version.l10n_be_dimona_next_action in ('progress', 'issue'):
                continue
            version.l10n_be_needs_dimona_in = version.l10n_be_dimona_next_action == 'in'
            version.l10n_be_needs_dimona_out = version.l10n_be_dimona_next_action == 'out'
            version.l10n_be_needs_dimona_update = version.l10n_be_dimona_next_action == 'update'
            version.l10n_be_needs_dimona_cancel = version.l10n_be_dimona_next_action == 'cancel'

    @api.depends('l10n_be_dimona_declaration_id.state', 'contract_date_start')
    def _compute_l10n_be_needs_dimona_in(self):
        for version in self:
            if version.l10n_be_dimona_declaration_id:
                if version.l10n_be_dimona_declaration_id.state != 'B':
                    version.l10n_be_needs_dimona_in = False
                else:
                    version.l10n_be_needs_dimona_in = True
                continue
            if version.contract_date_start:
                versions_by_employee = version.employee_id._get_contract_versions(
                    date_start=version.contract_date_start,
                    date_end=version.contract_date_start,
                    domain=Domain('l10n_be_dimona_declaration_id', '!=', False))
                if versions_by_employee[version.employee_id.id][version.contract_date_start]:
                    version.l10n_be_needs_dimona_in = False
                else:
                    version.l10n_be_needs_dimona_in = True
            else:
                version.l10n_be_needs_dimona_in = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'l10n_be_dimona_category' in vals and vals['l10n_be_dimona_category'] == 'flx' and vals.get('contract_date_start'):
                if not vals.get('contract_date_end'):
                    start_date = fields.Date.from_string(vals['contract_date_start'])
                    start_q_year = (start_date.year, (start_date.month - 1) // 3)
                    q_month = start_q_year[1] * 3 + 3
                    vals['contract_date_end'] = (date(start_q_year[0], q_month, 1) + relativedelta(months=1, days=-1)).strftime('%Y-%m-%d')
        return super().create(vals_list)

    @api.depends('address_id', 'country_code')
    def _compute_l10n_be_location_unit(self):
        for version in self:
            if version.country_code != 'BE':
                version.l10n_be_location_unit = False
                continue
            version.l10n_be_location_unit = self.env['hr.work.location'].search([
                    ('address_id', '=', version.address_id.id), ('location_type', '=', 'dmfa_unit')], limit=1) if version.address_id else False

    @api.depends('employee_id.version_ids.date_version', 'employee_id.version_ids.l10n_be_is_retired')
    def _compute_retirement_date(self):
        for version in self:
            retired_versions = self.employee_id.version_ids.filtered(lambda v: v.l10n_be_is_retired)
            version.l10n_be_retirement_date = retired_versions[0].date_version if retired_versions else False

    def write(self, vals):
        trigger_fields = ['contract_date_start', 'contract_date_end', 'l10n_be_dimona_planned_hours', 'active', 'l10n_be_joint_committee_id', 'transport_mode_car', 'car_id', 'l10n_be_dimona_planned_start_time', 'l10n_be_dimona_planned_end_time']
        potential_update = any(field in vals for field in trigger_fields)
        if potential_update:
            # Sudo because hr.group_hr_user has the right to modify contract dates
            old_values = {version_sudo: {field: version_sudo[field] for field in trigger_fields + ['l10n_be_dimona_declaration_id']} for version_sudo in self.sudo()}

        # Force to track cars in employee form if any changes is found after version write
        if not self._track_disabled():
            self.employee_id._track_prepare(["car_id", "bike_id"])

        if 'contract_date_start' in vals:
            for version in self:
                if version.company_id.country_id.code == 'BE' and version.contract_date_start != fields.Date.to_date(vals['contract_date_start']):
                    version.l10n_be_needs_dimona_in = True

        res = super().write(vals)
        if potential_update:
            trigger_activities_employees = self.env['hr.employee']
            for version_sudo in self.sudo():
                if version_sudo.company_id.country_id.code != 'BE':
                    continue

                if version_sudo.l10n_be_joint_committee_id.egov3_code == '999':
                    if old_values[version_sudo]['l10n_be_joint_committee_id'] != version_sudo.l10n_be_joint_committee_id:
                        version_sudo.l10n_be_worker_code_id = False
                        version_sudo.l10n_be_dimona_category = False
                        version_sudo.l10n_be_dimona_next_action = False
                    continue

                if version_sudo.is_flexi() and version_sudo.contract_date_start and version_sudo.contract_date_start > fields.Date.today() + timedelta(days=31):
                    continue

                if not self.env.context.get('salary_simulation'):
                    self._run_dimona_action_submit_declaration_to_gov(version_sudo, old_values[version_sudo])

                if 'transport_mode_car' in vals or 'car_id' in vals:
                    old_car = old_values[version_sudo]['car_id']
                    new_car = version_sudo.car_id
                    if not new_car or new_car == old_car:
                        continue
                    # The previous car goes back to the pool, the fleet officer stays in charge of the driver.
                    if old_car.future_driver_id == version_sudo.employee_id.work_contact_id:
                        old_car.future_driver_id = False
                    new_car.future_driver_id = version_sudo.employee_id.work_contact_id

                if vals.get('contract_date_start') and version_sudo.contract_date_start != old_values[version_sudo]['contract_date_start']\
                        and version_sudo.employee_id and version_sudo.employee_id.current_version_id._is_struct_from_country('BE')\
                        and version_sudo.employee_id.current_version_id.contract_date_start:
                    trigger_activities_employees |= version_sudo.employee_id

            trigger_activities_employees.sudo()._trigger_l10n_be_next_activities()

        if ((cat_id := vals.get('l10n_be_salary_scale_id')) and self.l10n_be_joint_committee_id.egov3_code == '302'):
            salary_scale = self.env['l10n_be.salary.scale'].browse(cat_id)
            if (cat_code := salary_scale.code) and cat_code.isnumeric() and int(cat_code) <= 9:
                for version_sudo in self.sudo():
                    version_sudo._adjust_base_computed_seniority(cat_code)
        return res

    def _run_dimona_action_submit_declaration_to_gov(self, version, old_version_vals):
        # Only a declaration that already existed can need correcting
        # `hr` propagates the contract dates through a nested write, so an entrance
        # dimona that is *currently* being saved is already visible in this piece of
        # code - we need to check the old value otherwise we're comparing the dimona
        # info of the new declaration with itslef
        declared_before = old_version_vals['l10n_be_dimona_declaration_id']
        # That propagation runs under sync_contract_dates, which `hr` also uses to
        # skip its own dates logic: it is not the user changing the contract, and
        # every version of one contract shares a single Dimona period anyway.
        dates_synced = self.env.context.get('sync_contract_dates')
        # in plain english, we need a dimona update when:
        # - the planned hours are changed (student contracts)
        # - start date of the contract changes, but only if there was already an IN
        # dimona before with a different start date
        # - end date changed, but only if there was already an IN
        # dimona before with a different end date
        if (version.l10n_be_dimona_planned_hours != old_version_vals['l10n_be_dimona_planned_hours']
            or (declared_before
                and (not dates_synced and version.contract_date_start != old_version_vals['contract_date_start']
                    or (declared_before.date_end and not dates_synced and version.contract_date_end != old_version_vals['contract_date_end'])))):
            version.l10n_be_needs_dimona_update = True
        if version._check_dimona_out_requirements():
            version.l10n_be_needs_dimona_out = True
        if not version.active and old_version_vals['active'] and not version._l10n_be_dimona_already_declared('dimona_cancel'):
            version.l10n_be_needs_dimona_cancel = True
        version._l10n_be_dimona_autodeclare()

    def _check_dimona_out_requirements(self):
        self.ensure_one()
        is_eligible_code_495_active = self.l10n_be_worker_code_id.dmfa_code == '495' and not self.l10n_be_dimona_declaration_id.date_end
        is_departure_reason_set = self.employee_id.departure_reason_id
        return bool(is_eligible_code_495_active and is_departure_reason_set) \
            and not self._l10n_be_dimona_already_declared('dimona_out')

    def _l10n_be_dimona_already_declared(self, declaration_type):
        """Whether this version already filed this operation against its Dimona period.

        00913-355 and 00913-356 make a cancellation and a departure one-shot: the ONSS
        refuses a second one against a period it has already cancelled or closed. A
        refused declaration does not count -- correcting and re-filing it is the point.
        """
        self.ensure_one()
        return bool(self.env['l10n.be.dimona.declaration'].search_count([
            ('version_id', '=', self.id),
            ('declaration_type', '=', declaration_type),
            ('state', '!=', 'B'),
        ], limit=1))

    @api.model
    def _benefit_white_list(self):
        return super()._benefit_white_list() + [
            'insurance_amount',
            'ip_value',
            'private_car_reimbursed_amount',
            'train_transport_reimbursed_amount',
            'bus_transport_reimbursed_amount',
            'metro_transport_reimbursed_amount',
            'tram_transport_reimbursed_amount',
            'bike_transport_reimbursed_amount',
            'l10n_be_ambulatory_insurance_amount',
            'meal_voucher_paid_monthly_by_employer',
        ]

    @api.depends('has_hospital_insurance')
    def _compute_hospital_insurance_fields(self):
        for version in self:
            if not version.has_hospital_insurance:
                version.insured_relative_spouse = False
                version.insured_relative_adults = 0
                version.insured_relative_children = 0
                version.hospital_insurance_employee_contribution = 0

    @api.depends('has_hospital_insurance', 'insured_relative_adults', 'insured_relative_spouse')
    def _compute_insured_relative_adults_total(self):
        for version in self:
            version.insured_relative_adults_total = (
                int(version.has_hospital_insurance)
                + version.insured_relative_adults
                + int(version.insured_relative_spouse))

    @api.model
    def _get_insurance_amount(self, child_amount, child_count, adult_amount, adult_count):
        return child_amount * child_count + adult_amount * adult_count

    @api.depends(
        'insured_relative_children', 'insured_relative_adults_total',
        'hospital_insurance_amount_per_child', 'hospital_insurance_amount_per_adult')
    def _compute_insurance_amount(self):
        for version in self:
            version.insurance_amount = version._get_insurance_amount(
                version.hospital_insurance_amount_per_child,
                version.insured_relative_children,
                version.hospital_insurance_amount_per_adult,
                version.insured_relative_adults_total)

    @api.depends('l10n_be_has_group_insurance')
    def _compute_group_insurance_fields(self):
        for version in self:
            if not version.l10n_be_has_group_insurance:
                version.l10n_be_group_insurance_company_contribution = 0
                version.l10n_be_group_insurance_company_contribution_unit = 'percentage'
                version.l10n_be_group_insurance_employee_contribution = 0
                version.l10n_be_group_insurance_employee_contribution_unit = 'percentage'
                version.l10n_be_group_insurance_employee_voluntary = 0

    @api.depends('l10n_be_has_ambulatory_insurance')
    def _compute_ambulatory_insurance_fields(self):
        for version in self:
            if not version.l10n_be_has_ambulatory_insurance:
                version.l10n_be_ambulatory_insured_spouse = False
                version.l10n_be_ambulatory_insured_adults = 0
                version.l10n_be_ambulatory_insured_children = 0

    @api.constrains('rd_percentage')
    def _check_discount_percentage(self):
        if self.filtered(lambda c: c.rd_percentage < 0 or c.rd_percentage > 1):
            raise ValidationError(self.env._('The time Percentage in R&D should be between 0-100'))
        if self.env.context.get('salary_simulation'):
            return
        for version in self:
            if version.rd_percentage and version.employee_id and version.employee_id.certificate not in ['civil_engineer', 'doctor', 'master', 'bachelor']:
                raise ValidationError(self.env._('Only employees with a Bachelor/Master/Doctor/Civil Engineer degree can benefit from the withholding taxes exemption.'))

    @api.constrains("contract_date_start", "work_location_id")
    def _check_contract_date_start(self):
        for version in self:
            if version.country_code != 'BE':
                continue
            if version.work_location_id.date_start and version.contract_date_start and version.contract_date_start < version.work_location_id.date_start:
                raise ValidationError(self.env._("The start date of the related establishment unit %(eu)s is not compatible with the start date of the contract %(ver)s.", eu=version.work_location_id.date_start, ver=version.contract_date_start))

    @api.depends('ip_wage_rate')
    def _compute_ip_value(self):
        for version in self:
            version.ip_value = version.ip_wage_rate

    @api.depends('employee_id', 'private_car_employee_kilometer', 'transport_mode_car')
    def _compute_car_id(self):
        versions_to_reset = self.filtered(lambda v: v.private_car_employee_kilometer or not v.transport_mode_car)
        versions_to_reset.car_id = False
        remaining_versions = self - versions_to_reset
        if not remaining_versions:
            return
        employees_partners = remaining_versions.employee_id.work_contact_id
        cars = self.env['fleet.vehicle'].search([
            ('vehicle_type', '=', 'car'),
            '|', ('driver_id', 'in', employees_partners.ids), ('future_driver_id', 'in', employees_partners.ids)
        ], order='future_driver_id, driver_id')
        dict_car = {
            (car.driver_id or car.future_driver_id).id: car.id for car in cars
        }
        for version in remaining_versions:
            if version.car_id:
                continue
            partner_id = version.employee_id.work_contact_id.id
            if partner_id in dict_car:
                version.car_id = dict_car[partner_id]
                version.transport_mode_car = True
            else:
                version.car_id = False

    @api.depends('new_bike', 'new_bike_model_id')
    def _compute_bike_id(self):
        for version in self:
            if version.new_bike or version.new_bike_model_id:
                version.bike_id = False

    @api.depends('bike_id')
    def _compute_new_bike_model_id(self):
        for version in self:
            if version.bike_id:
                version.update({
                    'new_bike_model_id': False,
                    'new_bike': False,
                })

    @api.depends('new_bike_model_id')
    def _compute_new_bike(self):
        for version in self:
            if version.new_bike_model_id:
                version.new_bike = True

    @api.depends('car_id')
    def _compute_car_model_name(self):
        for version in self:
            if version.car_id:
                version.car_model_name = version.car_id.model_id.display_name
            else:
                version.car_model_name = False

    @api.depends('car_id')
    def _compute_fuel_type(self):
        for version in self:
            version.fuel_type = version.car_id.fuel_type if version.car_id else False

    @api.depends('car_id', 'car_id.total_depreciated_cost', 'car_id.atn')
    def _compute_car_atn_and_costs(self):
        self.car_atn = False
        self.company_car_total_depreciated_cost = False
        for version in self:
            if version.car_id:
                version.car_atn = version.car_id.atn
                version.company_car_total_depreciated_cost = version.car_id.total_depreciated_cost

    @api.depends('new_bike', 'bike_id', 'new_bike_model_id', 'bike_id.total_depreciated_cost',
        'bike_id.co2_fee', 'new_bike_model_id.default_total_depreciated_cost', 'transport_mode_bike')
    def _compute_company_bike_depreciated_cost(self):
        for version in self:
            version.company_bike_depreciated_cost = False
            if not version.new_bike and version.transport_mode_bike and version.bike_id:
                version.company_bike_depreciated_cost = version.bike_id.total_depreciated_cost
            elif not version.transport_mode_bike and version.new_bike and version.new_bike_model_id:
                version.company_bike_depreciated_cost = version.new_bike_model_id.default_recurring_cost_amount_depreciated

    @api.depends('car_id.log_contracts.state')
    def _compute_car_open_contracts_count(self):
        for version in self:
            version.car_open_contracts_count = len(version.car_id.log_contracts.filtered(
                lambda c: c.state == 'open').ids)

    @api.depends('car_open_contracts_count', 'car_id.log_contracts.recurring_cost_amount_depreciated')
    def _compute_recurring_cost_amount_depreciated(self):
        for version in self:
            if version.car_open_contracts_count == 1:
                version.recurring_cost_amount_depreciated = version.car_id.log_contracts.filtered(
                    lambda c: c.state == 'open'
                ).recurring_cost_amount_depreciated
            else:
                version.recurring_cost_amount_depreciated = 0.0

    def _inverse_recurring_cost_amount_depreciated(self):
        for version in self:
            if version.car_open_contracts_count == 1:
                version.car_id.log_contracts.filtered(
                    lambda c: c.state == 'open'
                ).recurring_cost_amount_depreciated = version.recurring_cost_amount_depreciated

    def _get_available_cars_domain(self):
        return self._get_vehicles_without_current_drivers_domain(
            self.employee_id.work_contact_id,
        )

    @api.depends('name')
    def _compute_available_cars_amount(self):
        for version in self:
            version.available_cars_amount = self.env['fleet.vehicle'].sudo().search_count(
                version._get_available_cars_domain(),
            )

    @api.onchange('new_bike')
    def _onchange_new_bike(self):
        if self.new_bike:
            self.bike_id = False
            self.bike_transport_employee_kilometer = False
        else:
            self.new_bike_model_id = False

    @api.depends('commission_on_target')
    def _compute_commission_cost(self):
        for version in self:
            version.warrants_cost = version.commission_on_target * 1.326 / 1.05
            warrant_commission = version.warrants_cost * 3.0
            cash_commission = version.commission_on_target * 9.0
            version.yearly_commission_cost = warrant_commission + cash_commission * (1 + EMPLOYER_ONSS)
            version.yearly_commission = warrant_commission + cash_commission
            version.warrant_value_employee = version.commission_on_target * 1.326 * (1.00 - 0.535)

    def _get_meal_voucher_info_depends_fields(self):
        return ['meal_voucher_amount', 'meal_voucher_employee_share']

    @api.depends(lambda self: self._get_meal_voucher_info_depends_fields())
    def _compute_meal_voucher_info(self):
        # The amount of the meal voucher is computed on the basis of the contribution
        # of the employer and the employee. Indeed, the first can contribute up to a
        # maximum of € 6.91 per check and per day provided, while the participation
        # of the second must amount to a minimum of € 1.09.
        # Depending on the number of extra legal paid holidays, the number of meal
        # voucher that will be given differs, as when the employee takes a days off
        # (no matter the nature), he won't receive a meal voucher.
        min_meal_voucher_threshold = self.env['hr.rule.parameter']._get_parameter_from_code('min_meal_voucher_employee_share', raise_if_not_found=False) or 1.09
        for version in self:
            employee_share = max(version.meal_voucher_employee_share, min_meal_voucher_threshold)
            version.meal_voucher_paid_by_employer = max(0, version.meal_voucher_amount - employee_share)
            monthly_nb_meal_voucher = version._get_monthly_nb_meal_voucher()
            version.meal_voucher_paid_monthly_by_employer = version.meal_voucher_paid_by_employer * monthly_nb_meal_voucher
            version.meal_voucher_average_monthly_amount = version.meal_voucher_amount * monthly_nb_meal_voucher

    def _get_monthly_nb_meal_voucher(self, holidays=None):
        return 220.0 / 12

    def _get_train_transport_reimbursed_amount(self):
        self.ensure_one()
        if self.country_code != 'BE' or not self.train_transport_employee_kilometer:
            return 0
        code = self.l10n_be_joint_committee_id.egov3_code
        rate = 1 / 12 if self.train_transport_periodicity == 'yearly' else 1
        train_equivalent_amount = self._get_train_equivalent_amount(
            self.train_transport_employee_kilometer, self.train_transport_periodicity)
        amount = train_equivalent_amount * rate
        if code == '200':
            rule = 'train_cp200_reimbursement_ratio'
        else:
            rule = 'train_cp302_reimbursement_ratio'
        reimbursement_rate = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            rule, date=self.env.context.get('payslip_date'), raise_if_not_found=False) or 0
        return amount * reimbursement_rate

    def _difference_years_months(self, start_date, end_date):
        if not start_date:
            return 0, 0
        if start_date.day != 1:
            start_date = (start_date + relativedelta(months=1)).replace(day=1)
        rd = relativedelta(end_date, start_date)
        return rd.years, rd.months

    def _compute_l10n_be_in_position_seniority(self):
        today = fields.Datetime.today().date()
        for version in self:
            dates = filter(None, [
                version._get_field_block_start_date('l10n_be_salary_scale_id'),
                version.contract_date_start])
            last_occupation_change_date = min(dates, default=False)
            if version.date_start > today:
                end_date = version.date_start
            else:
                end_date = version.date_end if version.date_end and version.date_end < today else today
            version.l10n_be_in_position_years, version.l10n_be_in_position_months = version._difference_years_months(last_occupation_change_date, end_date)

    @api.depends('l10n_be_base_computed_seniority')
    def _compute_l10n_be_computed_seniority(self):
        """
        This method compute the computed seniority which
        will be used in determining the pay scale for CP302
        Several Cases to be take into consideration
        --------------------------------------------------
        *** 1st Case ***
        Employee type = CDI (Fixed Term = True)

        *** 2nd Case ***
        Employee type = Temporary

        *** 3rd Case ***
        Employee type = Seasonal

        *** 4th Case ***
        Employee type = CREW
        """
        crew_employee_type_id = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_crew').id
        temporary_employee_type_id = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_temporary').id
        seasonal_employee_type_id = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_seasonal').id
        cp302_versions = self.filtered(lambda v: v.l10n_be_joint_committee_id.egov3_code == '302')
        cp200_versions = self.filtered(lambda v: v.l10n_be_joint_committee_id.egov3_code == '200')
        (self - cp302_versions - cp200_versions).update({
            'l10n_be_computed_seniority_years': 0,
            'l10n_be_computed_seniority_months': 0,
        })
        today = fields.Date.today()

        for version in cp200_versions:
            date_to = version.date_start if version.date_start and version.date_start > today else today
            company_seniority = relativedelta(date_to, version.employee_id._get_first_contract_date())
            seniority = version.l10n_be_scale_seniority + company_seniority.years + (company_seniority.months + version.l10n_be_scale_seniority_months) // 12
            version.l10n_be_computed_seniority_years = max(0, seniority)
            version.l10n_be_computed_seniority_months = (company_seniority.months + version.l10n_be_scale_seniority_months) % 12

        for version in cp302_versions:
            dates = list(filter(None, [
                version._get_field_block_start_date('l10n_be_salary_scale_id'),
                version.contract_date_start]))
            last_occupation_change_date = min(dates) if dates else False
            if not last_occupation_change_date:
                version.l10n_be_computed_seniority_years = 0
                version.l10n_be_computed_seniority_months = 0
                continue

            # 2nd & 3rd Cases
            if version.employee_type_id.id in (temporary_employee_type_id, seasonal_employee_type_id):
                version._calculate_seniority_work_entries(last_occupation_change_date)

            # 1st & 4th Cases
            elif not version.fixed_term or version.employee_type_id.id == crew_employee_type_id:
                version._calculate_seniority_cdi_crew()
            else:
                version.l10n_be_computed_seniority_years = 0
                version.l10n_be_computed_seniority_months = 0

    def _get_contract_wage_field(self):
        self.ensure_one()
        if self.wage_type == 'hourly':
            return 'l10n_be_flexi_hourly_wage' if self.is_flexi() else 'hourly_wage'
        return 'l10n_be_flexi_monthly_wage' if self.is_flexi() else 'wage'

    def _calculate_seniority_cdi_crew(self):
        """
        *** 1st Case ***
        Contract type = CDI + Computed Seniority < 1 year
            - If in-position seniority is less than 6 months → Computed Seniority = 0
            - Once in-position seniority reaches 6 months → Computed Seniority = 1 year
            - For the following 18 months → Computed Seniority remains 1 year
            - After a total of 24 months (6 + 18) → Computed Seniority = 2 years
            - Beyond that → Seniority increases normally (month by month)

        *** 4th Case ***
        Contract type = CREW
            - Salary scale is initially forced to 3
            - If in-position seniority is less than 6 months:
                → Salary scale = 3
                → Computed Seniority = 0
            - Once in-position seniority reaches 6 months:
                → Salary scale = 4
                → Computed Seniority = 1 year
            - For the following 18 months:
                → Salary scale = 4
                → Computed Seniority remains 1 year
            - After a total of 24 months:
                → Continue increasing seniority normally (month by month)
        """
        self.ensure_one()

        is_crew = self.employee_type_id.id == self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_crew').id
        if not self.l10n_be_base_computed_seniority:
            if self.l10n_be_in_position_years == 0 and self.l10n_be_in_position_months < 6:
                self.l10n_be_computed_seniority_years = 0
                self.l10n_be_computed_seniority_months = 0
                if is_crew:
                    crew_salary_scale_id = self.env.ref('l10n_be_hr_payroll.cp302_3').id
                    self.write({'l10n_be_salary_scale_id': crew_salary_scale_id})
                return
            if self.l10n_be_in_position_years < 2:
                self.l10n_be_computed_seniority_years = 1
                self.l10n_be_computed_seniority_months = 0
                if is_crew:
                    crew_salary_scale_id = self.env.ref('l10n_be_hr_payroll.cp302_4').id
                    self.write({'l10n_be_salary_scale_id': crew_salary_scale_id})
                return
        self.l10n_be_computed_seniority_years, self.l10n_be_computed_seniority_months = (
            self.l10n_be_in_position_years + self.l10n_be_base_computed_seniority,
            self.l10n_be_in_position_months,
        )

    def _calculate_seniority_work_entries(self, last_occupation_change_date):
        """
        *** 2nd Case ***
        Contract type = Temporary
            If the # of work entries on various days >= 130 => 1 Year of seniority
            If the # of work entries on various days >= 260 => 2 Years of seniority
            Then if the # of work entries on various days increase by 260 => +1 Year

        *** 3rd Case ***
        Contract type = Seasonal
            If the # of work entries on various days >= X => 1 Year of seniority
            If the # of work entries on various days >= X + Y => 2 Years of seniority
            Then if the # of work entries on various days increase by Y => +1 Year

            If the employee works 5 days/week => X = 130 and Y = 260
            If the employee works 6 days/week => X = 156 and Y = 312

            If the employee is Fully Fixed, amount of days on week = Total/Avg
            If the employee is Flexible, amount of days on a week = Total/Avg:
                - if <6 => 5 days/week
                - if >= 6 => 6 days/week
        """
        self.ensure_one()

        self.l10n_be_computed_seniority_months = 0  # We focus on years only
        number_of_work_entries = self._get_work_entries_count(last_occupation_change_date)

        if self.employee_type_id.id == self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_temporary').id:
            first_threshold = 130
            subsequent_threshold = 260
        else:
            """
            - 5 days/week: (130, 260)
            - 6 days/week: (156, 312)
            """
            hours_per_week, hours_per_day = self.resource_calendar_id.hours_per_week, self.resource_calendar_id.hours_per_day
            ratio = hours_per_week / hours_per_day if hours_per_day else 0
            amount_of_working_days_per_week = 5 if round(ratio) == 5 else 6
            first_threshold, subsequent_threshold = (130, 260) if amount_of_working_days_per_week == 5 else (156, 312)

        if number_of_work_entries >= first_threshold + subsequent_threshold:
            self.l10n_be_computed_seniority_years = 2 + int(number_of_work_entries - first_threshold - subsequent_threshold) / subsequent_threshold
        elif number_of_work_entries >= first_threshold:
            self.l10n_be_computed_seniority_years = 1
        else:
            self.l10n_be_computed_seniority_years = 0

    def _get_work_entries_count(self, last_occupation_change_date):
        """
        Count the number of work entries for the employee since the last
        occupation change date.
        """
        self.ensure_one()
        date_to = fields.Date.context_today(self)
        work_entries_vals = self.filtered('resource_calendar_id').generate_work_entries(last_occupation_change_date, date_to)
        return len(work_entries_vals)

    def _get_seniority_change_date(self):
        """
        Reverse-compute the date on which the employee's current computed seniority level
        was first reached.  This date is used as `date_version` when creating a new version
        to adjust the wage to the minimum scale, so the version is back-dated to the moment
        the scale bracket actually changed rather than using today.
        """
        self.ensure_one()
        if (
            self.l10n_be_joint_committee_id.egov3_code == '302'
            and self.l10n_be_salary_scale_id
            and self.l10n_be_salary_scale_id.code.isnumeric()
            and int(self.l10n_be_salary_scale_id.code) <= 9
        ):
            return self._get_seniority_change_date_cp302()
        return self._get_seniority_change_date_cp200()

    def _get_seniority_change_date_cp302(self):
        """
        CP302 reverse-computation of the seniority change date.

        CDI / CREW (time-based):
            Uses last_occupation_change_date
            - seniority 0      -> False
            - seniority 1      -> adjusted_start + 6 months  (the 6-month trigger)
            - seniority N >= 2 -> adjusted_start + N years
            With base_seniority > 0: offset = seniority_years - base_seniority years.

        Temporary / Seasonal (work-entry based):
            Returns the date of the work entry that crossed the current seniority threshold.
            - seniority 0  -> False
            - seniority 1  -> date of entry at index first_threshold - 1
            - seniority N  -> date of entry at index
                              first_threshold + (N-1)*subsequent_threshold - 1
        """
        self.ensure_one()

        dates = list(filter(None, [
            self._get_field_block_start_date('l10n_be_salary_scale_id'),
            self.contract_date_start,
        ]))
        if not dates:
            return False
        last_occupation_change_date = min(dates)

        adjusted_start = last_occupation_change_date
        if adjusted_start.day != 1:
            adjusted_start = (adjusted_start + relativedelta(months=1)).replace(day=1)

        temporary_employee_type_id = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_temporary', raise_if_not_found=False).id
        seasonal_employee_type_id = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_seasonal', raise_if_not_found=False).id

        # Temporary / Seasonal
        if self.employee_type_id.id in (temporary_employee_type_id, seasonal_employee_type_id):
            seniority_years = int(self.l10n_be_computed_seniority_years)
            if not seniority_years:
                return False

            if self.employee_type_id.id == temporary_employee_type_id:
                first_threshold = 130
                subsequent_threshold = 260
            else:
                hours_per_week = self.resource_calendar_id.hours_per_week
                hours_per_day = self.resource_calendar_id.hours_per_day
                ratio = hours_per_week / hours_per_day if hours_per_day else 0
                amount_of_working_days_per_week = 5 if round(ratio) == 5 else 6
                first_threshold, subsequent_threshold = (130, 260) if amount_of_working_days_per_week == 5 else (156, 312)

            if seniority_years == 1:
                threshold_index = first_threshold - 1
            else:
                threshold_index = first_threshold + (seniority_years - 1) * subsequent_threshold - 1

            date_to = fields.Date.context_today(self)
            work_entries_vals = self.filtered('resource_calendar_id').generate_work_entries(
                last_occupation_change_date, date_to
            )
            if not work_entries_vals or threshold_index >= len(work_entries_vals):
                return False

            sorted_entries = sorted(work_entries_vals, key=lambda e: e['date'])
            entry_date = sorted_entries[threshold_index]['date']
            return entry_date.date() if isinstance(entry_date, datetime) else entry_date

        # CDI / CREW
        seniority_years = int(self.l10n_be_computed_seniority_years)
        base_seniority = self.l10n_be_base_computed_seniority or 0

        if not base_seniority:
            if not seniority_years:
                return False
            if seniority_years == 1:
                return adjusted_start + relativedelta(months=6)
            # Normal annual increment
            return adjusted_start + relativedelta(years=seniority_years)
        in_position_at_change = seniority_years - base_seniority
        if in_position_at_change <= 0:
            return adjusted_start
        return adjusted_start + relativedelta(years=in_position_at_change)

    def _get_seniority_change_date_cp200(self):
        """
        CP200 reverse-computation of the seniority change date.

        Student:
            seniority change date = birthday + current_age years

        Regular employee:
            seniority change date = first_version_date + company_seniority years
        """
        self.ensure_one()
        today = fields.Date.context_today(self)

        if self.l10n_be_dimona_category == 'stu':
            if not self.employee_id or not self.employee_id.birthday:
                return False
            age = relativedelta(today, self.employee_id.birthday).years
            if not age:
                return False
            return self.employee_id.birthday + relativedelta(years=age)

        first_contract_date = self.employee_id._get_first_contract_date() if self.employee_id else False
        if not first_contract_date:
            return False
        seniority_start_date = first_contract_date - relativedelta(
            years=self.l10n_be_scale_seniority or 0,
            months=self.l10n_be_scale_seniority_months or 0,
        )
        total_seniority = relativedelta(today, seniority_start_date).years
        if not total_seniority:
            return False
        return seniority_start_date + relativedelta(years=total_seniority)

    def _adjust_base_computed_seniority(self, new_salary_scale):
        """
        In this method, we need to adjust the base computed seniority when the salary scale is updated
        We need to check the employee's previous version minimum wage (hourly or monthly depending on the wage type)

        If the previous's version hourly wage (previous_salary_scale, years computed) is more than the new one (new_salary_scale, years 0)
        We need to find the minimum years of seniority in the new salary scale which guarantees a new hourly wage >= previous hourly wage
        """

        # To retrieve the previous occupation version, use self.employee_id.version_ids._get_occupation_dates() and then
        # retrieve the first tuple having a start date before the existing one (may be we need to retrieve the occupation date of the current version!).
        self.ensure_one()
        if int(new_salary_scale) > 9:
            # Only the first 9 salary scales have seniority levels
            return
        current_occuation_start_date = self._get_field_block_start_date('l10n_be_salary_scale_id')
        all_versions = self.employee_id.version_ids.filtered(lambda v: v.l10n_be_salary_scale_id).sorted(key=lambda v: v.contract_date_start or date.min, reverse=True)
        previous_version = self.env['hr.version']
        previous_version_start_date = current_occuation_start_date
        for version in all_versions:
            if version.contract_date_start < previous_version_start_date and version.l10n_be_salary_scale_id.code != new_salary_scale:
                previous_version = version
                previous_version_start_date = version.contract_date_start
                break
        if not previous_version or previous_version.l10n_be_joint_committee_id.egov3_code != '302':
            return  # No previous occupation

        previous_salary_scale = previous_version.l10n_be_salary_scale_id.code
        if not previous_salary_scale:
            return
        wage_type = 'monthly' if self.wage_type == 'monthly' and int(previous_salary_scale) > 3 and int(self.l10n_be_salary_scale_id.code) > 3 else 'hourly'
        previous_computed_seniority = previous_version.l10n_be_computed_seniority_years
        previous_parameter_rules = self.env['hr.rule.parameter']._get_parameter_from_code('cp302_salary_scales')[previous_salary_scale][wage_type]
        previous_wage = previous_parameter_rules[int(previous_computed_seniority)]

        current_parameter_rules = self.env['hr.rule.parameter']._get_parameter_from_code('cp302_salary_scales')[new_salary_scale][wage_type]

        seniority = 0
        for i, min_wage in current_parameter_rules.items():
            if min_wage >= previous_wage:
                seniority = i
                break
        self.l10n_be_base_computed_seniority = seniority

    def _get_public_transport_amount_302(self, field):
        self.ensure_one()
        if field not in ['bus', 'tram', 'metro']:
            raise NotImplementedError()
        amount = self[f'{field}_transport_employee_amount']
        periodicity = self[f'{field}_transport_periodicity']
        train_equivalent_amount_1km = self._get_train_equivalent_amount(1, 'monthly')
        train_equivalent_amount_16km = self._get_train_equivalent_amount(16, 'monthly')
        rate = 1 / 12 if periodicity == 'yearly' else 1
        return 0.8 * min(train_equivalent_amount_16km, max(train_equivalent_amount_1km, amount * rate))

    def _get_public_transport_amount_200(self, field):
        self.ensure_one()
        if field not in ['bus', 'tram', 'metro']:
            raise NotImplementedError()
        amount = self[f'{field}_transport_employee_amount']
        periodicity = self[f'{field}_transport_periodicity']
        kilometer = self[f'{field}_transport_employee_kilometer']
        rate = 1 / 12 if periodicity == 'yearly' else 1
        if periodicity == 'fixed':
            train_equivalent_amount_7km = self._get_train_equivalent_amount(7, 'monthly')
            return 0.718 * min(train_equivalent_amount_7km, amount)
        train_equivalent_amount = self._get_train_equivalent_amount(kilometer, periodicity)
        return min(train_equivalent_amount, 0.75 * amount) * rate

    def _get_l10n_be_min_wage(self):
        self.ensure_one()
        if not self.contract_date_start or self.country_code != 'BE':
            return 0, False, 0
        if self.employee_type_id.code == 'Apprenticeship':
            wage_type = 'monthly' if self._get_contract_wage_field() == 'wage' else 'hourly'
            min_wage = float_round(self._get_l10n_be_min_wage_apprenticeship(), 2)
            return min_wage, wage_type, self.l10n_be_computed_seniority_years

        current_date = fields.Date.context_today(self)
        flexi_hourly_wage = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_flexi_minimum_wage', current_date, raise_if_not_found=False) or 11.87
        if self.is_flexi():
            if self.wage_type == 'monthly':
                return round(flexi_hourly_wage * self.resource_calendar_id.hours_per_week * 52 / 12, 2), 'monthly', 0
            return flexi_hourly_wage, 'hourly', 0

        match self.l10n_be_joint_committee_id.egov3_code:
            case "302" if self.l10n_be_salary_scale_id and self.l10n_be_salary_scale_id.code.isnumeric() and int(self.l10n_be_salary_scale_id.code) <= 9:
                return self._get_l10n_be_min_wage_cp302()
            case "200":
                return self._get_l10n_be_min_wage_cp200()
            case _:
                return 0, False, 0

    def _get_latest_continuous_apprenticeship_period_start(self, date, contract_type):
        '''
        Returns the start date of the latest continuous apprenticeship period for the employee
        of the given contract type, up to the given date. If there is no such period, returns False.
        '''
        self.ensure_one()
        if not self.contract_date_start:
            return False
        versions = self.employee_id.version_ids.filtered(lambda v: v.date_start and v.date_start <= date).sorted('date_start', reverse=True)
        oldest_version = versions[:1]
        for version in versions:
            if version.employee_type_id.code != 'Apprenticeship' or version.l10n_be_apprenticeship_contract_type != contract_type:
                return oldest_version.contract_date_start
            oldest_version = version
        return oldest_version.contract_date_start

    def _get_apprenticeship_years(self, date):
        self.ensure_one()
        if not self.contract_date_start:
            return 0
        oldest_version = self._get_latest_continuous_apprenticeship_period_start(date, self.l10n_be_apprenticeship_contract_type)
        return relativedelta(date, oldest_version).years + 1

    def _get_l10n_be_min_wage_apprenticeship(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        RMMM = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_ref', raise_if_not_found=False)
        match self.l10n_be_apprenticeship_contract_type:
            case 'approved':
                training_year = self._get_apprenticeship_years(today)
                year_half = 'first' if today.month <= 6 else 'second'
                rates = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_rates_for_approved_apprentice', raise_if_not_found=False)
                training_year = min(training_year, max(rates.keys()))
                return rates.get(training_year, {}).get(year_half, 0.0)
            case 'business_manager':
                first_contract_date = self._get_latest_continuous_apprenticeship_period_start(today, 'business_manager')
                training_year = self._get_apprenticeship_years(today)
                rates = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_rates_for_business_manager_trainee', raise_if_not_found=False)
                rates = rates['old'] if first_contract_date and (
                    (self.l10n_be_working_region == 'wa' and first_contract_date < date(2023, 9, 1)) or
                    (self.l10n_be_working_region == 'br' and first_contract_date < date(2024, 9, 1))
                ) else rates['new']
                rate = rates['yes'] if self.employee_id.certificate else rates['no']
                return rate.get(min(training_year, max(rate.keys())), 0)
            case 'industrial':
                age = self.employee_id._get_age(today)
                rates = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_rates_for_industrial_apprenticeship_agreement', raise_if_not_found=False)
                return rates.get(min(age, max(rates.keys())), 0.0) * RMMM * 0.5
            case 'professional_immersion':
                age = self.employee_id._get_age(today)
                rates = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_rates_for_professional_immersion_agreement', raise_if_not_found=False)
                return float_round(rates.get(min(age, max(rates.keys())), 0.0) * RMMM * 0.5, precision_rounding=0.1, rounding_method='UP')
            case 'dual_learning':
                rates = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_rates_for_dual_learning_flemish_region_brussels', raise_if_not_found=False)
                return rates.get(self.l10n_be_apprenticeship_contract_subtype, 0.0) * RMMM
            case 'work_study':
                rates = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_apprenticeship_min_wage_rates_for_work_study_contract_walloon_region_brussels', raise_if_not_found=False)
                return rates.get(self.l10n_be_apprenticeship_contract_subtype, 0.0) * RMMM
            case _:
                return 0

    def _get_l10n_be_min_wage_cp302(self):
        self.ensure_one()
        wage_type = 'monthly' if self.wage_type == 'monthly' and int(self.l10n_be_salary_scale_id.code) > 3 else 'hourly'
        minimum_wage = self.env['hr.rule.parameter']._get_parameter_from_code('cp302_salary_scales')[self.l10n_be_salary_scale_id.code][wage_type][int(self.l10n_be_computed_seniority_years)]
        minimum_wage *= self.work_time_rate
        if self.l10n_be_dimona_category == 'stu':
            minimum_wage *= self._get_student_wage_rate()
        return minimum_wage, wage_type, self.l10n_be_computed_seniority_years

    def _get_student_wage_rate(self):
        self.ensure_one()
        if not self.employee_id.birthday:
            return 1.0
        today = date.today()
        age = self.employee_id._get_age(today)
        if age == 17:
            return 0.9
        if age == 16:
            return 0.8
        if age == 15:
            return 0.7
        return 1.0

    def _get_l10n_be_min_wage_cp200(self):
        self.ensure_one()
        if not self._get_below_scale_warning_applicable_versions():
            return 0, False, 0

        min_hourly_wage = -1
        today = fields.Date.context_today(self)
        date_to = self.date_start if self.date_start and self.date_start > today else today
        if self.l10n_be_dimona_category == 'stu':
            age = relativedelta(date_to, self.employee_id.birthday).years
            hours_per_week = self.resource_calendar_id.hours_per_week
            min_monthly_wage = self._get_student_min_wage(self.l10n_be_salary_scale_id.code, age, 'monthly', hours_per_week)
            scale_key = age
            if self.wage_type == 'hourly' and hours_per_week:
                min_hourly_wage = self._calculate_min_hourly_wage(min_monthly_wage, hours_per_week)
        else:
            if self.employee_id:
                company_seniority = relativedelta(date_to, self.employee_id._get_first_contract_date())
                seniority = self.l10n_be_scale_seniority + company_seniority.years + (company_seniority.months + self.l10n_be_scale_seniority_months) // 12
            else:
                company_seniority = 0
                seniority = 0
            hours_per_week = self.resource_calendar_id.hours_per_week
            min_monthly_wage = self._get_employee_min_wage(
                salary_scale=self.l10n_be_salary_scale_id.code,
                company_seniority=company_seniority.years,
                seniority=seniority,
                wage_type="monthly",
                hours_per_week=hours_per_week,
            )
            if self.wage_type == 'hourly' and hours_per_week:
                min_hourly_wage = self._calculate_min_hourly_wage(min_monthly_wage, hours_per_week)
            scale_key = seniority

        if min_monthly_wage == 0:
            return 0, False, 0

        work_time_rate = self.work_time_rate
        min_monthly_wage *= work_time_rate
        min_hourly_wage *= work_time_rate

        wage_field = self._get_contract_wage_field()
        wage_type = 'monthly' if wage_field == 'wage' else 'hourly'
        min_wage = min_monthly_wage if wage_type == 'monthly' else min_hourly_wage

        return min_wage, wage_type, scale_key

    def _get_public_transport_reimbursed_amount(self, field):
        self.ensure_one()
        if field not in ['bus', 'tram', 'metro']:
            raise NotImplementedError()
        amount_field = self[f'{field}_transport_employee_amount']
        if self.country_code != 'BE' or not amount_field:
            return 0
        code = self.l10n_be_joint_committee_id.egov3_code
        if code == '200':
            return self._get_public_transport_amount_200(field)
        return self._get_public_transport_amount_302(field)

    def _get_private_car_daily_amount(self, ref_date):
        self.ensure_one()
        kilometer = self.private_car_employee_kilometer
        cp_scales = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'private_car_daily_reimbursement', date=ref_date, raise_if_not_found=False,
        )
        daily_amount = 0.0
        if cp_scales:
            code = self.l10n_be_joint_committee_id.egov3_code
            km_scales = cp_scales.get(code)
            sorted_keys = sorted(km_scales.keys(), key=int)
            daily_amount = km_scales[sorted_keys[-1]]
            for km_threshold in sorted_keys:
                if kilometer <= int(km_threshold):
                    daily_amount = km_scales[km_threshold]
                    break
        return daily_amount

    def _get_private_car_reimbursed_amount(self):
        self.ensure_one()
        if self.country_code != 'BE' or not self.private_car_employee_kilometer:
            return 0
        code = self.l10n_be_joint_committee_id.egov3_code
        kilometer = self.private_car_employee_kilometer
        ref_date = self.env.context.get('payslip_date') or fields.Date.today()
        if code in ['200', '302'] and ref_date >= date(2026, 2, 1):
            daily_amount = self._get_private_car_daily_amount(ref_date=ref_date)
            return round(daily_amount * 21.67 * self.work_time_rate, 2)

        amount = 0
        train_equivalent_amount = self._get_train_equivalent_amount(kilometer)
        if (code == '200' or self.l10n_be_dimona_category == 'stu') and kilometer >= 3:
            amount = train_equivalent_amount * 0.5
        elif kilometer >= 1:
            amount = train_equivalent_amount * 0.7
        return amount

    def _get_bike_reimbursed_amount(self):
        self.ensure_one()
        if self.country_code != 'BE' or not self.bike_transport_employee_kilometer:
            return 0

        code = self.l10n_be_joint_committee_id.egov3_code
        if code == "200":
            rule_param_per_km = "cp200_cycle_reimbursement_per_km"
        elif code == "302":
            rule_param_per_km = "cp302_cycle_reimbursement_per_km"
        else:
            rule_param_per_km = "bike_reimbursement"

        cycle_reimbursement_per_km = self.env["hr.rule.parameter"].sudo()._get_parameter_from_code(
            rule_param_per_km, date=self.env.context.get("payslip_date"), raise_if_not_found=False) or 0
        amount = cycle_reimbursement_per_km * self.bike_transport_employee_kilometer * 2
        if code == '200':
            maximum_daily_amount = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'bike_max_reimbursement_daily_cp200', date=self.env.context.get('payslip_date'), raise_if_not_found=False) or 0
            amount = min(maximum_daily_amount, amount)
        return amount

    @api.onchange('transport_mode_car', 'private_car_employee_kilometer', 'train_transport_employee_kilometer',
        'bus_transport_employee_kilometer', 'tram_transport_employee_kilometer', 'metro_transport_employee_kilometer',
        'bike_transport_employee_kilometer', 'new_bike')
    def _onchange_transport_mode(self):
        if not self.transport_mode_car:
            self.company_car_total_depreciated_cost = 0
        for field in ['bus', 'tram', 'metro']:
            amount_field = f'{field}_transport_employee_amount'
            kilometer_field = f'{field}_transport_employee_kilometer'
            if self[kilometer_field] == 0:
                self[amount_field] = 0
        if self.transport_mode_car:
            self.private_car_employee_kilometer = 0
            self.has_bicycle = False
        else:
            self.car_id = False
        if self.transport_mode_bike:
            self.new_bike = False
            self.new_bike_model_id = False
        else:
            self.bike_id = False
        if self.sudo().car_id:
            self.private_car_employee_kilometer = False

    @api.model
    def _get_sacrifice_fields(self):
        return super()._get_sacrifice_fields() + ['l10n_be_group_insurance_rate']

    @api.depends('wage', 'l10n_be_group_insurance_rate')
    def _compute_l10n_be_group_insurance_amount(self):
        for version in self:
            rate = version.l10n_be_group_insurance_rate
            insurance_amount = version.wage * rate
            version.l10n_be_group_insurance_amount = insurance_amount
            # Example
            # 5 % salary configurator
            # 4.4 % insurance cost
            # 8.86 % ONSS
            # =-----------------------
            # 13.26 % over the 5%
            version.l10n_be_group_insurance_cost = insurance_amount * (1 + 13.26 / 100.0)

    def _get_yearly_cost_sacrifice_fixed(self):
        if self.company_id.country_code != "BE":
            return super()._get_yearly_cost_sacrifice_fixed()

        fixed = super()._get_yearly_cost_sacrifice_fixed()
        # add mobility budget
        fixed += self.l10n_be_mobility_budget_amount if self.l10n_be_mobility_budget else 0
        # add group insurance
        fixed += self._get_salary_costs_factor() * self.wage * self.l10n_be_group_insurance_rate
        # check if cafeteria plan is enable. If so substract net contribution from yearly_cost.
        cafeteria_benefit = self.env.ref(
            "l10n_be_hr_payroll.l10n_be_cafeteria_plan", raise_if_not_found=False
        )
        if cafeteria_benefit and cafeteria_benefit.active:
            net_contribution_fixed = self.l10n_be_cafeteria_plan_net_contribution * 12
            fixed -= net_contribution_fixed

        return fixed

    @api.depends('schedule_pay', 'no_onss', 'l10n_be_cafeteria_plan_net_contribution')
    def _compute_final_yearly_costs(self):
        return super()._compute_final_yearly_costs()

    def _get_salary_costs_factor(self):
        self.ensure_one()
        res = super()._get_salary_costs_factor()
        if self.structure_type_id == self.env.ref('hr.structure_type_employee_cp200'):
            res = 13.92
            if not self.no_onss:
                res += 13.0 * EMPLOYER_ONSS
        if self.l10n_be_group_insurance_rate:
            return res * (1.0 - self.l10n_be_group_insurance_rate)
        return res

    def _convert_gross_to_net_contribution(self, amount_gross) -> float:
        """
        Net contribution means that the gross is increased and it's compensated by the employee over the net salary.
        This method computes the amount of net needed to compensate an increase of gross salary.
        :return: amount_net
        """
        cost_factor = self._get_salary_costs_factor()
        pay_frequency = 12
        amount_net = amount_gross * cost_factor / pay_frequency
        return amount_net

    def _convert_net_contribution_to_gross(self, amount_net) -> float:
        """
        Inverse method of _convert_gross_to_net_contribution
        :return: amount_gross
        """
        cost_factor = self._get_salary_costs_factor()
        pay_frequency = 12
        amount_gross = amount_net / cost_factor * pay_frequency
        return amount_gross

    @api.depends(
        'l10n_be_has_ambulatory_insurance',
        'l10n_be_ambulatory_insured_adults',
        'l10n_be_ambulatory_insured_spouse')
    def _compute_ambulatory_insured_adults_total(self):
        for version in self:
            version.l10n_be_ambulatory_insured_adults_total = (
                int(version.l10n_be_has_ambulatory_insurance)
                + version.l10n_be_ambulatory_insured_adults
                + int(version.l10n_be_ambulatory_insured_spouse))

    @api.model
    def _get_ambulatory_insurance_amount(self, child_amount, child_count, adult_amount, adult_count):
        return child_amount * child_count + adult_amount * adult_count

    @api.depends('no_onss')
    def _compute_available_l10n_be_worker_status(self):
        all_types = {selection[0] for selection in self._get_l10n_be_worker_status()}
        no_onss_values = {'F1', 'F2'}
        onss_values = all_types - no_onss_values
        for version in self:
            if version.no_onss:
                version.available_l10n_be_worker_status = list(no_onss_values)
            else:
                version.available_l10n_be_worker_status = list(onss_values)

    @api.model
    def _get_l10n_be_worker_status(self):
        return [
            ('A1', self.env._("[A1] Artist with an employment contract")),
            ('A2', self.env._("[A2] Artist without an employment contract (article 1bis)")),
            ('B', self.env._("[B] Volunteer firefighters")),
            ('BA', self.env._("[BA] Worker employed outside the normal work circuit")),
            ('D', self.env._("[D] Home worker")),
            ('D1', self.env._("[D1] Home worker Childminder Flemish Community")),
            ('D2', self.env._("[D2] Home worker Childminder French Community")),
            ('D3', self.env._("[D3] Home worker Childminder German-speaking Community")),
            ('E', self.env._("[E] Staff of educational establishments declared in Dimona to a provincial or local administration")),
            ('F1', self.env._("[F1] Trainees with the occupational accident/professional illness compensation scheme for apprentices")),
            ('F2', self.env._("[F2] Trainees with an occupational accident/professional illness compensation scheme other than that for apprentices")),
            ('FE', self.env._("[FE] Foreign executive")),
            ('LP', self.env._("[LP] Workers with reduced hours")),
            ('MA', self.env._("[MA] Contractual mandates in a public service granted a pension supplement")),
            ('MN', self.env._("[MN] Ministers of religion who cannot marry")),
            ('MY', self.env._("[MY] Ministers of religion who can marry and lay council delegates")),
            ('PJ', self.env._("[PJ] Recognized professional journalist")),
            ('RM', self.env._("[RM] Reserve military personnel")),
            ('RS', self.env._("[RS] Holder of a lifeguard certificate")),
            ('S', self.env._("[S] Seasonal worker")),
            ('SA', self.env._("[SA] Professional technical and administrative staff of fire services")),
            ('SP', self.env._("[SP] Professional operational staff of fire services")),
            ('SS', self.env._("[SS] Judicial trainee")),
            ('SW', self.env._("[SW] Worker performing services as included in the law of May 3, 2024")),
            ('T', self.env._("[T] Temporary worker")),
            ('TS', self.env._("[TS] Temporary statutory worker in education paid by a community, a university, a higher education institution or a local or provincial administration")),
            ('TW', self.env._("[TW] Jobseeker temporary professional experience in the Flemish Region, engaged under article 60 § 7 of the organic law of CPAS of July 8, 1976")),
            ('VA', self.env._("[VA] Volunteer ambulance driver or Civil Security volunteer")),
        ]

    @api.model
    def _get_l10n_be_dimona_category_selection(self):
        return [
            ("oth", self.env._("[OTH] Other")),
            ("stu", self.env._("[STU] Student")),
            ("alt", self.env._("[ALT] Apprentice")),
            ("ext", self.env._("[EXT] Occasional Employee")),
            ("flx", self.env._("[FLX] Flexi-job")),
            ("ivt", self.env._("[IVT] Integration plan (job seeker)")),
            ("stg", self.env._("[STG] Intern without NSSO")),
            ("tri", self.env._("[TRI] Transition Intern (job seeker)")),
            ("dwd", self.env._("[DWD] No ONSS")),
            ("bcw", self.env._("[BCW] Construction Worker")),
            ("rta", self.env._("[RTA] Construction apprentice")),
            ("swo", self.env._("[SWO] Sex Worker")),
            ("s17", self.env._("[S17] Sport worker")),
            ("t17", self.env._("[T17] Television worker")),
            ("o17", self.env._("[O17] Socio cultural worker")),
            ("pmp", self.env._("[PMP] Parliamentarian")),
        ]

    @api.depends('employee_type_id.l10n_be_dimona_category')
    def _compute_l10n_be_dimona_category(self):
        for version in self:
            if version.company_id.country_id.code != 'BE':
                continue
            version.l10n_be_dimona_category = (version.employee_type_id.l10n_be_dimona_category if version.employee_type_id else None)\
                or version.l10n_be_dimona_category

    @api.depends(
        'l10n_be_ambulatory_insured_children', 'l10n_be_ambulatory_insured_adults_total',
        'l10n_be_ambulatory_amount_per_child', 'l10n_be_ambulatory_amount_per_adult')
    def _compute_ambulatory_insurance_amount(self):
        for version in self:
            version.l10n_be_ambulatory_insurance_amount = version._get_ambulatory_insurance_amount(
                version.l10n_be_ambulatory_amount_per_child,
                version.l10n_be_ambulatory_insured_children,
                version.l10n_be_ambulatory_amount_per_adult,
                version.l10n_be_ambulatory_insured_adults_total)

    @api.depends('l10n_be_mobility_budget_amount')
    def _compute_l10n_be_mobility_budget_amount_monthly(self):
        for version in self:
            version.l10n_be_mobility_budget_amount_monthly = version.l10n_be_mobility_budget_amount / 12

    @api.depends('l10n_be_dimona_category')
    def _compute_no_onss(self):
        for version in self:
            version.no_onss = version.l10n_be_dimona_category in ['dwd', 'o17', 's17', 't17', 'stg', 'tri']

    @api.model
    def _get_train_equivalent_amount(self, kilometer, periodicity='monthly'):
        train_table = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'train_reimbursement', date=self.env.context.get('payslip_date'), raise_if_not_found=False)
        if not train_table:
            return 0
        train_table_keys = sorted(train_table.keys())
        kilometer_key = train_table_keys[0]
        for train_km in train_table_keys:
            if kilometer >= train_km:
                kilometer_key = train_km
            else:
                break
        return train_table[kilometer_key][periodicity]

    @api.model
    def _generate_work_entries_postprocess_adapt_to_calendar(self, vals):
        res = super()._generate_work_entries_postprocess_adapt_to_calendar(vals)
        return res and not vals.get('l10n_be_is_time_credit')

    def _get_work_hours_split_half(self, date_from, date_to, work_entries_vals):
        """
        Returns, for each (work entry type, category options) pair, the number of days and the number of
        hours worked between two dates. If called on multiple contracts, sums the work amounts of each contract.

        For each date in the period, the work entries of that date are examined together to decide how the
        theoretical number of days (0, 0.5 or 1) of that date is distributed among them:
        - a single work entry on a date gets 0.5 or 1 day, depending on its duration compared to the theoretical
          number of hours for that date;
        - two work entries whose durations are equal and add up to the theoretical number of hours each get 0.5 day;
        - otherwise, any entry whose duration is exactly half the theoretical number of hours gets 0.5 day, then
          the "prevalent" entry (the working entry, or absence entry if there is none, with the lowest sequence)
          gets either 1 day (if strictly longer than every other entry, and no entry already got an exact half
          day) or 0.5 day (in which case the remaining entry with the highest duration gets the other 0.5 day).
          Every entry that received no day still contributes its duration in hours.
        :param date_from: The start date
        :param date_to: The end date
        :returns: a dictionary {(work_entry_type_id_1, options_1): [days_1, hours_1], (work_entry_type_id_2, options_2): [days_2, hours_2], ...}
        """

        def _add_work_data(work_data, we, number_of_days):
            work_data[we['work_entry_type_id'].id, we['options']][0] += number_of_days
            work_data[we['work_entry_type_id'].id, we['options']][1] += we['duration']

        date_from = datetime.combine(date_from, datetime.min.time())
        date_to = datetime.combine(date_to, datetime.max.time())
        work_data = defaultdict(lambda: [0, 0])  # {(work_entry_type, options): [days, hours]}

        hours_per_day = self.resource_calendar_id.hours_per_day
        calendar = self.resource_calendar_id
        # A full day is the number of hours actually scheduled on that specific day, so a full day
        # off on a shorter day (e.g. 4h instead of the usual 8h) is not counted as half a day.
        default_hours_full_day = hours_per_day if calendar.attendance_ids else 0
        hours_per_dayofweek = {}
        if calendar.calendar_type == 'fixed':
            hours_per_dayofweek = dict(
                self.env['resource.calendar.attendance']._read_group(
                    [('calendar_id', '=', calendar.id)],
                    ['dayofweek'],
                    ['duration_hours:sum'])
            )

        # YTI clean this nightmare
        version_ids = set(self.ids)
        date_from = date_from.date()
        date_to = date_to.date()
        filtered_work_entries = [
            work_entry_vals for work_entry_vals in work_entries_vals
            if work_entry_vals['version_id'].id in version_ids
            and date_from <= work_entry_vals['date'] <= date_to
        ]
        work_entries = defaultdict(list)
        # work_entries = {date: [
        #   (work_entry_type_1, options_1, duration_1),
        #   (work_entry_type_2, options_2, duration_2),
        # ]}
        for work_entry_vals in filtered_work_entries:
            work_entries[work_entry_vals['date']].append({
                'work_entry_type_id': work_entry_vals['work_entry_type_id'],
                'options': work_entry_vals.get('category_options_ids', self.env['hr.salary.rule.category']).sorted(),
                'duration': work_entry_vals['duration']
            })

        for entry_date, work_entry_data in work_entries.items():

            if calendar.calendar_type == 'fixed':
                number_of_hours_full_day = hours_per_dayofweek.get(str(entry_date.weekday()), default_hours_full_day)
            else:
                number_of_hours_full_day = sum(
                    calendar.attendance_ids._filter_by_date(entry_date).mapped('duration_hours')
                ) or default_hours_full_day

            number_of_work_entries_for_date = len(work_entry_data)
            if number_of_work_entries_for_date == 1:
                # If we only have one work entry for a given date, the number of hours is the duration of the work entry
                # and the number of days is 1 or 0.5 depending on the theoretical number of hours per day
                # Ex: 7.6h attendance
                work_entry_duration = work_entry_data[0]['duration']
                number_of_days = float_round(work_entry_duration / number_of_hours_full_day, precision_rounding=0.5, rounding_method='HALF-UP') if number_of_hours_full_day else 1
                _add_work_data(work_data, work_entry_data[0], number_of_days)
                continue

            elif number_of_work_entries_for_date == 2:
                # If we have two work entries for a given date, we first check the easy case where the total duration is
                # the theoretical number of hours per day and they have the same duration. In that case, 0.5 days is assigned to each
                # Ex: 3.8h attendance 3.8h time off
                total_duration_for_date = sum(we['duration'] for we in work_entry_data)
                is_equal_to_hours_per_day = float_compare(total_duration_for_date, number_of_hours_full_day, 2) == 0
                are_both_durations_equal = float_compare(work_entry_data[0]['duration'], work_entry_data[1]['duration'], 2) == 0
                if is_equal_to_hours_per_day and are_both_durations_equal:
                    for we in work_entry_data:
                        _add_work_data(work_data, we, 0.5)
                    continue

            # For remaining entries, first assign half day for entries that have a duration equal to exactly the number
            # of hours per day / 2
            exact_half_days = [we for we in work_entry_data if float_compare(we.get('duration'), number_of_hours_full_day / 2, 2) == 0]
            for exact_half_day in exact_half_days:
                _add_work_data(work_data, exact_half_day, 0.5)

            # Separate working entries and absence entries
            working_time_entries, absence_entries = (
                [d for d in work_entry_data if
                    d not in exact_half_days
                    and d['work_entry_type_id'].count_as == k]
                for k in ('working_time', 'absence')
            )

            if not working_time_entries and not absence_entries:
                # Should not happen but just in case, nothing left to process
                continue

            if working_time_entries:
                prevalent_work_entry = min(working_time_entries, key=lambda d: d['work_entry_type_id'].sequence)
            else:
                prevalent_work_entry = min(absence_entries, key=lambda d: d['work_entry_type_id'].sequence)

            other_entries = [e for e in working_time_entries + absence_entries if e != prevalent_work_entry]

            # If we don't have exact half day and that the prevalent work entry is of a higher duration than all other
            # entries, it is considered as the only full day. The others will have 0 days
            prevalent_number_of_days = 1.0 if all(
                float_compare(prevalent_work_entry['duration'], e['duration'], 2) > 0 for e in other_entries
            ) and not exact_half_days else 0.5
            _add_work_data(work_data, prevalent_work_entry, prevalent_number_of_days)

            # If the prevalent was decided as a half day, we should compute which entry will have the other half.
            # We take the next entry with the highest duration
            other_half = False
            if float_compare(prevalent_number_of_days, 0.5, 1) == 0 and not exact_half_days:
                other_half = max(other_entries, key=lambda e: e['duration'])
                _add_work_data(work_data, other_half, 0.5)

            # For the remaining entries, we don't have any more days to distribute. We simply encode them with their duration
            for work_entry in [e for e in other_entries if e != other_half]:
                work_data[work_entry['work_entry_type_id'].id, work_entry['options']][1] += work_entry['duration']

        return work_data

    # override to add work_entry_type from leave
    def _get_leave_work_entry_type_dates(self, leave, date_from, date_to, employee):
        result = super()._get_leave_work_entry_type_dates(leave, date_from, date_to, employee)
        if not self._is_struct_from_country('BE'):
            return result

        if result.code == "006.00":
            # The public holidays are paid only during the 14 first days of unemployment
            public_holiday_during_unemployment = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('request_date_to', '>=', date_from.date()),
                ('request_date_from', '<=', date_from.date()),
                ('work_entry_type_id.code', '=', '006.11'),
                ('state', '=', 'validate'),
            ], limit=1)
            if public_holiday_during_unemployment:
                return self.env.ref('hr_work_entry.l10n_be_work_entry_type_public_holiday_temporary_unemployment')

            economic_unemployments = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('request_date_to', '>=', date_to.date()),
                ('request_date_from', '<=', date_from.date()),
                ('work_entry_type_id.code', 'in', ['137.20', '137.00']),
                ('state', '=', 'validate'),
            ], limit=1)
            if economic_unemployments and not self.is_worker():
                return self.env.ref('hr_work_entry.l10n_be_work_entry_type_temporary_economic_unemployement_employee')
            if economic_unemployments and self.is_worker():
                return self.env.ref('hr_work_entry.l10n_be_work_entry_type_economic_unemployment')
            # The public holidays are paid only during the period of 30 days following the start of the
            # suspension of the employment contract due to illness or accident, work accident or
            # occupational disease, pregnancy or childbirth leave, strike or lockout;
            # Sickness is often certified month by month, one hr.leave record per certificate.
            # Compare local calendar dates, not the raw UTC instant.
            # Otherwise a leave starting the same local day as the holiday gets wrongly excluded.
            # Use hr.leave's own request_date_from/request_date_to, already local dates.
            # Do not re-derive a local date from the UTC date_from/date_to datetime fields.
            leave_tz = ZoneInfo(leave.resource_id.tz or leave.company_id.tz or 'UTC')
            leave_date = leave.date_from.replace(tzinfo=UTC).astimezone(leave_tz).date()
            absent_less_than_X_days_before = self.env['hr.leave'].search([
                ('employee_id', '=', self.employee_id.id),
                ('request_date_to', '>=', leave_date + relativedelta(days=-30)),
                ('request_date_from', '<=', leave_date),
                ('work_entry_type_id.code', 'in', [
                    '128.00', '007.05', '128.05', '009.00', '122.04', '123.00', '013.00', '122.00'
                ]),
                ('state', '=', 'validate'),
            ], order="request_date_from asc")
            current_absence = absent_less_than_X_days_before.filtered_domain([
                ('request_date_from', '<=', leave_date),
                ('request_date_to', '>=', leave_date),
            ])[-1:]
            # Use all absences to check whether the employee was continuously absent.
            # Use the current absence to determine the public holiday's work entry type.
            if current_absence:
                unpaid_work_entry_type = current_absence.work_entry_type_id
                if unpaid_work_entry_type.code == '013.00':
                    unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period', False)
                is_absent = True
                paid_duration = 30
                for offset in range(paid_duration):
                    day = leave_date + relativedelta(days=-offset)
                    if all(l.request_date_from > day or l.request_date_to < day for l in absent_less_than_X_days_before):
                        is_absent = False
                if is_absent:
                    return unpaid_work_entry_type

        # The salary is not guaranteed after 30 calendar days of sick leave (it means from the 31th day of sick leave)
        # This is present here for legacy support and can be removed in the future.
        # For newly created leaves, the leaves are directly split correctly upon creation.
        if result.code in ('013.00', '122.00'):
            if not leave.holiday_id:
                return result

            sick_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_sick_leave')
            partial_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')
            long_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_long_sick')
            sick_work_entry_types = sick_work_entry_type + partial_sick_work_entry_type + long_sick_work_entry_type

            cutoff_date = leave.holiday_id._get_l10n_be_long_term_sick_cutoff_date()
            if date_from.date() >= cutoff_date:
                return long_sick_work_entry_type

            if result.code == '122.00':
                return result

            current_leave_duration = (date_from - leave.holiday_id.date_from).days + 1
            if current_leave_duration > 30:
                return partial_sick_work_entry_type

            if not leave.holiday_id.l10n_be_sickness_relapse:
                return result

            all_sick_leaves = self.env["hr.leave"].search(
                [
                    ("employee_id", "=", self.employee_id.id),
                    ("date_from", "<", leave.date_from),
                    ("work_entry_type_id", "in", sick_work_entry_types.ids),
                    ("state", "=", "validate"),
                ],
                order="date_from desc",
            )

            prev_leaves_sum = current_leave_duration

            for sick_leave in all_sick_leaves:
                prev_leaves_sum += (sick_leave.date_to - sick_leave.date_from).days + 1
                if prev_leaves_sum > 30:
                    return partial_sick_work_entry_type
                if not sick_leave.l10n_be_sickness_can_relapse or not sick_leave.l10n_be_sickness_relapse:
                    return result

        return result

    def _get_bypassing_work_entry_type_codes(self):
        return super()._get_bypassing_work_entry_type_codes() + [
            '123.00',  # Long term sick
            '122.04',  # Partial Incapacity
            '147.05',  # Parental Time Off
            '147.00',  # Time credit
            '158.00',   # Unpaid Time Off
            # '013.00', # Sick Leave - Actually Sick Leave < Public Time Off
                          # If the employee does not have to work on a public
                          # holiday but falls ill when he could have benefited
                          # from a well-deserved day off, he is not entitled to
                          # a guaranteed salary but to remuneration in accordance
                          # with the days holidays. In fact, the employee is
                          # entitled to remuneration for each public holiday falling
                          # within 30 calendar days of the onset of his illness.
            '006.11',
            '086.00',
        ]

    def _is_same_occupation(self, version):
        self.ensure_one()
        res = super()._is_same_occupation(version)
        time_credit_type = self.resource_calendar_id.attendance_ids.work_entry_type_id.filtered('l10n_be_is_time_credit')
        version_time_credit_type = version.resource_calendar_id.attendance_ids.work_entry_type_id.filtered('l10n_be_is_time_credit')
        is_starterjob = self.l10n_be_is_starterjob
        return res \
            and self.l10n_be_time_credit == version.l10n_be_time_credit \
            and time_credit_type == version_time_credit_type \
            and self.l10n_be_joint_committee_id == version.l10n_be_joint_committee_id \
            and is_starterjob == version.l10n_be_is_starterjob

    def is_worker(self):
        self.ensure_one()
        workers_worker_codes = self.env["hr.rule.parameter"]._get_parameter_from_code('l10n_be_workers_worker_codes', raise_if_not_found=False)
        if not workers_worker_codes:
            return False
        return self.l10n_be_worker_code_id and\
            self.l10n_be_worker_code_id.dmfa_code in workers_worker_codes

    def is_employee(self):
        self.ensure_one()
        employees_worker_codes = self.env["hr.rule.parameter"]._get_parameter_from_code('l10n_be_employees_worker_codes', raise_if_not_found=False)
        if not employees_worker_codes:
            return False
        return self.l10n_be_worker_code_id and\
            self.l10n_be_worker_code_id.dmfa_code in employees_worker_codes

    def is_short_term_contract(self):
        self.ensure_one()
        if not self.fixed_term:
            return False
        if not self.contract_date_start or not self.contract_date_end:
            return False
        return self.contract_date_end < self.contract_date_start + relativedelta(months=3, days=-1)

    def _l10n_be_is_eligible_for_acs_deduction(self):
        self.ensure_one()
        return (
            self.company_id.country_code == 'BE' and
            self.l10n_be_worker_code_id.dmfa_code in ['024', '025', '029', '484', '485'] and
            self.l10n_be_working_region == 'br'
        )

    def is_student(self):
        self.ensure_one()
        return self.l10n_be_dimona_category == 'stu'

    def is_PFI(self):
        self.ensure_one()
        return self.l10n_be_dimona_category == 'ivt'

    def is_flexi(self):
        self.ensure_one()
        return self.l10n_be_dimona_category == 'flx' and not self.l10n_be_refused_flexijob

    def is_classic_employee(self):
        return not self.is_student() and not self.is_PFI() and not self.is_flexi()

    def _should_apply_onss_activation(self):
        return self.l10n_be_work_exemption in ['2', '7']

    def _get_contract_insurance_amount(self, name):
        self.ensure_one()
        if name == 'hospital':
            return self._get_hospital_insurance_amount() - self.hospital_insurance_employee_contribution
        if name == 'ambulatory':
            return self.l10n_be_ambulatory_insurance_amount - self.l10n_be_ambulatory_insurance_employee_contribution
        if name == 'group':
            if self.l10n_be_group_insurance_company_contribution_unit == 'amount':
                return self.l10n_be_group_insurance_company_contribution
            return self.l10n_be_group_insurance_amount * (self.l10n_be_group_insurance_company_contribution / 100.0)
        return 0.0

    def _get_hospital_insurance_amount(self):
        self.ensure_one()
        return self.insurance_amount

    def _get_fields_that_recompute_payslip(self):
        # Returns the fields that should recompute the payslip
        return super()._get_fields_that_recompute_payslip() + [
            'ip_wage_rate',
            'ip_artist',
            'ip_onss',
            'l10n_be_child_bonus',
            'mobile',
            'mobile_amount',
            'internet',
            'transport_mode_car',
            'train_transport_employee_kilometer',
            'train_transport_periodicity',
            'bus_transport_employee_amount',
            'bus_transport_employee_kilometer',
            'bus_transport_periodicity',
            'tram_transport_employee_amount',
            'tram_transport_employee_kilometer',
            'tram_transport_periodicity',
            'metro_transport_employee_amount',
            'metro_transport_employee_kilometer',
            'metro_transport_periodicity',
            'bike_transport_employee_kilometer',
            'private_car_employee_kilometer',
            'distance_home_work',
            'distance_home_work_unit',
            'km_home_work',
            "laptop",
            "tablet",
            'meal_voucher_amount',
            'meal_voucher_calculation_method',
            'meal_voucher_employee_share',
            'work_time_rate',
            'no_onss',
            'no_withholding_taxes',
            'l10n_be_resident_situation',
            'car_id',
        ]

    def _get_holiday_pay_tax_provision_prorata(self, start_date, end_date):
        """
        Flexi-jobs are paid their holiday pay directly, except for the days covered
        by Dimona occupations "Accepted with Warnings", which are treated as a
        regular occupation for the holiday pay tax provision.
        """
        self.ensure_one()
        periods = self.env['l10n.be.dimona.period'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('date_start', '!=', False),
            ('date_start', '<=', end_date),
            '|', ('date_end', '=', False), ('date_end', '>=', start_date),
        ])
        if not periods:
            return 0.0

        total_days = 0
        anomaly_days = 0
        for period in periods:
            overlap_start = max(period.date_start, start_date)
            overlap_end = min(period.date_end or end_date, end_date)
            if overlap_start > overlap_end:
                continue
            days = (overlap_end - overlap_start).days + 1
            total_days += days
            if 'W' in period.declaration_ids.mapped('state'):
                anomaly_days += days

        return anomaly_days / total_days if total_days else 0.0

    @api.depends('l10n_be_mobility_budget')
    def _compute_l10n_be_mobility_budget_amount(self):
        for version in self:
            if version.l10n_be_mobility_budget:
                version.l10n_be_mobility_budget_amount = version._get_mobility_budget_amount(inverse=False)[1]
            else:
                version.l10n_be_mobility_budget_amount = 0

    def _get_mobility_budget_amount(self, inverse=True):
        self.ensure_one()

        if inverse:
            return self.wage, self.l10n_be_mobility_budget_amount

        today = fields.Date.context_today(self)
        mobility_budget_max = self.env['hr.rule.parameter']._get_parameter_from_code(
            "mobility_budget_max", today, raise_if_not_found=False) or 16875
        mobility_budget_min = self.env['hr.rule.parameter']._get_parameter_from_code(
            "mobility_budget_min", today, raise_if_not_found=False) or 3164

        wage = self.wage
        if not self.l10n_be_mobility_budget:
            return wage, 0.0

        mobility_budget = max(min(self._get_mobility_budget_cost(wage), mobility_budget_max), mobility_budget_min)
        return wage, mobility_budget

    def _get_mobility_budget_cost_ratio(self):
        """ 12 months
            + 13e month
            - simple holiday allowance (20 days/4 weeks ≃ 0.92 month) """
        self.ensure_one()
        return 13 - 0.92

    def action_work_schedule_change_wizard(self):
        if len(self) != 1:
            raise UserError(self.env._("This feature can only be used on a single contract."))
        if not self.contract_date_start:
            raise UserError(self.env._('This feature can only be used on versions that have a contract start date'))
        if not self.is_current:
            return False
        action = self.env['ir.actions.actions']._for_xml_id('l10n_be_hr_payroll.schedule_change_wizard_action')
        action['context'] = {'active_id': self.id}
        return action

    def _get_l10n_be_holiday_attest_worked_days(self, date_from, date_to):
        payslips = self.env['hr.payslip'].search([
            ('version_id', 'in', self.ids),
            ('date_from', '>=', date_from + relativedelta(day=1)),
            ('date_to', '<=', date_to + relativedelta(day=31)),
            ('state', 'in', ['validated', 'paid'])
        ])

        worked_lines = payslips.worked_days_line_ids

        all_days = 0
        senior_youth_leaves = 0
        european_leaves = 0
        paid_leaves = 0
        non_equivalent_days = 0
        european_leaves_amount = 0
        non_equivalent_codes = self.env['hr.work.entry.type'].search([('category_ids.code', '=', 'UNASSIMILATED')]).mapped('code')

        for wd in worked_lines.filtered(lambda wd: wd.code != '000.00'):
            all_days += wd.number_of_days
            if wd.code == "142.99":
                senior_youth_leaves += wd.number_of_days
            elif wd.code == "142.20":
                european_leaves += wd.number_of_days
                european_leaves_amount += wd.amount
            elif wd.code == "016.00":
                paid_leaves += wd.number_of_days
            if wd.code in non_equivalent_codes:
                non_equivalent_days += wd.number_of_days

        equivalent_days = all_days - non_equivalent_days - senior_youth_leaves - european_leaves

        return {
            'equivalent_days': equivalent_days,
            'senior_youth_leaves': senior_youth_leaves,
            'european_leaves': european_leaves,
            'paid_leaves': paid_leaves,
            'non_equivalent_days': non_equivalent_days,
            'european_leaves_amount': european_leaves_amount,
        }

    def _get_dimona_api_routes(self):
        routes = API_DATA['routes'].get(self.company_id.l10n_be_dimona_environment)
        if not routes:
            raise UserError(self.env._(
                'The Dimona declarations of %(company)s are not filed over the ONSS REST API.',
                company=self.company_id.name))
        return routes

    def _l10n_be_dimona_can_declare(self):
        """Whether Dimona declarations can be filed for this version."""
        self.ensure_one()
        return self.company_id._l10n_be_dimona_can_declare(self.payroll_config_id)

    def _validate_dimona_response(self, key, response):
        response_json = response.json()
        expected_format = API_DATA['response_validation'][key]['response']
        TYPE_MAP = {
            "str": str,
            "int": int,
            "list": list,
            "dict": dict,
            "float": float,
            "bool": bool,
        }
        if response.status_code != API_DATA['response_validation'][key]['status']:
            return response_json
        if len(response_json) != len(expected_format):
            raise UserError(self.env._(' The API response is not in the expected format. Please contact an administrator.'))
        for field, field_type in expected_format.items():
            if field not in response_json:
                raise UserError(self.env._(' The API response is not containing the required fields. Please contact an administrator.'))
            if not isinstance(response_json[field], TYPE_MAP[field_type]):
                raise UserError(self.env._(' The API response have an unexpected type. Please contact an administrator.'))
        return response_json

    def _get_dimona_jwt(self, company):
        expeditor_number = company.onss_expeditor_number
        if not expeditor_number:
            raise UserError(self.env._('No expeditor number defined on the payroll settings.'))
        if expeditor_number.isdigit():
            expeditor = API_DATA['jwt']['user'] % (company.onss_expeditor_number)
        else:
            expeditor = expeditor_number
        certificate_sudo = company.sudo().onss_certificate_id
        if not certificate_sudo:
            raise UserError(self.env._('No Certificate defined on the Payroll Configuration'))
        if not self.l10n_be_dimona_category:
            raise UserError(self.env._('The DIMONA category is missing for employee %s. Please set it before opening a DIMONA declaration.', self.employee_id.name))
        unique_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
        now = int(time.time())
        payload = {
            # Unique jwt indentifier
            "jti": unique_id,
            # App supplying the jwt
            "iss": expeditor,
            # Main jwt subject
            "sub": expeditor,
            # jwt receiver (audience)
            "aud": API_DATA['jwt']['audiance'],
            # Expiration
            "exp": now + API_DATA['jwt']['expires_in'],
            # Timestamp before accepting jwt
            "nbf": now,
            # Creation timestamp
            "iat": now,
        }
        try:
            pem_key = certificate_sudo.private_key_id.pem_key.content
            password = certificate_sudo.private_key_id.password.content

            private_key = serialization.load_pem_private_key(
                pem_key,
                password=password.encode() if password else None,
            )

            bearer_token = jwt.encode(payload, private_key, algorithm="RS256")

        except ValueError as e:
            raise UserError(self.env._('Error on authentication. Please contact an administrator. (%s)', e))
        except AttributeError:
            raise UserError(self.env._('The ONSS Certificate has an incorrect format or is missing required components (private key or password).'))
        return bearer_token

    def _dimona_authenticate(self, company, declare=True):
        bearer = self._get_dimona_jwt(company)
        data = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'scope': 'scope:dimona:declaration:declarant' if declare else 'scope:dimona:declaration:consult',
            'client_assertion': bearer,
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        try:
            response = request(**self._get_dimona_api_routes()['authentification'], data=data, headers=headers, timeout=DIMONA_TIMEOUT)
        except HTTPError as e:
            raise UserError(self.env._('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
        if response.status_code == 200:
            return self._validate_dimona_response('authentification', response)['access_token']
        if response.status_code == 400:
            raise UserError(self.env._('Error with one or several invalid parameters on the POST request during authentication. Please contact an administrator. (%s)', response.text))
        if response.status_code == 500:
            raise UserError(self.env._('Due to a technical problem at the ONSS side, the authentication could not be done by the ONSS.'))
        response.raise_for_status()

    def _dimona_declaration(self, data):
        self.ensure_one()
        result = self._dimona_send(data)
        return self._dimona_register(data, result)

    def _dimona_send(self, data):
        """Hand `data` over to the ONSS and return the reference it answers with."""
        self.ensure_one()
        if self.company_id.l10n_be_dimona_environment == 'sandbox':
            # sandbox: send nothing, just generate a random reference
            timestamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S')
            return f"{timestamp}{random.randint(100, 999)}"

        access_token = self._dimona_authenticate(self.company_id)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = request(**self._get_dimona_api_routes()['push_declaration'], json=data, headers=headers, timeout=DIMONA_TIMEOUT)
        except HTTPError as e:
            raise UserError(self.env._('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))

        if response.status_code == 201:
            return response.headers['Location'].split('/')[-1]

        if response.status_code == 400:
            raise UserError(self.env._('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
        if response.status_code == 401:
            raise UserError(self.env._('The authentication token is invalid. Please contact an administrator. (%s)', response.text))
        if response.status_code == 403:
            raise UserError(self.env._('Your user does not have the rights to make a declaration for the employer. This happens, for example, if the user does not have or no longer has a mandate for the employer. (%s)', response.text))
        if response.status_code == 500:
            raise UserError(self.env._('Due to a technical problem at the ONSS side, the Dimona declaration could not be received by the ONSS.'))
        response.raise_for_status()

    def _dimona_register(self, data, reference=False, **vals):
        """Keep a record of the declaration `data` this version just handed over."""
        self.ensure_one()
        declaration = self.env['l10n.be.dimona.declaration'].create({
            'name': reference,
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'company_id': self.company_id.id,
            'request_content': data,
            **vals,
        })
        self.l10n_be_last_dimona_declaration_id = declaration
        if 'dimonaIn' in data:
            self.l10n_be_dimona_declaration_id = declaration
        self.employee_id.message_post(body=self._dimona_registered_message(declaration))
        self._dimona_after_register(declaration)
        return declaration

    def _dimona_registered_message(self, declaration):
        return self.env._('DIMONA declaration posted successfully, waiting validation')

    def _dimona_after_register(self, declaration):
        self.env.ref('l10n_be_hr_payroll.ir_cron_check_dimona')._trigger(fields.Datetime.now() + timedelta(minutes=1))

    def _fake_dimona_response(self, dimonaType, status='A'):
        return {
            "Location": "foo/bar/blork/123456778",
            "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/9876540",
            "worker": {
                "ssin": self.employee_id.niss,
                "gender": self.sex,
                "birthDate": "1991-07-28",
                "givenName": "Test",
                "familyName": "test",
                "givenNames": "test",
                "nationality": 150
            },
            dimonaType: {
                "features": {"workerType": "OTH", "jointCommissionNumber": "XXX"},
                "startDate": "2025-12-01"
            },
            "employer": {"employerId": 123456, "enterpriseNumber": "123456"},
            "declarationStatus": {
                "period": {"id": 9876540, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/9876540"},
                "result": status,
                "declarationId": 9876540
            }
        }

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + ['l10n_be_onss_reduction_unexperienced_employees_flander'] + ['employee_id.birthday'] + ['l10n_be_dimona_next_action']

    def _l10n_be_dimona_issues(self, declaration_type, foreigner=False):
        """Everything that stops this version from filing this Dimona declaration."""
        self.ensure_one()
        issues = []
        if declaration_type in ('in', 'update') and not self.l10n_be_dimona_category:
            issues.append(self.env._('- The DIMONA category is missing for employee %s', self.employee_id.name))
        if declaration_type == 'in':
            if not self.payroll_config_id.onss_registration_number and self.company_id.l10n_be_dimona_environment != 'sandbox':
                issues.append(self.env._('- No ONSS registration number is defined for company %s', self.company_id.name))
            if self.l10n_be_dimona_declaration_id and self.l10n_be_dimona_declaration_id.state != 'B':
                issues.append(self.env._('- There is already a IN declaration for this contract.'))
            if not foreigner and not self.employee_id._is_niss_valid():
                issues.append(self.env._('- The NISS is invalid.'))

            first_name, last_name = self.employee_id._get_split_name()
            if not first_name or not last_name:
                issues.append(self.env._('- The employee name is incomplete'))

            if foreigner and not all(self.employee_id[field] for field in ['birthday', 'place_of_birth', 'country_of_birth', 'country_id', 'sex']):
                issues.append(self.env._("- Foreigner employees should provide their name, birthdate, birth place, birth country, nationality and sex"))
            if foreigner and not all(self.employee_id[f'private_{field}'] for field in ['street', 'zip', 'city', 'country_id']):
                issues.append(self.env._("- Foreigner employees should provide a complete address (street, number, zip, city, country)"))
            if not foreigner and self.private_zip not in API_DATA['data']['municipality_by_postal_code']:
                issues.append(self.env._("- The employee zip does not exist."))
            if not self.employee_id.sex:
                issues.append(self.env._("- The employee sex is not specified."))
            if self.private_street and not re.findall(r"[0-9]+", self.private_street):
                issues.append(self.env._('- No house number found on employee street'))

            if self.l10n_be_dimona_category == 'stu':
                if not self.l10n_be_dimona_planned_hours:
                    issues.append(self.env._('- There is no defined planned hours on the student contract.'))
                if not self.date_end:
                    issues.append(self.env._('- There is no defined end date on the student contract.'))
                elif (self.date_end.month - 1) // 3 + 1 != (self.date_start.month - 1) // 3 + 1:
                    issues.append(self.env._('- Start date and end date should belong to the same quarter.'))
                if self.date_start < fields.Date.context_today(self):
                    issues.append(self.env._('- The DIMONA should be introduced before start date for students.'))
        elif declaration_type == 'out':
            if not self.contract_date_end:
                issues.append(self.env._('- There is not end date defined on the employee contract.'))
            if self._l10n_be_dimona_already_declared('dimona_out'):
                issues.append(self.env._('- A DIMONA departure has already been filed for this period.'))
        elif declaration_type == 'cancel' and self._l10n_be_dimona_already_declared('dimona_cancel'):
            issues.append(self.env._('- This DIMONA period has already been cancelled.'))
        return issues

    def _l10n_be_dimona_autodeclare(self):
        """File whatever each version owes, reporting problems instead of raising.

        Unlike the buttons, this runs from write() -- including the contract-date writes
        performed while an employee is being created -- so incomplete data must not abort
        the save. It is reported where the user is looking instead: the "issue" badge, and
        the reason in the employee's chatter.

        Returns {version id: [issues]} for whatever it could not file.
        """
        blocked = {}
        for version in self:
            niss = version.employee_id.niss
            if not niss or niss == '/' or not version._l10n_be_dimona_can_declare():
                continue
            for declaration_type, flag in (
                ('in', 'l10n_be_needs_dimona_in'),
                ('out', 'l10n_be_needs_dimona_out'),
                ('update', 'l10n_be_needs_dimona_update'),
                ('cancel', 'l10n_be_needs_dimona_cancel'),
            ):
                if not version[flag] or not version._l10n_be_dimona_should_autodeclare(declaration_type):
                    continue
                if issues := version._l10n_be_dimona_issues(declaration_type):
                    blocked.setdefault(version.id, []).extend(issues)
                    version.l10n_be_dimona_next_action = 'issue'
                    version.employee_id.message_post(body=self.env._(
                        'The DIMONA declaration could not be prepared:\n%s', '\n'.join(issues)))
                    continue
                version._dimona_declaration(version._l10n_be_dimona_payload(declaration_type))
                version.l10n_be_dimona_next_action = 'progress'
        return blocked

    def _l10n_be_dimona_should_autodeclare(self, declaration_type):
        """Whether the automatic path may file this declaration now.

        A channel whose answers come back asynchronously has reasons to hold a follow-up
        back that are not problems to report: the period the entrance opened may not be
        named yet. Waiting is not an issue, so it must not raise the badge.
        """
        return True

    def _l10n_be_dimona_check(self, declaration_type, foreigner=False):
        if issues := self._l10n_be_dimona_issues(declaration_type, foreigner=foreigner):
            raise UserError('\n'.join(issues))

    def _l10n_be_dimona_payload(self, declaration_type, foreigner=False):
        """The declaration this version owes, in the shape the ONSS expects."""
        self.ensure_one()
        if declaration_type == 'out':
            return {
                "dimonaOut": {
                    "periodId": self.l10n_be_dimona_declaration_id._l10n_be_dimona_period_id(),
                    "endDate": self.contract_date_end.strftime("%Y-%m-%d"),
                }
            }
        if declaration_type == 'cancel':
            return {
                "dimonaCancel": {
                    "periodId": self.l10n_be_dimona_declaration_id._l10n_be_dimona_period_id(),
                }
            }
        if declaration_type == 'update':
            data = {
                "dimonaUpdate": {
                    "periodId": self.l10n_be_dimona_declaration_id._l10n_be_dimona_period_id(),
                    "startDate": self.contract_date_start.strftime("%Y-%m-%d"),
                }
            }
            if self.contract_date_end:
                data["dimonaUpdate"]["endDate"] = self.contract_date_end.strftime("%Y-%m-%d")
            if self.l10n_be_dimona_planned_hours:
                data['dimonaUpdate']["plannedHoursNumber"] = self.l10n_be_dimona_planned_hours
            if self.is_flexi() and self.contract_date_start and self.contract_date_end and self.contract_date_start == self.contract_date_end:
                if self.l10n_be_dimona_planned_start_time is not False and self.l10n_be_dimona_planned_end_time is not False:
                    # Format float time to string HH:MM
                    start_h, start_m = divmod(round(self.l10n_be_dimona_planned_start_time * 60), 60)
                    end_h, end_m = divmod(round(self.l10n_be_dimona_planned_end_time * 60), 60)
                    data['dimonaUpdate']["StartingHour"] = f"{start_h:02d}:{start_m:02d}"
                    data['dimonaUpdate']["EndingHour"] = f"{end_h:02d}:{end_m:02d}"
            return data

        first_name, last_name = self.employee_id._get_split_name()
        street_digits = re.findall(r"[0-9]+", self.private_street or '')
        data = {
            "employer": {
                "employerId": int(self.payroll_config_id.onss_registration_number),
            },
            "worker": {
                "ssin": self.employee_id.niss if not foreigner else False,
                'familyName': last_name,
                'givenName': first_name,
                'birthDate': (self.employee_id.birthday or fields.Date.today()).strftime("%Y-%m-%d"),
                'placeOfBirth': (self.employee_id.place_of_birth or '').upper(),
                'countryOfBirth': API_DATA['data']['country_code_by_alpha2'].get(self.employee_id.country_of_birth.code),
                'nationality': API_DATA['data']['country_code_by_alpha2'].get(self.country_id.code),
                'gender': API_DATA['data']['code_by_sex'].get(self.employee_id.sex, 0),
                'address': {
                    'street': self.private_street,
                    'houseNumber': street_digits[0] if street_digits else False,
                    'postCode': self.private_zip,
                    'municipality': {
                        'name': self.private_city,
                        'code': API_DATA['data']['municipality_by_city_name'].get(self.private_city.lower()) if self.private_city
                                else API_DATA['data']['municipality_by_postal_code'].get(self.private_zip) or 99999,
                    },
                    'country': API_DATA['data']['country_code_by_alpha2'].get(self.private_country_id.code)
                },
            },
            "dimonaIn": {
                "startDate": self.contract_date_start.strftime("%Y-%m-%d"),
                "features": {
                    "jointCommissionNumber": self.l10n_be_joint_committee_id.egov3_code or "XXX",
                    "workerType": self.l10n_be_dimona_category,
                }
            }
        }
        if self.contract_date_end:
            data['dimonaIn']["endDate"] = self.contract_date_end.strftime("%Y-%m-%d")
        if self.l10n_be_dimona_planned_hours:
            data['dimonaIn']["plannedHoursNumber"] = self.l10n_be_dimona_planned_hours
        if self.is_flexi() and self.contract_date_start == self.contract_date_end:
            if self.l10n_be_dimona_planned_start_time is not False and self.l10n_be_dimona_planned_end_time is not False:
                start_h, start_m = divmod(round(self.l10n_be_dimona_planned_start_time * 60), 60)
                end_h, end_m = divmod(round(self.l10n_be_dimona_planned_end_time * 60), 60)
                data['dimonaIn']["StartingHour"] = f"{start_h:02d}:{start_m:02d}"
                data['dimonaIn']["EndingHour"] = f"{end_h:02d}:{end_m:02d}"
        # Drop empty worker informations (The ONSS doesn't like it)
        data['worker']['address'] = {key: value for key, value in data['worker']['address'].items() if value}
        data['worker'] = {key: value for key, value in data['worker'].items() if value or key == 'gender'}
        return data

    def _action_open_dimona(self, foreigner=False):
        self.ensure_one()
        self._l10n_be_dimona_check('in', foreigner=foreigner)
        payload = self._l10n_be_dimona_payload('in', foreigner=foreigner)
        self._dimona_declaration(payload)

    def action_open_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'without_niss': (not self.employee_id.niss) or (self.employee_id.niss == '/'),
            'declaration_type': 'in',
        }).submit_declaration()
        self.l10n_be_dimona_next_action = 'progress'
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _action_close_dimona(self):
        self.ensure_one()
        self._l10n_be_dimona_check('out')
        payload = self._l10n_be_dimona_payload('out')
        self._dimona_declaration(payload)

    def action_close_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'declaration_type': 'out',
        }).submit_declaration()
        self.l10n_be_dimona_next_action = 'progress'
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _action_update_dimona(self):
        self.ensure_one()
        self._l10n_be_dimona_check('update')
        payload = self._l10n_be_dimona_payload('update')
        self._dimona_declaration(payload)

    def action_update_dimona(self):
        self.ensure_one()
        self._l10n_be_dimona_check('update')
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'declaration_type': 'update',
        }).submit_declaration()
        self.l10n_be_dimona_next_action = 'progress'
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _action_cancel_dimona(self):
        self.ensure_one()
        self._l10n_be_dimona_check('cancel')
        payload = self._l10n_be_dimona_payload('cancel')
        self._dimona_declaration(payload)

    def action_cancel_dimona(self):
        self.ensure_one()
        self.env['l10n.be.dimona.wizard'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'declaration_type': 'cancel',
        }).submit_declaration()
        self.l10n_be_dimona_next_action = 'progress'
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def _get_fake_dimona_check_response(self):
        return {
            "worker": {
                "ssin": self.employee_id.niss,
                "gender": self.sex,
                "birthDate": "1991-07-28",
                "givenName": "Test",
                "familyName": "test",
                "givenNames": "test",
                "nationality": 150
            },
            "dimonaIn": {
                "features": {"workerType": "OTH", "jointCommissionNumber": "XXX"},
                "startDate": "2025-12-01"
            },
            "employer": {"employerId": 123456, "enterpriseNumber": "123456"},
            "declarationStatus": {
                "period": {"id": 9876540, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/9876540"},
                "result": 'A',
                "declarationId": 9876540
            }
        }

    def action_check_dimona(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(self.env._("You don't have the right to call this action"))

        if not self.l10n_be_last_dimona_declaration_id:
            raise UserError(self.env._("No DIMONA declaration is linked to this contract"))

        if not self.company_id._l10n_be_dimona_uses_rest_api():
            raise UserError(self.env._(
                "The DIMONA declarations of %(company)s are followed up outside of this database.",
                company=self.company_id.name))

        if self.company_id.l10n_be_dimona_environment == 'sandbox':
            fake_response = self._get_fake_dimona_check_response()
            check_response = self.env['l10n.be.check.dimona.sandbox'].create({
                'version_id': self.id,
                'response_json': json.dumps(self.l10n_be_last_dimona_declaration_id.content or fake_response, indent=2),
            })
            return {
                'name': self.env._('DIMONA Check Response'),
                'type': 'ir.actions.act_window',
                'res_model': 'l10n.be.check.dimona.sandbox',
                'res_id': check_response.id,
                'view_mode': 'form',
                'target': 'new',
            }

        access_token = self._dimona_authenticate(self.company_id, declare=False)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % access_token,
        }
        try:
            response = request(
                self._get_dimona_api_routes()['get_declaration']['method'],
                self._get_dimona_api_routes()['get_declaration']['url'] + url_quote(self.l10n_be_last_dimona_declaration_id.name),
                headers=headers, timeout=DIMONA_TIMEOUT)
            if response.status_code == 200:
                self.l10n_be_last_dimona_declaration_id._dimona_apply_response(response.json())
            elif response.status_code == 400:
                raise UserError(self.env._('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
            elif response.status_code == 403:
                raise UserError(self.env._('Your user does not have the rights to consult this declaration. This happens, for example, if the user does not have or no longer has a mandate for the employer. (%s)', response.text))
            elif response.status_code == 404:
                raise UserError(self.env._('The declaration has been submitted but not processed yet or the declaration reference is not known. (%s)', response.text))
            elif response.status_code == 500:
                raise UserError(self.env._('Due to a technical problem at the ONSS side, the Dimona declaration could not be received by the ONSS.'))
            response.raise_for_status()
        except HTTPError as e:
            raise UserError(self.env._('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))

    def action_send_dimona(self):
        self.ensure_one()
        if self._l10n_be_dimona_can_declare():
            if self.l10n_be_needs_dimona_in:
                self.action_open_dimona()
            elif self.l10n_be_needs_dimona_update:
                self.action_update_dimona()
            elif self.l10n_be_needs_dimona_out:
                self.action_close_dimona()
            elif self.l10n_be_needs_dimona_cancel:
                self.action_cancel_dimona()
            return
        return self.env['l10n.be.dimona.manual.wizard'].action_open_manual_declaration(self)

    def _get_version_lookup_key(self):
        self.ensure_one()
        if self.country_code != 'BE':
            return super()._get_version_lookup_key()
        return (self.employee_id.id, self.l10n_be_dimona_category, self.l10n_be_worker_code_id.id)

    @api.model
    def action_fetch_all_dimona(self):
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(self.env._("You don't have the right to call this action"))

        payroll_configs_per_company = self.env['payroll.config.settings']._read_group(
            domain=[('company_id.onss_expeditor_number', '!=', False),
            ('company_id.onss_certificate_id', '!=', False),
            ('onss_registration_number', '!=', False)],
            groupby=['company_id'], aggregates=['id:recordset']
        )
        for company, configs in payroll_configs_per_company:
            if not company._l10n_be_dimona_uses_rest_api():
                continue
            config = configs[-1]
            access_token = self._dimona_authenticate(company, declare=False)
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer %s' % access_token,
            }

            # 1: Fetch all relations
            next_page = self._get_dimona_api_routes()['search_relations']['url'] + '?' + url_encode({'pageSize': 50, 'page': 1})
            relations_to_create = []
            while next_page:
                try:
                    data = {
                        "employer": {
                            "employerId": int(config.onss_registration_number),
                        },
                    }
                    _logger.info("Fetching Dimona Relations: %s", next_page)
                    response = request(
                        self._get_dimona_api_routes()['search_relations']['method'],
                        next_page,
                        json=data, headers=headers, timeout=DIMONA_TIMEOUT)
                    if response.status_code == 200:
                        result = response.json()
                        next_page = result.get('next', False)
                        for item in result['items']:
                            relation_reference = item['worker']['ssin']
                            existing_period = self.env['l10n.be.dimona.relation'].search([
                                ('company_id', '=', company.id),
                                ('name', '=', relation_reference)])
                            if not existing_period:
                                relations_to_create.append({
                                    'name': relation_reference,
                                    'company_id': company.id,
                                    'content': item
                                })
                            else:
                                existing_period.write({'content': item})
                    elif response.status_code == 400:
                        raise UserError(self.env._('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
                    elif response.status_code == 500:
                        raise UserError(self.env._('Due to a technical problem at the ONSS side, the Dimona declarations could not be fetch to the ONSS.'))
                    response.raise_for_status()
                except HTTPError as e:
                    raise UserError(self.env._('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
            self.env['l10n.be.dimona.relation'].create(relations_to_create)

            # 2: Fetch all periods
            next_page = self._get_dimona_api_routes()['search_periods']['url'] + '?' + url_encode({'pageSize': 50, 'page': 1})
            periods_to_create = []
            while next_page:
                try:
                    data = {
                        "employer": {
                            "employerId": int(config.onss_registration_number),
                        },
                    }
                    _logger.info("Fetching Dimona Periods: %s", next_page)
                    response = request(
                        self._get_dimona_api_routes()['search_periods']['method'],
                        next_page,
                        json=data, headers=headers, timeout=DIMONA_TIMEOUT)
                    if response.status_code == 200:
                        result = response.json()
                        next_page = result.get('next', False)
                        for item in result['items']:
                            period_reference = item['periodId']
                            existing_period = self.env['l10n.be.dimona.period'].search([
                                ('company_id', '=', company.id),
                                ('name', '=', period_reference)])
                            if not existing_period:
                                periods_to_create.append({
                                    'name': period_reference,
                                    'company_id': company.id,
                                    'content': item
                                })
                            else:
                                existing_period.write({'content': item})
                    elif response.status_code == 400:
                        raise UserError(self.env._('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
                    elif response.status_code == 500:
                        raise UserError(self.env._('Due to a technical problem at the ONSS side, the Dimona declarations could not be fetch to the ONSS.'))
                    response.raise_for_status()
                except HTTPError as e:
                    raise UserError(self.env._('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
            self.env['l10n.be.dimona.period'].create(periods_to_create)

            # 3: Fetch all declarations
            next_page = self._get_dimona_api_routes()['search_declarations']['url'] + '?' + url_encode({'pageSize': 50, 'page': 1})
            declarations_to_create = []
            while next_page:
                try:
                    data = {
                        "employer": {
                            "employerId": int(config.onss_registration_number),
                        },
                    }
                    _logger.info("Fetching Dimona Declarations: %s", next_page)
                    response = request(
                        self._get_dimona_api_routes()['search_declarations']['method'],
                        next_page,
                        json=data, headers=headers, timeout=DIMONA_TIMEOUT)
                    if response.status_code == 200:
                        result = response.json()
                        next_page = result.get('next', False)
                        for item in result['items']:
                            declaration_reference = item['declarationStatus']['declarationId']
                            existing_declaration = self.env['l10n.be.dimona.declaration'].search([
                                ('company_id', '=', company.id),
                                ('name', '=', declaration_reference)])
                            if not existing_declaration:
                                declarations_to_create.append({
                                    'name': declaration_reference,
                                    'company_id': company.id,
                                    'content': item
                                })
                            else:
                                existing_declaration.write({'content': item})
                    elif response.status_code == 400:
                        raise UserError(self.env._('Error with one or several invalid parameters on the POST request. Please contact an administrator. (%s)', response.text))
                    elif response.status_code == 500:
                        raise UserError(self.env._('Due to a technical problem at the ONSS side, the Dimona declarations could not be fetch to the ONSS.'))
                    response.raise_for_status()
                except HTTPError as e:
                    raise UserError(self.env._('Cannot connect with the ONSS servers. Please contact an administrator. (%s)', e))
            self.env['l10n.be.dimona.declaration'].create(declarations_to_create)

    @api.model
    def _cron_l10n_be_check_dimona(self, batch_size=50):
        self.action_fetch_all_dimona()

    def _get_no_wet_or_wet_match(self, leave, leave_entry_type):
        # In belgium, after 1 month of sick leave, the following consecutive leaves are a of a different kind. They should count anyways
        return super()._get_no_wet_or_wet_match(leave, leave_entry_type) \
                or (leave[2].work_entry_type_id.code == '013.00' and leave_entry_type.code == '122.00')

    def _get_mobility_budget_cost(self, base_wage):
        self.ensure_one()
        mobility_cost = base_wage * self._get_mobility_budget_cost_ratio() / 5.0
        mobility_cost += self.employee_id._get_last_year_variable_revenues(date_from=fields.Date.today()) / 5.0

        # add group insurance
        company_gi_amount = self.l10n_be_group_insurance_company_contribution * (
            self.wage if self.l10n_be_group_insurance_company_contribution_unit == 'percentage' else 1
        )
        employee_gi_amount = self.l10n_be_group_insurance_employee_contribution * (
            self.wage if self.l10n_be_group_insurance_employee_contribution_unit == 'percentage' else 1
        )
        total_gi_amount = company_gi_amount + employee_gi_amount + self.l10n_be_group_insurance_employee_voluntary
        return mobility_cost + total_gi_amount

    @api.depends("l10n_be_worker_code_id.dmfa_code")
    def _compute_needs_flxwage_declaration(self):
        for version in self:
            version.l10n_be_needs_flxwage_declaration = version.l10n_be_worker_code_id.dmfa_code in ['050', '450']

    def action_employee_work_schedule_change_wizard(self, resource_calendar_id):
        self.ensure_one()
        if self.company_id.country_id.code != 'BE' or not self.contract_date_start:
            return
        new_resource_calendar = self.env['resource.calendar'].browse(resource_calendar_id)
        if new_resource_calendar == self.resource_calendar_id:
            return
        # Don't open the pop-up if employee does not have a payslip
        if not self.env['hr.payslip'].search_count([('employee_id', '=', self.employee_id.id)], limit=1):
            return
        action = self.env['ir.actions.actions']._for_xml_id('l10n_be_hr_payroll.schedule_change_wizard_action')
        action['context'] = {
            'default_version_id': self.id,
            'default_date_start': self.date_start,
            'default_date_end': self.date_end or False,
            'default_resource_calendar_id': new_resource_calendar.id,
        }
        return action

    def _get_wage_from_reference_salary(self, year, monthly_wage):
        """
        Inverse of `_l10n_be_get_monthly_wage`: converts a gross monthly wage back into the actual
        contract wage (hourly wage, or the monthly wage itself for non-hourly wage types).
        """
        self.ensure_one()
        if self.wage_type != "hourly":
            return monthly_wage
        hours_per_week = self._l10n_be_get_hours_per_week(year)
        return monthly_wage * 3 / (hours_per_week * 13) if hours_per_week else 0
