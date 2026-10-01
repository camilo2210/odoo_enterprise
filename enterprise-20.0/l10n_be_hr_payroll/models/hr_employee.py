# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from datetime import date, datetime, timedelta
from functools import reduce
from itertools import pairwise
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import date_utils, float_round
from odoo.tools.float_utils import float_compare
from odoo.fields import Domain

# old worker_code → new worker_code
L10N_BE_YOUNG_WORKER_CODE_MAPPING = {
    '035': '015',
    '439': '495',
    '487': '495',
    '486': '496',
    '020': '011',
}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    allowed_joint_committee_ids = fields.Many2many(related="version_id.allowed_joint_committee_ids", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_allowed_worker_code_ids = fields.Many2many(related="version_id.l10n_be_allowed_worker_code_ids", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_joint_committee_id = fields.Many2one(readonly=False, related="version_id.l10n_be_joint_committee_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_egov3_code = fields.Char(related="version_id.l10n_be_egov3_code", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_worker_code_id = fields.Many2one(readonly=False, related="version_id.l10n_be_worker_code_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_worker_code_is_single = fields.Boolean(related="version_id.l10n_be_worker_code_is_single", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_worker_status = fields.Selection(readonly=False, related="version_id.l10n_be_worker_status", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_risk_class = fields.Selection(readonly=False, related="version_id.l10n_be_risk_class", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    available_l10n_be_worker_status = fields.Json(related="version_id.available_l10n_be_worker_status", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_legal_first_name = fields.Char(string="First Name (BE)", compute="_compute_l10n_be_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user",
        help="The employee's official first name as per government-issued or legal documents.")
    l10n_be_legal_last_name = fields.Char(string="Last Name (BE)", compute="_compute_l10n_be_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user",
        help="The employee's official last name as per government-issued or legal documents.")

    l10n_be_employee_type_code = fields.Char(related='version_id.employee_type_id.code', string="Employee Type code", groups='hr_payroll.group_hr_payroll_user')
    l10n_be_apprenticeship_contract_number = fields.Char(readonly=False, related='version_id.l10n_be_apprenticeship_contract_number', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_apprenticeship_contract_type = fields.Selection(readonly=False, related='version_id.l10n_be_apprenticeship_contract_type', inherited=True, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_apprenticeship_contract_subtype = fields.Selection(readonly=False, related='version_id.l10n_be_apprenticeship_contract_subtype', inherited=True, groups='hr_payroll.group_hr_payroll_user')

    niss = fields.Char(
        'NISS Number', compute="_compute_niss", inverse='_inverse_niss', store=True, readonly=False,
        groups="hr.group_hr_user", tracking=True, index=True)
    spouse_fiscal_status_explanation_tooltip = fields.Html(compute='_compute_spouse_fiscal_status_explanation_tooltip', groups="hr.group_hr_user")

    l10n_be_scale_seniority = fields.Integer(readonly=False, related="version_id.l10n_be_scale_seniority", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_scale_seniority_months = fields.Integer(readonly=False, related="version_id.l10n_be_scale_seniority_months", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_fictive_hire_date = fields.Date(string="Fictive Hire Date", groups="hr_payroll.group_hr_payroll_user", compute='_compute_l10n_be_fictive_hire_date', store=True, readonly=False)

    first_contract_year_n1 = fields.Char(compute='_compute_first_contract_year', groups="hr_payroll.group_hr_payroll_user")
    first_contract_year_n2 = fields.Char(compute='_compute_first_contract_year', groups="hr_payroll.group_hr_payroll_user")
    postponed_paid_time_off_n1 = fields.Float(string='Postponed Paid Time Off (N-1)', groups="hr_payroll.group_hr_payroll_user", tracking=True)
    postponed_paid_time_off_n2 = fields.Float(string='Postponed Paid Time Off (N-2)', groups="hr_payroll.group_hr_payroll_user", tracking=True)

    l10n_be_holiday_attest_ids = fields.One2many('l10n.be.holiday.attest', inverse_name='employee_id', string="Holiday Attestation", groups="hr_payroll.group_hr_payroll_user")

    mobility_card = fields.Char(groups="hr_payroll.group_hr_payroll_user", help="Number of the card used to refill your car.")
    l10n_be_withholding_tax_type = fields.Selection(readonly=False, related="version_id.l10n_be_withholding_tax_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_withholding_tax_amount = fields.Float(readonly=False, related="version_id.l10n_be_withholding_tax_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_withholding_tax_percentage = fields.Float(readonly=False, related="version_id.l10n_be_withholding_tax_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fiscal_voluntarism_type = fields.Selection(readonly=False, related="version_id.fiscal_voluntarism_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fiscal_voluntarism_amount = fields.Float(readonly=False, related="version_id.fiscal_voluntarism_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fiscal_voluntarism_percentage = fields.Float(readonly=False, related="version_id.fiscal_voluntarism_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    transport_mode_car = fields.Boolean(readonly=False, related="version_id.transport_mode_car", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    car_atn = fields.Monetary(related="version_id.car_atn", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    train_transport_employee_kilometer = fields.Integer(readonly=False, related="version_id.train_transport_employee_kilometer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    train_transport_periodicity = fields.Selection(readonly=False, related="version_id.train_transport_periodicity", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    bus_transport_employee_amount = fields.Monetary(readonly=False, related="version_id.bus_transport_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    bus_transport_employee_kilometer = fields.Integer(readonly=False, related="version_id.bus_transport_employee_kilometer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_planned_start_time = fields.Float(readonly=False, related="version_id.l10n_be_dimona_planned_start_time", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_planned_end_time = fields.Float(readonly=False, related="version_id.l10n_be_dimona_planned_end_time", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_flexi_hourly_wage = fields.Monetary(readonly=False, related="version_id.l10n_be_flexi_hourly_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_flexi_monthly_wage = fields.Monetary(readonly=False, related="version_id.l10n_be_flexi_monthly_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    bus_transport_periodicity = fields.Selection(readonly=False, related="version_id.bus_transport_periodicity", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    tram_transport_employee_amount = fields.Monetary(readonly=False, related="version_id.tram_transport_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    tram_transport_employee_kilometer = fields.Integer(readonly=False, related="version_id.tram_transport_employee_kilometer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    tram_transport_periodicity = fields.Selection(readonly=False, related="version_id.tram_transport_periodicity", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    metro_transport_employee_amount = fields.Monetary(readonly=False, related="version_id.metro_transport_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    metro_transport_employee_kilometer = fields.Integer(readonly=False, related="version_id.metro_transport_employee_kilometer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    metro_transport_periodicity = fields.Selection(readonly=False, related="version_id.metro_transport_periodicity", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    bike_transport_employee_kilometer = fields.Float(readonly=False, related="version_id.bike_transport_employee_kilometer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    private_car_employee_kilometer = fields.Integer(readonly=False, related="version_id.private_car_employee_kilometer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    warrant_value_employee = fields.Monetary(related="version_id.warrant_value_employee", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_paid_by_employer = fields.Monetary(related="version_id.meal_voucher_paid_by_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_paid_monthly_by_employer = fields.Monetary(related="version_id.meal_voucher_paid_monthly_by_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    eco_checks = fields.Monetary(related="version_id.eco_checks", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    company_car_total_depreciated_cost = fields.Monetary(related="version_id.company_car_total_depreciated_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    temporary_car_total_depreciated_cost = fields.Float(related="version_id.temporary_car_total_depreciated_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    warrants_cost = fields.Monetary(related="version_id.warrants_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    yearly_commission = fields.Monetary(related="version_id.yearly_commission", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    yearly_commission_cost = fields.Monetary(related="version_id.yearly_commission_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    commission_on_target = fields.Monetary(readonly=False, related="version_id.commission_on_target", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fuel_card = fields.Monetary(readonly=False, related="version_id.fuel_card", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    internet = fields.Monetary(readonly=False, related="version_id.internet", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    mobile = fields.Monetary(readonly=False, related="version_id.mobile", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    mobile_amount = fields.Monetary(readonly=False, related="version_id.mobile_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    has_laptop = fields.Boolean(readonly=False, related="version_id.has_laptop", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    laptop = fields.Monetary(readonly=False, related="version_id.laptop", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    tablet = fields.Monetary(readonly=False, related="version_id.tablet", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    electricity_amount = fields.Monetary(readonly=False, related="version_id.electricity_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    heating_amount = fields.Monetary(readonly=False, related="version_id.heating_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    housing_onss_amount = fields.Monetary(readonly=False, related="version_id.housing_onss_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    housing_fiscal_amount = fields.Monetary(readonly=False, related="version_id.housing_fiscal_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    rent_amount = fields.Monetary(readonly=False, related="version_id.rent_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    pension_amount = fields.Monetary(readonly=False, related="version_id.pension_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_amount = fields.Monetary(readonly=False, related="version_id.meal_voucher_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_calculation_method = fields.Selection(readonly=False, related="version_id.meal_voucher_calculation_method", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    fixed_meal_voucher_days = fields.Integer(readonly=False, related="version_id.fixed_meal_voucher_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_average_monthly_amount = fields.Monetary(related="version_id.meal_voucher_average_monthly_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    meal_voucher_employee_share = fields.Monetary(readonly=False, related="version_id.meal_voucher_employee_share", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    is_meal_voucher_valid = fields.Boolean(related="version_id.is_meal_voucher_valid", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip_wage_rate = fields.Float(readonly=False, related="version_id.ip_wage_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip_value = fields.Float(related="version_id.ip_value", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip_artist = fields.Boolean(readonly=False, related="version_id.ip_artist", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    ip_onss = fields.Boolean(readonly=False, related="version_id.ip_onss", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    no_withholding_taxes = fields.Boolean(readonly=False, related="version_id.no_withholding_taxes", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_resident_situation = fields.Selection(readonly=False, related="version_id.l10n_be_resident_situation", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    work_in_belgium_over_75 = fields.Boolean(readonly=False, related="version_id.work_in_belgium_over_75", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    rd_percentage = fields.Float(readonly=False, related="version_id.rd_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_aid_zone = fields.Boolean(readonly=False, related="version_id.l10n_be_is_aid_zone", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_impulsion_plan = fields.Selection(readonly=False, related="version_id.l10n_be_impulsion_plan", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    restructuring_reduction_date_start = fields.Date(string="Restructuring Reduction Start Date", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_retired = fields.Boolean(readonly=False, related="version_id.l10n_be_is_retired", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_retirement_date = fields.Date(related="version_id.l10n_be_retirement_date", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_contribute_to_fse = fields.Boolean(readonly=False, related="version_id.l10n_be_contribute_to_fse", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_early_retirement_status = fields.Boolean(readonly=False, related="version_id.l10n_be_early_retirement_status", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    has_hospital_insurance = fields.Boolean(readonly=False, related="version_id.has_hospital_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_children = fields.Integer(readonly=False, related="version_id.insured_relative_children", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_adults = fields.Integer(readonly=False, related="version_id.insured_relative_adults", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_spouse = fields.Boolean(readonly=False, related="version_id.insured_relative_spouse", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hospital_insurance_amount_per_child = fields.Float(readonly=False, related="version_id.hospital_insurance_amount_per_child", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hospital_insurance_amount_per_adult = fields.Float(readonly=False, related="version_id.hospital_insurance_amount_per_adult", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    hospital_insurance_employee_contribution = fields.Float(readonly=False, related="version_id.hospital_insurance_employee_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insurance_amount = fields.Float(related="version_id.insurance_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    insured_relative_adults_total = fields.Integer(related="version_id.insured_relative_adults_total", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_hospital_insurance_notes = fields.Text(readonly=False, related="version_id.l10n_be_hospital_insurance_notes", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    # Group Insurance
    l10n_be_has_group_insurance = fields.Boolean(readonly=False, related="version_id.l10n_be_has_group_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_rate = fields.Float(readonly=False, related="version_id.l10n_be_group_insurance_rate", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_amount = fields.Monetary(related="version_id.l10n_be_group_insurance_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_cost = fields.Monetary(related="version_id.l10n_be_group_insurance_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_company_contribution = fields.Float(readonly=False, related="version_id.l10n_be_group_insurance_company_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_company_contribution_unit = fields.Selection(readonly=False, related="version_id.l10n_be_group_insurance_company_contribution_unit", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_employee_contribution = fields.Float(readonly=False, related="version_id.l10n_be_group_insurance_employee_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_employee_contribution_unit = fields.Selection(readonly=False, related="version_id.l10n_be_group_insurance_employee_contribution_unit", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_group_insurance_employee_voluntary = fields.Monetary(readonly=False, related="version_id.l10n_be_group_insurance_employee_voluntary", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    # Ambulatory Insurance
    l10n_be_ambulatory_insurance_employee_contribution = fields.Float(readonly=False, related="version_id.l10n_be_ambulatory_insurance_employee_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_has_ambulatory_insurance = fields.Boolean(readonly=False, related="version_id.l10n_be_has_ambulatory_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_children = fields.Integer(readonly=False, related="version_id.l10n_be_ambulatory_insured_children", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_adults = fields.Integer(readonly=False, related="version_id.l10n_be_ambulatory_insured_adults", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_spouse = fields.Boolean(readonly=False, related="version_id.l10n_be_ambulatory_insured_spouse", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_amount_per_child = fields.Float(readonly=False, related="version_id.l10n_be_ambulatory_amount_per_child", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_amount_per_adult = fields.Float(readonly=False, related="version_id.l10n_be_ambulatory_amount_per_adult", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insurance_amount = fields.Float(related="version_id.l10n_be_ambulatory_insurance_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insured_adults_total = fields.Integer(related="version_id.l10n_be_ambulatory_insured_adults_total", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_ambulatory_insurance_notes = fields.Text(readonly=False, related="version_id.l10n_be_ambulatory_insurance_notes", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_mobility_budget = fields.Boolean(readonly=False, related="version_id.l10n_be_mobility_budget", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_mobility_budget_amount = fields.Monetary(readonly=False, related="version_id.l10n_be_mobility_budget_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_mobility_budget_amount_monthly = fields.Monetary(related="version_id.l10n_be_mobility_budget_amount_monthly", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_is_4th_fixed_term_contract_warning = fields.Char(default=False, compute='_compute_l10n_be_is_4th_fixed_term_contract_warning', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_canteen_cost = fields.Monetary(readonly=False, related="version_id.l10n_be_canteen_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_dimona_planned_hours = fields.Integer(readonly=False, related="version_id.l10n_be_dimona_planned_hours", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_be_dimona_declaration_id = fields.Many2one(readonly=False, related="version_id.l10n_be_dimona_declaration_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_last_dimona_declaration_id = fields.Many2one(readonly=False, related="version_id.l10n_be_last_dimona_declaration_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_in = fields.Boolean(related="version_id.l10n_be_needs_dimona_in", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_update = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_update", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_out = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_out", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_cancel = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_cancel", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_next_action = fields.Selection(readonly=False, related="version_id.l10n_be_dimona_next_action", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_relation_id = fields.Many2one('l10n.be.dimona.relation', string='Dimona Relation', groups="hr_payroll.group_hr_payroll_user", index='btree_not_null')
    l10n_be_part_time_status = fields.Selection(readonly=False, related='version_id.l10n_be_part_time_status', inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_starterjob = fields.Boolean(readonly=False, related='version_id.l10n_be_is_starterjob', inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_salary_scale_id = fields.Many2one(readonly=False, related='version_id.l10n_be_salary_scale_id', inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_is_sale_representative = fields.Boolean(readonly=False, related='version_id.l10n_be_is_sale_representative', inherited=True, groups="hr_payroll.group_hr_payroll_user")
    display_l10n_be_scale = fields.Boolean(related='version_id.display_l10n_be_scale', inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_homeworking_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_homeworking_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_office_fees_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_office_fees_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_office_fees_2022_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_office_fees_2022_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_phone_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_phone_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_internet_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_internet_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_pc_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_pc_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_second_screen_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_second_screen_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_scanner_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_scanner_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_car_management_garage_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_car_management_garage_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_car_management_parking_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_car_management_parking_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_car_management_wash_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_car_management_wash_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_travel_cost_loc_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_travel_cost_loc_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_travel_cost_meal_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_travel_cost_meal_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_travel_cost_living_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_travel_cost_living_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_service_travel_abroad_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_service_travel_abroad_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_working_tools_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_working_tools_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_buying_work_clothes_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_buying_work_clothes_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_work_clothes_maintenance_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_work_clothes_maintenance_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_personal_work_clothes_maintenance_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_personal_work_clothes_maintenance_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_car_travel_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_car_travel_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_bike_travel_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_bike_travel_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_bike_professional_travel_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_bike_professional_travel_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_daily_misc_base_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_daily_misc_base_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_monthly_misc_base_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_monthly_misc_base_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_daily_misc_other_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_daily_misc_other_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_monthly_misc_other_amount = fields.Monetary(readonly=False, related="version_id.l10n_be_lsa_monthly_misc_other_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_monthly_pro_base_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_monthly_pro_base_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_lsa_monthly_pro_other_amount = fields.Float(readonly=False, related='version_id.l10n_be_lsa_monthly_pro_other_amount', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_category = fields.Selection(related='version_id.l10n_be_dimona_category', inherited=True, readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_refused_flexijob = fields.Boolean(related='version_id.l10n_be_refused_flexijob', inherited=True, readonly=False, groups='hr_payroll.group_hr_payroll_user')
    l10n_be_employee_type_dimona_category = fields.Selection(related='version_id.employee_type_id.l10n_be_dimona_category', string='Employee Type DIMONA Category', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_company_seniority_years = fields.Integer(compute='_compute_company_seniority', help="Time the employee worked inside the company", groups="hr_payroll.group_hr_payroll_user")
    l10n_be_company_seniority_months = fields.Integer(compute='_compute_company_seniority', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_in_position_years = fields.Integer(related='version_id.l10n_be_in_position_years', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_in_position_months = fields.Integer(related='version_id.l10n_be_in_position_months', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_computed_seniority_years = fields.Integer(related='version_id.l10n_be_computed_seniority_years', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_computed_seniority_months = fields.Integer(related='version_id.l10n_be_computed_seniority_months', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_base_computed_seniority = fields.Integer(related='version_id.l10n_be_base_computed_seniority', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_show_effective_marital_warning = fields.Boolean(compute='_compute_l10n_be_show_effective_marital_warning', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_flexi_at_work_ids = fields.One2many('l10n.be.flexi.at.work', 'employee_id', string='Flexi@Work', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_city_nis_code = fields.Char('City NIS Code', related="version_id.l10n_be_city_nis_code",
        groups="hr_payroll.group_hr_payroll_user",
        help="Belgian National Institute of Statistics city code of the private address")
    l10n_be_country_nis_code = fields.Char('Country NIS Code', related="version_id.l10n_be_country_nis_code",
        groups="hr_payroll.group_hr_payroll_user",
        help="Belgian National Institute of Statistics country code of the private address")
    l10n_be_allowed_dimona_categories = fields.Json(related='version_id.l10n_be_allowed_dimona_categories', groups="hr_payroll.group_hr_payroll_user")
    l10n_be_onss_reduction_unexperienced_employees_flander = fields.Boolean(
        related="version_id.l10n_be_onss_reduction_unexperienced_employees_flander",
        groups="hr_payroll.group_hr_payroll_user",
        readonly=False,
    )
    l10n_be_working_region = fields.Selection(related="version_id.l10n_be_working_region", inherited=True, readonly=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_natural_person_state_ids = fields.One2many('l10n_be.dmfa.natural_person.state', 'employee_id', string="DMFA Natural Person States", groups='hr_payroll.group_hr_payroll_user')
    show_dimona_button = fields.Boolean(compute='_compute_show_dimona_button', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_overtime_counter = fields.Integer(compute='_compute_l10n_be_overtime_counter', groups='hr_payroll.group_hr_payroll_user')
    l10n_be_dimona_environment = fields.Selection(
        related='company_id.l10n_be_dimona_environment',
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_be_dimona_relation_date_start = fields.Date(
        related='l10n_be_dimona_relation_id.date_start',
        string='First Employment Date',
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_be_reorganisation_measure_ids = fields.Many2many(
        related="version_id.l10n_be_reorganisation_measure_ids",
        string='Has Work Reorganisation Measure',
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_be_include_employee_in_281_30 = fields.Boolean(
        related="version_id.l10n_be_include_employee_in_281_30",
        inherited=True,
        readonly=False,
        groups="hr_payroll.group_hr_payroll_user")
    l10n_be_long_sick_leave = fields.Boolean(
        compute="_compute_l10n_be_long_sick_leave",
        search="_search_l10n_be_long_sick_leave",
        groups="hr_payroll.group_hr_payroll_user"
    )
    l10n_be_capped_amount = fields.Monetary(readonly=False, related="version_id.l10n_be_capped_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        fields_description = super().fields_get(allfields, attributes)
        self.env['hr.version']._add_bik_amount_to_help(fields_description)
        return fields_description

    @api.model
    def _default_lang(self):
        return self.env.lang if self.env.company.country_id.code == 'BE' and self.env.lang in ['fr_BE', 'fr_FR', 'nl_BE', 'nl_NL', 'de_DE'] else None
    lang = fields.Selection(selection='_lang_get', default=_default_lang, string="Lang", groups="hr.group_hr_user")

    @api.model
    def _lang_get(self):
        langs = super()._lang_get()
        existing_codes = {code for code, _ in langs}
        be_specific_langs = [
            ('fr_BE', 'French (BE) / Français (BE)'),
            ('nl_BE', 'Dutch (BE) / Nederlands (BE)'),
            ('de_DE', 'German / Deutsch'),
        ]
        for lang in be_specific_langs:
            if lang[0] not in existing_codes:
                langs.append(lang)
        return langs

    def action_send_dimona(self):
        self.ensure_one()
        return self.version_id.action_send_dimona()

    @api.depends('version_id', 'marital')
    def _compute_l10n_be_show_effective_marital_warning(self):
        for employee in self:
            if employee.version_id.country_code != 'BE':
                employee.l10n_be_show_effective_marital_warning = False
            else:
                employee.l10n_be_show_effective_marital_warning = employee._get_effective_marital_at_date(min(date.today(), employee.version_id.date_end or date.max)) != employee.marital

    def _get_effective_marital_at_date(self, target_date=date.today()):
        """
        Determine the marital status used for withholding taxes at a given date.

        Rules:
        - Isolated statuses (single/divorced/widower) are applied immediately.
        - Non-isolated statuses (married/cohabitant) only take effect starting
        from the start of the calendar year.
        """
        self.ensure_one()
        non_isolated = {'married', 'cohabitant'}

        # Get the version active at the date
        version_at_date = self._get_version(target_date)
        if version_at_date.marital not in non_isolated:
            return version_at_date.marital

        # All versions within start_of_year -> date
        start_of_year = target_date.replace(month=1, day=1)
        version_periods = self._get_version_periods(start_of_year, target_date)
        versions_in_year = [
            version
            for (_, _, version)
            in version_periods.get(self.employee_id, [])
        ]

        for version in sorted(versions_in_year, key=lambda v: v.date_version, reverse=True):
            if version.marital not in non_isolated:
                return version.marital

        # Fallback to start of year marital status
        if versions_in_year:
            return versions_in_year[0].marital
        return self._get_version(start_of_year).marital

    def action_check_dimona(self):
        self.ensure_one()
        return self.version_id.action_check_dimona()

    def _get_split_name(self):
        self.ensure_one()
        names = re.sub(r"\([^()]*\)", "", self.name).strip().split()
        first_name = names[-1]
        last_name = ' '.join(names[:-1])
        return first_name, last_name

    def _get_last_year_variable_revenues(self, date_from=None, excluded_codes=None):
        self.ensure_one()
        date_from = date_from or self.env.context.get('variable_revenue_date_from')
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_from + relativedelta(months=-12, day=1)),
            ('date_from', '<=', date_from + relativedelta(months=-1, day=31)),
        ], order="date_from asc")
        variable_revenue_line_codes = {'COMMISSION', 'COMMISSION_ADV', 'COM_LOSS_PH', 'COM_LOSS_SICK', 'SIMPLE_VARIABLE', 'DOUBLE_VARIABLE'}
        if excluded_codes:
            variable_revenue_line_codes -= excluded_codes
        line_values = payslips._get_line_values(variable_revenue_line_codes, compute_sum=True)
        return sum(line_values[code]['sum']['total'] for code in variable_revenue_line_codes)

    def _get_certificate_selection(self):
        if self.env.company.country_id.code != "BE":
            return super()._get_certificate_selection()
        certificate_selection = [
            ('primary', self.env._('Primary School')),
            ('lower_secondary', self.env._('Lower Secondary')),
            ('higher_secondary', self.env._('Higher Secondary'))
        ]
        civil_engineer_added = False
        for selection in super()._get_certificate_selection():
            certificate_selection += [selection]
            if selection[0] == 'master':
                certificate_selection += [('civil_engineer', self.env._('Master: Civil Engineering'))]
                civil_engineer_added = True
        if not civil_engineer_added:
            certificate_selection += [('civil_engineer', self.env._('Master: Civil Engineering'))]
        return certificate_selection

    def has_employee_4th_consecutive_CDD_contract(self):
        self.ensure_one()
        if self.fixed_term and self.contract_date_start:
            anterior_versions = self.version_ids.filtered(
                    lambda v: v.contract_date_start and
                    v.contract_date_end and
                    v.contract_date_start <= self.contract_date_start and
                    v.contract_date_start >= date.today() - relativedelta(years=2)
                )
            if len(anterior_versions) < 4:
                return False

            if relativedelta(anterior_versions[-1].contract_date_end, anterior_versions[-4].contract_date_start).years >= 2:
                return False

            versions_by_contract_dates = anterior_versions.grouped(lambda v: (v.contract_date_start, v.contract_date_end))
            cdd_counter = 0
            for (date_start, date_end), versions in list(versions_by_contract_dates.items())[-4:]:  # Only take the last four contracts
                all_cdd_versions = all(v.fixed_term for v in versions)
                at_least_3_months_contract = (date_start + relativedelta(months=3) - relativedelta(days=1)) <= date_end
                if all_cdd_versions and at_least_3_months_contract:
                    cdd_counter += 1
            if cdd_counter >= 4:
                return True
        return False

    @api.onchange('fiscal_voluntarism_type')
    def _onchange_fiscal_voluntarism_type(self):
        self.fiscal_voluntarism_amount = 0.0
        self.fiscal_voluntarism_percentage = 0.0

    @api.onchange('l10n_be_joint_committee_id')
    def _onchange_joint_committee(self):
        if self.country_code == 'BE':
            self.l10n_be_salary_scale_id = False
            if self.l10n_be_dimona_category not in self.l10n_be_allowed_dimona_categories:
                self.l10n_be_dimona_category = False

            if self.l10n_be_joint_committee_id.egov3_code == '999':
                self.l10n_be_dimona_category = False
                self.l10n_be_worker_code_id = False
                self.l10n_be_egov3_code = '999'

    @api.onchange('employee_type_id')
    def _onchange_employee_type_id_worker_code(self):
        if self.country_code == 'BE' and self.l10n_be_worker_code_id.employee_type_ids \
                and self.employee_type_id not in self.l10n_be_worker_code_id.employee_type_ids:
            self.l10n_be_worker_code_id = False

    @api.onchange('l10n_be_salary_scale_id')
    def _onchange_salary_scale_id(self):
        if self.l10n_be_salary_scale_id.code in ['1', '2', '3']:
            self.wage_type = 'hourly'

    @api.onchange('l10n_be_withholding_tax_type')
    def _onchange_l10n_be_withholding_tax_type(self):
        if self.l10n_be_withholding_tax_type == 'percentage':
            self.l10n_be_withholding_tax_amount = 0
        elif self.l10n_be_withholding_tax_type == 'fixed':
            self.l10n_be_withholding_tax_percentage = 0

    @api.onchange('meal_voucher_employee_share')
    def _onchange_meal_voucher_employee_share(self):
        min_meal_voucher_threshold = self.env['hr.rule.parameter']._get_parameter_from_code('min_meal_voucher_employee_share', raise_if_not_found=False) or 1.09
        for employee in self:
            if employee.company_country_code == 'BE' and float_compare(employee.meal_voucher_employee_share, 0.0, precision_digits=2) == 0:
                return {
                    'warning': {
                        'title': self.env._("Below Legal Minimum"),
                        'message': self.env._("The employee's meal voucher share is set to 0. The payroll engine will automatically apply the legal minimum %s€ during the payslip computation.", min_meal_voucher_threshold)
                    }
                }

    @api.onchange('disabled_children_number')
    def _onchange_dependent_children(self):
        if self.disabled_children_number:
            self.children = self.disabled_children_number

    @api.depends("versions_count", "contract_date_start", "contract_date_end", "employee_type_id")
    def _compute_l10n_be_is_4th_fixed_term_contract_warning(self):
        self.l10n_be_is_4th_fixed_term_contract_warning = False
        belgian_employees = self.filtered(lambda emp: emp.company_country_code == 'BE')
        for employee in belgian_employees:
            if employee.has_employee_4th_consecutive_CDD_contract():
                employee.l10n_be_is_4th_fixed_term_contract_warning = self.env._("The employee cannot have 4 fixed consecutive contracts!")

    def _compute_l10n_be_overtime_counter(self):
        overtime_types_query = self.env['hr.work.entry.type']._search([
            ('category_ids', 'in', self.env.ref('hr_payroll.EXTRA_HOURS').id),
            ('country_id.code', 'in', [False, 'BE']),
        ])
        mapped_counters = dict(self.env['hr.leave']._read_group(
            domain=[
                ('employee_id', 'in', self.ids),
                ('state', '=', 'validate'),
                ('work_entry_type_id', 'in', overtime_types_query),
            ],
            groupby=['employee_id'],
            aggregates=['__count'],
        ))
        for employee in self:
            employee.l10n_be_overtime_counter = mapped_counters.get(employee, 0)

    def _get_dimona_periods_version_mismatch_warning(self):
        """
        Return a message when the Dimona periods of the employee do not tile exactly the
        same date ranges as their contract versions, or when the category or the joint
        committee declared in a Dimona IN differs from the matching version one.
        """
        self.ensure_one()
        periods = self.l10n_be_dimona_relation_id.period_ids.sorted('date_start')
        versions = self.version_ids.filtered('contract_date_start').sorted('contract_date_start')
        if not periods:
            return ''
        period_index = version_index = 0
        # Both cursors hold the first day still to be covered on their own side.
        period_start = version_start = None
        wrong_category = wrong_committee = False
        while period_index < len(periods) and version_index < len(versions):
            period, version = periods[period_index], versions[version_index]
            period_start = period_start or period.date_start
            version_start = version_start or version.contract_date_start
            # An open ended period may only be covered by an open ended version and vice versa.
            if period_start != version_start or bool(period.date_end) != bool(version.contract_date_end):
                break
            for declaration in period.declaration_ids.filtered(lambda d: d.declaration_type == 'dimona_in'):
                features = (declaration.content or {}).get('dimonaIn', {}).get('features', {})
                # The ONSS returns the worker type upper cased, unlike the version category.
                wrong_category = wrong_category or (features.get('workerType') or '').lower() != version.l10n_be_dimona_category
                wrong_committee = wrong_committee or features.get('jointCommissionNumber') != version.l10n_be_joint_committee_id.egov3_code
            if period.date_end == version.contract_date_end:
                # Both sides end together, jump to the next pair.
                period_index += 1
                version_index += 1
                period_start = version_start = None
            elif version.contract_date_end < period.date_end:
                # Several versions share that period, resume it the day after the version.
                version_index += 1
                version_start = None
                period_start = version.contract_date_end + timedelta(days=1)
            else:
                # Several periods share that version, resume it the day after the period.
                period_index += 1
                period_start = None
                version_start = period.date_end + timedelta(days=1)
        messages = []
        # Leftovers on either side mean the two sequences stopped matching somewhere.
        if period_index != len(periods) or version_index != len(versions):
            messages.append(self.env._("Dimona periods and contract versions are not aligned."))
        if wrong_category:
            messages.append(self.env._("The Dimona category does not match the contract version one."))
        if wrong_committee:
            messages.append(self.env._("The Dimona joint committee does not match the contract version one."))
        return ' '.join(messages)

    @api.depends('version_ids.date_version', 'version_ids.contract_date_start', 'version_ids.contract_date_end')
    def _compute_first_contract_year(self):
        today = fields.Date.context_today(self)
        for employee in self:
            version_date = employee._get_first_version_date()
            year = (version_date or today).year
            employee.first_contract_year_n1 = year - 1
            employee.first_contract_year_n2 = year - 2

    @api.depends('version_ids.contract_date_start')
    def _compute_company_seniority(self):
        today = fields.Date.context_today(self)
        for employee in self:
            first_contract_date = employee._get_first_contract_date()
            employee.l10n_be_company_seniority_years, employee.l10n_be_company_seniority_months = employee.version_id._difference_years_months(first_contract_date, today)

    @api.depends('version_ids.contract_date_start')
    def _compute_l10n_be_fictive_hire_date(self):
        for employee in self:
            if employee.company_id.country_id.code != 'BE':
                employee.l10n_be_fictive_hire_date = False
            elif not employee.l10n_be_fictive_hire_date and employee.first_contract_date:
                employee.l10n_be_fictive_hire_date = employee.first_contract_date

    def adjust_wage_to_minimum_scale(self, minimum_wage, wage_type, seniority, is_cp302=False):
        self.ensure_one()
        today = fields.Date.context_today(self)
        seniority_change_date = self.version_id._get_seniority_change_date()
        versions_after_seniority_change_date = self.version_ids.filtered(lambda v: v.date_version >= seniority_change_date).sorted(key=lambda v: v.date_version) if seniority_change_date else self.version_ids
        message = ""
        if versions_after_seniority_change_date:
            version_to_update = versions_after_seniority_change_date[-1]
            wage_field = version_to_update._get_contract_wage_field()
            version_to_update.write({
                wage_field: minimum_wage,
            })
            if is_cp302:
                message = self.env._("The %(wage_type)s wage has been adjusted to the minimum scale: %(amount)s€ "
                    "for salary scale %(salary_scale)s and for a seniority of %(years)s years. "
                    "This adjustment should have been applied earlier, as the seniority changed on %(date)s.",
                    wage_type=wage_type,
                    amount=round(minimum_wage, 2),
                    salary_scale=self.l10n_be_salary_scale_id.code,
                    years=seniority,
                    date=seniority_change_date)
            else:
                message = self.env._(
                    "The %(wage_type)s wage has been adjusted to the minimum scale: %(amount)s€ "
                    "for a seniority of %(years)s years. "
                    "This adjustment should have been applied earlier, as the seniority changed on %(date)s.",
                    wage_type=wage_type,
                    amount=round(minimum_wage, 2),
                    years=seniority,
                    date=seniority_change_date,
                )
        else:
            self.create_version({
                'date_version': seniority_change_date or today,
                'contract_date_start': self.version_id.contract_date_start,
                'contract_date_end': self.version_id.contract_date_end,
                'wage': minimum_wage if wage_type == 'monthly' else self.version_id.wage,
                'hourly_wage': minimum_wage if wage_type == 'hourly' else self.version_id.hourly_wage,
            })
        if is_cp302:
            message = self.env._("The %(wage_type)s wage has been adjusted to the minimum scale: %(amount)s€ for salary scale %(salary_scale)s and for a seniority of %(years)s years.", wage_type=wage_type, amount=round(minimum_wage, 2), salary_scale=self.l10n_be_salary_scale_id.code, years=seniority)
        else:
            message = self.env._("The %(wage_type)s wage has been adjusted to the minimum scale: %(amount)s€ for a seniority of %(years)s years.", wage_type=wage_type, amount=round(minimum_wage, 2), years=seniority)
        self.message_post(body=message)

    @api.model
    def _get_l10n_be_min_wage_invalid_employees(self):
        belgian_companies = self.env.companies.filtered(lambda c: c.country_id.code == 'BE')
        if not belgian_companies:
            return self.browse()
        employees = self.search([
            ('company_id', 'in', belgian_companies.ids),
        ])
        invalid_employees = self.browse()
        for employee in employees:
            version = employee.version_id
            if not version:
                continue
            min_wage, _, _ = version._get_l10n_be_min_wage()
            if min_wage > 0:
                current_wage = version._get_contract_wage()
                if current_wage < min_wage:
                    invalid_employees |= employee
        return invalid_employees

    def l10n_be_action_index_employees_salary(self):
        action = self._increase_employee_salary()
        action['context']['default_type'] = 'legal'
        return action

    def l10n_be_action_adjust_min_wages(self):
        adjusted_employees = self.browse()
        for employee in self:
            version = employee.version_id
            if not version:
                continue
            min_wage, wage_type, seniority = version._get_l10n_be_min_wage()
            if min_wage > 0:
                current_wage = version._get_contract_wage()
                if current_wage < min_wage:
                    is_cp302 = version.l10n_be_joint_committee_id.egov3_code == '302'
                    employee.adjust_wage_to_minimum_scale(min_wage, wage_type, seniority, is_cp302=is_cp302)
                    adjusted_employees |= employee
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._('The wages have been adjusted'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': self.env._('Employees'),
                    'res_model': 'hr.employee',
                    'views': [(False, 'list'), (False, 'form')],
                    'domain': [('id', 'in', adjusted_employees.ids)],
                    'target': 'main',
                },
            },
        }

    @api.model
    def _get_l10n_be_too_old_worker_code_domain(self):
        return [
            ('l10n_be_worker_code_id.dmfa_code', 'in', list(L10N_BE_YOUNG_WORKER_CODE_MAPPING)),
            ('birthday', '<', 'today =1d =1m -18y'),
        ]

    @api.model
    def _get_l10n_be_too_old_worker_code_employees(self, employees=None):
        belgian_companies = self.env.companies.filtered(lambda c: c.country_id.code == 'BE')
        if not belgian_companies:
            return self.browse()
        domain = [
            ('company_id', 'in', belgian_companies.ids),
            *self._get_l10n_be_too_old_worker_code_domain(),
        ]
        if employees is None:
            return self.search(domain)
        return employees.filtered_domain(domain)

    def l10n_be_action_update_worker_codes(self):
        worker_codes = self.env['l10n.be.worker.code'].search([
            ('dmfa_code', 'in', list(L10N_BE_YOUNG_WORKER_CODE_MAPPING.values())),
        ])
        worker_code_by_dmfa_code = {code.dmfa_code: code for code in worker_codes}
        updated_employees = self.browse()
        for employee in self._get_l10n_be_too_old_worker_code_employees(employees=self):
            new_dmfa_code = L10N_BE_YOUNG_WORKER_CODE_MAPPING[employee.l10n_be_worker_code_id.dmfa_code]
            new_worker_code = worker_code_by_dmfa_code.get(new_dmfa_code)
            if not new_worker_code:
                continue
            employee.l10n_be_worker_code_id = new_worker_code
            updated_employees |= employee
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._(
                    "%(count)s employees have been updated",
                    count=len(updated_employees),
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': self.env._('Employees'),
                    'res_model': 'hr.employee',
                    'views': [(False, 'list'), (False, 'form')],
                    'domain': [('id', 'in', updated_employees.ids)],
                    'target': 'main',
                },
            },
        }

    def _compute_spouse_fiscal_status_explanation_tooltip(self):
        no_income_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('spouse_no_income_threshold')
        low_income_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('spouse_low_income_threshold')
        other_income_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('spouse_other_income_threshold')
        explanation = self.env._(
            """- High Income: Spouse earns more than %(low_income_threshold)s€ net/month, excluding pensions, annuities, or assimilated income.\n
- Low Income: Spouse earns no more than %(low_income_threshold)s€ net/month, excluding pensions, annuities, or assimilated income.\n
- Without Income: Spouse earns no income, or no more than %(no_income_threshold)s€ net/month of pensions, annuities, or assimilated income.\n
- High Pensions : Spouse earns more than %(other_income_threshold)s€ net/month of pensions, annuities, or assimilated income.\n
- Low Pensions : Spouse earns no more than %(other_income_threshold)s€ net/month of pensions, annuities, or assimilated income.\n""",
            no_income_threshold=no_income_threshold,
            low_income_threshold=low_income_threshold,
            other_income_threshold=other_income_threshold,
        )

        for record in self:
            record.spouse_fiscal_status_explanation_tooltip = Markup('<div title="%s"><i class="oi text-info" data-icon="info"/></div>') % explanation

    @api.depends('name')
    def _compute_l10n_be_legal_name(self):
        for employee in self:
            if not employee.name or employee.l10n_be_legal_first_name or employee.l10n_be_legal_last_name:
                continue
            names = re.sub(r"\([^()]*\)", "", employee.name).strip().split()
            employee.update({
                'l10n_be_legal_first_name': ' '.join(names[:-1]),
                'l10n_be_legal_last_name': names[-1],
            })

    def _get_splitting_legal_name_countries(self):
        return super()._get_splitting_legal_name_countries() + ['BE']

    @api.depends('l10n_be_legal_first_name', 'l10n_be_legal_last_name')
    def _compute_legal_name(self):
        be_employees = self.filtered(lambda emp: emp.company_id.country_code == 'BE')
        for employee in be_employees:
            if employee.l10n_be_legal_first_name and employee.l10n_be_legal_last_name:
                employee.legal_name = f'{employee.l10n_be_legal_first_name} {employee.l10n_be_legal_last_name}'
            else:
                employee.legal_name = employee.name
        super(HrEmployee, self - be_employees)._compute_legal_name()

    @api.constrains('niss')
    def _check_niss(self):
        for employee in self:
            if employee.niss:
                clean_niss = re.sub(r'[,.\-\s]', '', employee.niss)
                if employee.niss != clean_niss:
                    employee.niss = clean_niss
            if employee.niss and not employee._is_niss_valid():
                raise ValidationError(self.env._("Invalid NISS."))

    @api.depends('identification_id')
    def _compute_niss(self):
        characters = dict.fromkeys([',', '.', '-', ' '], '')
        for employee in self:
            if employee.identification_id and not employee.niss and employee.company_country_code == 'BE':
                employee.niss = reduce(lambda a, kv: a.replace(*kv), characters.items(), employee.identification_id)

    def _parse_niss(self):
        for employee in self:
            if employee.niss and employee._is_niss_valid() and employee.niss != '/':
                employee.sex = 'male' if int(employee.niss[8]) % 2 == 1 else 'female'
                # When the birthday is unknown, the niss starts with 000001
                if employee.niss[:6] == '000001':
                    continue
                date = self._extract_date(employee.niss)
                if date:
                    employee.birthday = date

    def _extract_date(self, niss):
        if not niss or niss == '/':
            return False
        current_year = date.today().year
        century = (current_year // 100) * 100
        year = century + int(niss[:2])
        if year >= current_year:
            year -= 100
        mm = int(niss[2:4]) % 20
        dd = niss[4:6]
        try:
            extracted_date = datetime.strptime(f"{year}{mm:02d}{dd}", '%Y%m%d').date()
        except ValueError:
            extracted_date = False
        return extracted_date

    def _l10n_be_parse_sex(self, niss):
        if not niss or niss == '/':
            return False
        gender_sequence = int(niss[6:9])
        if not gender_sequence % 2:
            return 'female'
        return 'male'

    def _l10n_be_get_short_work_entries(self):
        return self.env['hr.employee']

    def _inverse_niss(self):
        self._parse_niss()

    @api.model
    def _validate_niss(self, niss):
        try:
            test = niss[:-2]
            # If birthday in and after 2000, add a '2' before
            if int(test[:2]) < date.today().year % 100:
                test = '2%s' % test
            checksum = int(niss[-2:])
            if checksum != (97 - int(test) % 97):
                raise Exception()
            return True
        except Exception:
            return False

    def _is_niss_valid(self):
        # The last 2 positions constitute the check digit. This check digit is
        # a sequence of 2 digits forming a number between 01 and 97. This number is equal to 97
        # minus the remainder of the division by 97 of the number formed:
        # - either by the first 9 digits of the national number for people born before the 1st
        # January 2000.
        # - either by the number 2 followed by the first 9 digits of the national number for people
        # born after December 31, 1999.
        # (https://fr.wikipedia.org/wiki/Num%C3%A9ro_de_registre_national)
        self.ensure_one()
        niss = self.niss
        if niss == '/':
            return True
        if not niss or len(niss) != 11:
            return False
        return self._validate_niss(niss)

    @api.onchange('new_bike')
    def _onchange_new_bike(self):
        self.version_id._onchange_new_bike()

    @api.onchange('other_dependents')
    def _onchange_other_dependents(self):
        if not self.other_dependents:
            self.children = 0
            self.other_disabled_juniors_dependent = 0
            self.other_juniors_dependent = 0
            self.other_senior_dependent = 0

    @api.onchange('other_juniors_dependent')
    def _onchange_other_juniors_dependent(self):
        if not self.other_juniors_dependent:
            self.other_disabled_juniors_dependent = 0

    @api.onchange('children')
    def _onchange_children(self):
        if not self.children:
            self.disabled_children_number = 0

    @api.onchange('transport_mode_car', 'private_car_employee_kilometer', 'train_transport_employee_kilometer',
        'bus_transport_employee_amount', 'tram_transport_employee_amount', 'metro_transport_employee_amount',
        'bike_transport_employee_kilometer', 'new_bike')
    def _onchange_transport_mode(self):
        self.version_id._onchange_transport_mode()

    @api.onchange('niss')
    def _onchange_niss(self):
        self._parse_niss()

    @api.onchange('contract_date_start')
    def _onchange_seniority_inputs(self):
        self.version_id.sudo()._compute_l10n_be_computed_seniority()

    @api.model
    def _get_invalid_niss_employee_ids(self):
        res = self.search_read([
            ('company_id', 'in', self.env.companies.filtered(lambda c: c.country_id.code == 'BE').ids),
            ('contract_date_start', '!=', None),
        ], ['id', 'niss'])
        return [row['id'] for row in res if not row['niss'] or (row['niss'] != '/' and not self._validate_niss(row['niss']))]

    def _get_first_versions(self, date_limit=date.max):
        self.ensure_one()
        versions = super()._get_first_versions(date_limit)
        return versions.filtered(
            lambda v: v.company_id.country_id.code != 'BE' or (v.company_id.country_id.code == 'BE' and not v.is_PFI())
        )

    def _create_public_holiday_allocations(self):
        public_holiday_compensation_type = self.env['hr.work.entry.type'].search([('code', '=', '006.15'), ('country_id.code', '=', 'BE')])
        if not public_holiday_compensation_type:
            return

        eligible_employees = self.filtered(lambda emp: emp.active and emp.l10n_be_worker_code_id)
        if not eligible_employees:
            return

        all_versions = eligible_employees.version_ids.filtered('contract_date_start')
        if not all_versions:
            return
        min_contract_start = min(all_versions.mapped('contract_date_start'))
        max_contract_end = max(
            (v.contract_date_end for v in all_versions if v.contract_date_end),
            default=None,
        ) if all(v.contract_date_end for v in all_versions) else None

        domain = [
            ('company_id', 'in', eligible_employees.company_id.ids),
            ('calendar_id', 'in', all_versions.resource_calendar_id.ids + [False]),
            ('resource_id', '=', False),
            ('date_to', '>=', min_contract_start),
        ]
        if max_contract_end:
            domain.append(('date_from', '<=', max_contract_end))

        public_holidays = self.env['resource.calendar.leaves'].search(domain)
        if not public_holidays:
            return

        existing_allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', 'in', eligible_employees.ids),
            ('public_holiday_id', 'in', public_holidays.ids),
        ])
        existing_pairs = {(rec.employee_id.id, rec.public_holiday_id.id) for rec in existing_allocations}
        allocations_vals = []

        for employee in eligible_employees:
            company_tz = ZoneInfo(employee.company_id.tz or self.env.user.tz or 'UTC')
            for leave in public_holidays:
                if (employee.id, leave.id) in existing_pairs:
                    continue
                if leave.company_id != employee.company_id:
                    continue

                leave_date_from = leave.date_from.astimezone(company_tz).date()
                leave_date_to = leave.date_to.astimezone(company_tz).date()

                employee_days = 0
                for version in employee.version_ids.filtered('contract_date_start'):
                    if leave.calendar_id and leave.calendar_id != version.resource_calendar_id:
                        continue

                    version_start = version.contract_date_start
                    version_end = version.contract_date_end

                    overlap_start = max(leave_date_from, version_start)
                    overlap_end = min(leave_date_to, version_end or leave_date_to)

                    if overlap_end < overlap_start:
                        continue

                    current_date = overlap_start
                    while current_date <= overlap_end:
                        if not employee.company_id.resource_calendar_id._works_on_date(current_date):
                            employee_days += 1
                        current_date += timedelta(days=1)

                if not employee_days:
                    continue

                allocations_vals.append({
                    'name': self.env._("%(leave_name)s Compensation (%(days)s day(s))", leave_name=leave.name or self.env._("Public Holiday"), days=employee_days),
                    'work_entry_type_id': public_holiday_compensation_type.id,
                    'number_of_days': employee_days,
                    'employee_id': employee.id,
                    'state': 'confirm',
                    'date_from': leave_date_to.replace(day=1),
                    'date_to': leave_date_to.replace(day=31, month=12),
                    'public_holiday_id': leave.id,
                })

        created_allocations = self.env['hr.leave.allocation'].create(allocations_vals)
        created_allocations.action_approve()

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            for employee_sudo in self.sudo():
                # As this is impossible to archive a version if it's the only employee version
                # could be required to cancel a dimona if there was no date_end on the dimona
                # IN and we archive the employee itself.
                if employee_sudo.active and len(employee_sudo.version_ids) == 1 and employee_sudo.version_ids.l10n_be_dimona_declaration_id and not employee_sudo.version_ids.l10n_be_dimona_declaration_id.date_end:
                    employee_sudo.version_ids.l10n_be_needs_dimona_cancel = True
        if 'lang' in vals:
            lang = self.env['res.lang'].with_context(active_test=False).search([('code', '=', vals['lang'])])
            if lang and not lang.active:
                self.env['base.language.install'].create({'lang_ids': [(6, 0, lang.ids)]}).lang_install()
        result = super().write(vals)

        if 'mobility_card' in vals:
            car_ids = self.env['fleet.vehicle'].sudo().search([
                ('driver_employee_id', 'in', self.ids),
            ])
            car_ids._compute_mobility_card()

        if 'contract_date_start' in vals:
            contract_date_start = vals['contract_date_start']
            if isinstance(contract_date_start, str):
                contract_date_start = datetime.strptime(contract_date_start, "%Y-%m-%d")
            outside_contract_public_holidays = self.env['hr.leave.allocation'].search([
                ('employee_id', 'in', self.ids),
                ('public_holiday_id.date_from', '<', contract_date_start),
            ])
            outside_contract_public_holidays.action_refuse()
            outside_contract_public_holidays.unlink()

            self.sudo()._create_public_holiday_allocations()

        if 'contract_date_end' in vals:
            contract_date_end = vals['contract_date_end']
            if isinstance(contract_date_end, str):
                contract_date_end = datetime.strptime(contract_date_end, "%Y-%m-%d")
            outside_contract_public_holidays = self.env['hr.leave.allocation'].search([
                ('employee_id', 'in', self.ids),
                ('public_holiday_id.date_to', '>', contract_date_end),
            ])
            outside_contract_public_holidays.action_refuse()
            outside_contract_public_holidays.unlink()

            self.sudo()._create_public_holiday_allocations()

        return result

    @api.model_create_multi
    def create(self, vals_list):
        employees = super(HrEmployee, self.with_context(pending_employee_creation=True)).create(vals_list)
        updated_context = dict(employees.env.context)
        updated_context.pop('pending_employee_creation')
        created_employees = employees.with_context(updated_context)
        created_employees.sudo().filtered(
            lambda v: v.current_version_id._is_struct_from_country('BE') and v.current_version_id.contract_date_start
        )._trigger_l10n_be_next_activities()
        employees.sudo()._create_public_holiday_allocations()
        return created_employees

    def _compute_current_version_id(self):
        prev_current_version_id_by_employee = self.current_version_id.grouped('employee_id')
        super()._compute_current_version_id()
        to_trigger_next_activities = self.filtered(
            lambda e: e.current_version_id and (not prev_current_version_id_by_employee.get(e) or
                prev_current_version_id_by_employee.get(e) != e.current_version_id)
        )
        if to_trigger_next_activities:
            to_trigger_next_activities.sudo().filtered(
                lambda e: e.current_version_id._is_struct_from_country('BE') and e.current_version_id.contract_date_start
            )._trigger_l10n_be_next_activities()

    def _create_credit_time_next_activity(self):
        self.ensure_one()
        part_time_link = "https://www.socialsecurity.be/site_fr/employer/applics/elo/index.htm"
        part_time_link = '<a href="%s" target="_blank">%s</a>' % (part_time_link, part_time_link)
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            note=self.env._('Part Time of %(employee)s must be stated at %(link)s.',
                   employee=self.name,
                   link=part_time_link),
            user_id=self.current_version_id.hr_responsible_id.id or self.env.user.id,
            summary=self.env._('Part Time'),
            technical_usage='l10n_be_hr_payroll_part_time',
        )

    def _create_dimona_next_activity(self):
        dimona_link = "https://www.socialsecurity.be/site_fr/employer/applics/dimona/index.htm"
        dimona_link = '<a href="%s" target="_blank">%s</a>' % (dimona_link, dimona_link)
        for employee in self:
            employee.activity_schedule(
                'mail.mail_activity_data_todo',
                note=self.env._('State the Dimona at %(link)s to declare the arrival of %(employee)s.',
                    link=dimona_link,
                    employee=employee.name),
                user_id=employee.current_version_id.hr_responsible_id.id or self.env.user.id,
                summary='Dimona',
                technical_usage='l10n_be_hr_payroll_dimona',
            )

    def _trigger_l10n_be_next_activities(self):
        if self.env.context.get('pending_employee_creation'):
            return
        activities_by_usage = dict(
            self.env['mail.activity']._read_group(
                domain=[
                    ('res_model', '=', 'hr.employee'),
                    ('res_id', 'in', self.ids),
                    ('technical_usage', 'in', ['l10n_be_hr_payroll_dimona', 'l10n_be_hr_payroll_part_time']),
                ],
                groupby=['technical_usage'],
                aggregates=['id:recordset'],
            )
        )
        dimona_activities = activities_by_usage.get('l10n_be_hr_payroll_dimona', self.env['mail.activity'])
        part_time_activities = activities_by_usage.get('l10n_be_hr_payroll_part_time', self.env['mail.activity'])

        for employee in self.filtered('id'):
            has_part_time_activity = any(activity.res_id == employee.id
                and activity.date_deadline >= employee.current_version_id.contract_date_start
                for activity in part_time_activities)
            if employee.current_version_id.l10n_be_time_credit and not has_part_time_activity:
                employee._create_credit_time_next_activity()

        dimona_to_do_employees = self.filtered(
            lambda e: e.id
            and e.id not in dimona_activities.mapped('res_id')
            and e.current_version_id.l10n_be_joint_committee_id.egov3_code != '999'
        )
        if dimona_to_do_employees:
            dimona_to_do_employees._create_dimona_next_activity()

    def action_open_relation(self):
        self.ensure_one()
        return {
            'name': self.env._('Dimona Relation'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_id': self.l10n_be_dimona_relation_id.id,
            'res_model': 'l10n.be.dimona.relation',
        }

    def action_open_flxwage_declarations(self):
        self.ensure_one()
        return {
            'name': self.env._('Flexi@Work'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.be.flexi.at.work',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
        }

    # --- Holiday Attest Helper Methods --- #
    def _get_simple_holiday_pay_recoverable_amount(self, year):
        self.ensure_one()
        return sum(a.simple_holiday_pay_cap for a in self.l10n_be_holiday_attest_ids if a.year == year)

    def get_l10n_be_holiday_attest_occupations(self, year):
        first_of_year = date(year, 1, 1)
        last_of_year = min(date(year, 12, 31), self.departure_date or date.today())
        versions = self.version_ids.filtered(
            lambda v: v._is_overlapping_period(first_of_year, last_of_year)
        )
        if not versions:
            return []
        occupations = []
        occupation_dates = versions._get_occupation_dates()
        for idx, (occ_versions, date_from, date_to) in enumerate(occupation_dates):
            base_version = occ_versions[0]
            next_occupation = occupation_dates[idx + 1] if idx < len(occupation_dates) - 1 else None
            date_start_next_occupation = next_occupation[1] - relativedelta(days=1) if next_occupation else False
            attest_worked_days = occ_versions._get_l10n_be_holiday_attest_worked_days(
                max(first_of_year, date_from), min(date_to or date.max, last_of_year)
            )
            occupations.append({
                'date_start': max(first_of_year, base_version.date_version),
                'date_end': date_start_next_occupation or last_of_year,
                'hours_per_week': float_round(base_version.resource_calendar_id.hours_per_week, 2),
                'days_per_week': float_round(base_version.resource_calendar_id.days_per_week, 2),
                'reference_hours_per_week': float_round(base_version.reference_calendar_id.hours_per_week, 2) if base_version.reference_calendar_id else 0,
                'equivalent_days': attest_worked_days['equivalent_days'],
                'senior_youth_leaves': attest_worked_days['senior_youth_leaves'],
                'european_leaves': attest_worked_days['european_leaves'],
                'paid_leaves': attest_worked_days['paid_leaves'],
                'non_equivalent_days': attest_worked_days['non_equivalent_days'],
                'european_leaves_amount': attest_worked_days['european_leaves_amount']
            })
        return occupations

    def _l10n_be_get_last_year_average_variable_revenues(self, date_from):
        self.ensure_one()
        first_version_date = self._get_first_contract_date()
        if not first_version_date:
            return 0
        start = first_version_date
        end = date_from + relativedelta(day=31, months=-1)
        number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
        number_of_month = min(12, number_of_month)
        if number_of_month <= 0:
            return 0
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_from + relativedelta(months=-12, day=1)),
            ('date_from', '<=', date_from + relativedelta(months=-1, day=31)),
        ], order="date_from asc")
        variable_codes = ['COMMISSION', 'COMMISSION_ADV', 'SIMPLE_VARIABLE', 'DOUBLE_VARIABLE']
        line_values = payslips._get_line_values(variable_codes, compute_sum=True)
        total_amount = sum(line_values[code]['sum']['total'] for code in variable_codes)
        return total_amount / number_of_month if number_of_month else 0

    def _l10n_be_get_sick_leave_twelve_months_cutoff_date(self, reference_date, current_leave=None):
        """Return the twelve-month sickness cutoff for the relevant sickness chain.

        When a current leave is provided, only its explicit relapse chain is considered.
        This preserves a deliberate fresh-sickness choice while still accounting for an
        overlapping partial-incapacity period.
        """
        self.ensure_one()
        if current_leave:
            sick_leaves = []
            chain_leave = current_leave
            while chain_leave:
                sick_leaves.append(chain_leave)
                chain_leave = chain_leave.l10n_be_sickness_relapse_origin_leave_id
        else:
            sick_work_entry_type_codes = [
                '013.00',     # Sick Time Off
                '122.04',     # Partial Incapacity
                '122.00',     # days of illness after 30th day
                '123.00',     # Long Term Sick
            ]
            sick_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', self.id),
                ('date_from', '<=', reference_date),
                ('work_entry_type_id.code', 'in', sick_work_entry_type_codes),
                ('state', '=', 'validate'),
            ], order='date_from desc')

        # Versions whose calendar has partial incapacity attendances are treated as sick periods.
        partial_incapacity_versions = self.sudo().version_ids.filtered(
            lambda version: version.date_start <= reference_date
                and any(
                    attendance.work_entry_type_id.code == '122.04'
                    for attendance in version.resource_calendar_id.attendance_ids
                )
        )
        if current_leave:
            partial_incapacity_versions = partial_incapacity_versions.filtered(
                lambda version: any(
                    version.date_start <= leave.request_date_to + relativedelta(days=1)
                    and (version.date_end or date.max) >= leave.request_date_from - relativedelta(days=1)
                    for leave in sick_leaves
                )
            )
        sick_version_periods = [
            SimpleNamespace(
                request_date_from=version.date_start,
                request_date_to=min(version.date_end or date.max, reference_date),
                l10n_be_sickness_relapse=True,
            )
            for version in partial_incapacity_versions
        ]

        # Merge overlapping or adjacent periods so a sick leave inside a version period
        # does not cause a false gap when walking the relapse chain.
        sick_periods = sorted(
            [
                SimpleNamespace(
                    request_date_from=leave.request_date_from,
                    request_date_to=leave.request_date_to,
                    l10n_be_sickness_relapse=leave.l10n_be_sickness_relapse,
                )
                for leave in sick_leaves
            ] + sick_version_periods,
            key=lambda period: period.request_date_from,
        )
        merged_sick_periods = []
        for sick_period in sick_periods:
            if (
                merged_sick_periods
                and (sick_period.request_date_from - merged_sick_periods[-1].request_date_to).days <= 1
            ):
                previous_period = merged_sick_periods[-1]
                previous_period.request_date_to = max(previous_period.request_date_to, sick_period.request_date_to)
                previous_period.l10n_be_sickness_relapse |= sick_period.l10n_be_sickness_relapse
            else:
                merged_sick_periods.append(sick_period)

        all_sick_periods = list(reversed(merged_sick_periods))
        if not all_sick_periods:
            return date.max

        if current_leave:
            considered_periods = all_sick_periods
            current_period = all_sick_periods[-1]
        else:
            current_period = all_sick_periods[0]
            considered_periods = [current_period]
            relapse_period = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
                'sickness_relapse_period_days', date=reference_date
            )
            previous_periods = [
                period
                for period in all_sick_periods
                if period.request_date_from < current_period.request_date_from
            ]
            for index, previous_period in enumerate(previous_periods):
                days_between_periods = (
                    current_period.request_date_from - previous_period.request_date_to
                ).days - 1
                if days_between_periods > relapse_period:
                    break
                is_first_sick_period = index == len(previous_periods) - 1
                if is_first_sick_period or previous_period.l10n_be_sickness_relapse:
                    current_period = previous_period
                    considered_periods.append(current_period)

        min_cutoff_date = current_period.request_date_from + relativedelta(months=12)
        if not considered_periods:
            return min_cutoff_date

        periods_before_cutoff = [period for period in considered_periods if period.request_date_from <= min_cutoff_date]
        if not periods_before_cutoff:
            return min_cutoff_date
        last_period_before_cutoff = max(periods_before_cutoff, key=lambda period: period.request_date_from)

        sorted_periods = sorted(
            [period for period in considered_periods if period.request_date_from <= last_period_before_cutoff.request_date_from],
            key=lambda period: period.request_date_from,
        )
        days_between_periods_to_report = sum(
            max(0, (curr.request_date_from - prev.request_date_to).days - 1)
            for prev, curr in pairwise(sorted_periods)
        )
        return min_cutoff_date + relativedelta(days=days_between_periods_to_report)

    def _get_fictitious_remuneration_previous_year(self, date_from, payslips=None):
        self.ensure_one()
        payslips_n1 = payslips or self.env['hr.payslip'].search([
            ('employee_id', '=', self.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_from.replace(month=1, day=1) + relativedelta(years=-1)),
            ('date_from', '<=', date_from.replace(month=12, day=31) + relativedelta(years=-1)),
        ])
        if not payslips_n1:
            return 0.0
        last_day_previous_year = date_from.replace(month=12, day=31) - relativedelta(years=1)
        variable_monthly_salary = self._l10n_be_get_last_year_average_variable_revenues(last_day_previous_year)
        unpaid_and_unassimilated_codes = self.env['hr.work.entry.type'].search([
            ('category_ids.code', '=', 'UNASSIMILATED')
        ]).mapped('code')
        excluded_codes = unpaid_and_unassimilated_codes + ['000.00']
        equivalent_worked_days = payslips_n1.worked_days_line_ids.filtered(
            lambda wd: not wd.is_paid and wd.code not in excluded_codes
        )
        fictitious_remuneration_base = 0.0
        for version, worked_days in equivalent_worked_days.grouped('version_id').items():
            days = sum(worked_days.mapped('number_of_days'))
            fixed_monthly_salary = version._get_contract_wage()
            fictitious_remuneration_base += days * (fixed_monthly_salary + variable_monthly_salary)

        return fictitious_remuneration_base * 3 / 13 / 5

    def _get_payslips_for_year(self, reference_year, struct_codes):
        """
        Returns all payslips for the calendar year, including existing future payslips.
        """
        self.ensure_one()
        current_year = date(reference_year, 1, 1)
        next_year = current_year + relativedelta(years=1)

        structures = self.env['hr.payroll.structure'].search(
            domain=[('code', 'in', struct_codes)]
        )

        return self.env['hr.payslip'].search([
            ('employee_id', '=', self.id),
            ('date_to', '>=', current_year),
            ('date_from', '<', next_year),
            ('state', 'in', ['validated', 'paid']),
            ('struct_id', 'in', structures.ids)
        ])

    def _get_average_rd_percentage(self, structure_code, use_date) -> float:
        """
            Calculate average rd_percentage to use on 'date' based on the pay type (structure_code)

            it's the weighted average of rd_percentage over
            all versions in the concerned interval of time
            interval depends on the structure
            End Of Year Bonus, BeholN -> current year versions
            Double Holiday, BeholN1 -> previous year versions
            Termination -> ytd versions
        """
        if not use_date:
            use_date = date.today()

        if structure_code in ['BETHIRTEEN', 'BEHOLN']:
            interval_start = date(use_date.year, 1, 1)
            interval_end = min(date(use_date.year, 12, 31), self.departure_date or date.max)
        elif structure_code in ['BEDOUBLE', 'BEHOLN1']:
            interval_start = date(use_date.year - 1, 1, 1)
            interval_end = date(use_date.year - 1, 12, 31)
        elif structure_code in ['BETERM']:
            departure_date = self.departure_date or use_date
            interval_start = departure_date - relativedelta(years=1)
            interval_end = departure_date
        else:
            return self._get_version(use_date).rd_percentage

        versions = self.version_ids.filtered(
            lambda v: v.date_start
                and v.date_start <= interval_end
                and (not v.date_end or v.date_end >= interval_start)
        )

        total_weight = 0.0
        weighted_sum = 0.0

        for version in versions:
            effective_start = max(version.date_start, interval_start)
            effective_end = min((version.date_end or interval_end), interval_end)

            weight = (effective_end - effective_start).days + 1

            total_weight += weight
            weighted_sum += weight * version.rd_percentage

        return float(weighted_sum / total_weight) if total_weight else 0

    def _get_first_contract_date(self, date_limit=date.max):
        if self.company_id.country_id.code == 'BE' and self.l10n_be_fictive_hire_date and self.l10n_be_fictive_hire_date <= date_limit:
            return self.l10n_be_fictive_hire_date
        return super()._get_first_contract_date(date_limit=date_limit)

    @api.model
    def _l10n_be_age_at_quarter_end(self, employee, date_ref):
        _, quarter_end = date_utils.get_quarter(date_ref)
        return employee._get_age(target_date=quarter_end)

    def action_create_allocation(self):
        default_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_legal_leave')
        if not default_work_entry_type:
            raise UserError(
                self.env._(
                    "There is no time type linked to the Paid Time Off time type.",
                ),
            )
        vals_list = []
        for employee in self:
            vals_list.append({
                'name': f'{default_work_entry_type.name} Allocation',
                'work_entry_type_id': default_work_entry_type.id,
                'number_of_days': employee.l10n_be_holiday_pay_number_of_days_n1,
                'employee_id': employee.id,
                'state': 'confirm',
                'date_from': date(employee.first_contract_date.year, 1, 1),
                'date_to': date(employee.first_contract_date.year, 12, 31),
            })
        allocations = self.env['hr.leave.allocation'].create(vals_list)

        if len(allocations) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'hr.leave.allocation',
                'res_id': allocations.id,
                'view_ids': [('form')],
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.allocation',
            'view_ids': [('list')],
            'view_mode': 'list',
            'domain': [('id', 'in', allocations.ids)],
        }

    def action_view_allocations(self):
        self.ensure_one()
        return {
            'name': self.env._('Holiday Allocations'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.allocation',
            'view_ids': [('list')],
            'view_mode': 'list',
            'domain': [
                ('employee_id', '=', self.id),
                ('date_from', '=', date(self.first_contract_date.year, 1, 1)),
                ('date_to', '=', date(self.first_contract_date.year, 12, 31)),
                ('work_entry_type_id.code', '=', '016.00'),
            ],
            'context': {'default_employee_id': self.id},
        }

    def action_generate_termination_payslip(self):
        self.ensure_one()
        if not self.departure_id:
            raise UserError(self.env._("You can't generate termination fees for an employee without a departure."))
        return self.departure_id.action_generate_termination_payslip()

    def action_generate_termination_holidays(self):
        self.ensure_one()
        if not self.departure_id:
            raise UserError(self.env._("You can't generate termination holiday attests for an employee without a departure."))
        return self.departure_id.action_generate_termination_holidays()

    def action_generate_termination_thirteen_month(self):
        self.ensure_one()
        if not self.departure_id:
            raise UserError(self.env._("You can't generate a 13th month payslip for an employee without a departure."))
        return self.departure_id.action_generate_termination_thirteen_month()

    def action_report_employment_certificate(self):
        self.ensure_one()

        pdf, _mime = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            self.env.ref('l10n_be_hr_payroll.action_report_employment_certificate').sudo(),
            self.ids,
        )

        attachment = self.env['ir.attachment'].create({
            'name': self.env._('Employment_Certificate_%s.pdf', self.name.replace(" ", "_")),
            'type': 'binary',
            'raw': pdf,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        self.message_post(
            body=self.env._("Employment certificate generated."),
            attachment_ids=[attachment.id],
        )

        return attachment

    def l10n_be_get_last_work_day_of_year(self, year: int) -> date | None:
        self.ensure_one()
        year_beg = date(year, 1, 1)
        year_end = date(year, 12, 31)

        # the last in contract day of the year can be the last work day of the year
        contract_ends = self.version_ids.filtered_domain(Domain.OR([
            Domain('contract_date_end', '=', False),
            Domain([
                ('contract_date_end', '>=', year_beg),
                ('contract_date_end', '<=', year_end),
            ]),
        ])).mapped('contract_date_end')
        if not contract_ends:
            contract_ends = [date.max]
        last_contract_end = max((contract_end or date.max) for contract_end in contract_ends)

        departure_date = self.departure_date or date.max

        last_work_day = min(last_contract_end, departure_date)

        if last_work_day < year_beg:
            return None  # no work day in the year

        # if the employee continues working after the year, then the last work
        # day it the last day of the year
        return min(last_work_day, year_end)

    def action_l10n_be_remove_from_dmfa(self):
        dmfa_id = self.env.context.get("dmfa_id")
        if not dmfa_id:
            return
        dmfa = self.env["l10n_be.dmfa"].browse(dmfa_id)
        payslips_to_remove = dmfa.payslip_ids.filtered(lambda p: p.employee_id in self)
        if payslips_to_remove:
            dmfa.payslip_ids = [(3, payslip.id) for payslip in payslips_to_remove]
        return dmfa.action_show_related_payslips()

    def action_open_employee_overtime(self):
        self.ensure_one()
        overtime_work_entry_types = self.env['hr.work.entry.type'].search([
            ('category_ids', 'in', self.env.ref('hr_payroll.EXTRA_HOURS').id),
            ('country_id.code', 'in', [False, 'BE']),
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Overtime'),
            'views': [(self.env.ref('l10n_be_hr_payroll.hr_leave_view_pivot_overtime').id, "pivot")],
            'search_view_id': [self.env.ref("hr_holidays.view_hr_holidays_filter").id, 'search'],
            'res_model': 'hr.leave',
            'view_mode': 'pivot',
            'domain': [('employee_id', '=', self.id), ('work_entry_type_id', 'in', overtime_work_entry_types.ids)],
            'context': {
                'default_employee_id': self.id,
                'search_default_filter_date_from': 1,
            },
        }

    def _store_avatar_card_fields(self, res):
        super()._store_avatar_card_fields(res)
        if self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            res.one("company_id", ["country_code"])
            res.extend(["l10n_be_computed_seniority_years", "l10n_be_computed_seniority_months",
                        "l10n_be_scale_seniority", "l10n_be_scale_seniority_months", "l10n_be_company_seniority_years",
                        "l10n_be_company_seniority_months", "l10n_be_egov3_code"])
            res.one("l10n_be_salary_scale_id", ["name"])

    @api.depends('company_id', 'company_id.l10n_be_dimona_environment')
    def _compute_show_dimona_button(self):
        is_dev = self.env.user.has_group('base.group_no_one')
        is_sandbox = self.company_id.l10n_be_dimona_environment == 'sandbox'
        for record in self:
            record.show_dimona_button = is_dev or is_sandbox

    def _compute_l10n_be_long_sick_leave(self):
        matching_employees = self._get_l10n_be_versions_on_mutual_health()
        for employee in self:
            employee.l10n_be_long_sick_leave = employee in matching_employees

    def _get_l10n_be_versions_on_mutual_health(self):
        belgian_companies = self.env.companies.filtered(lambda c: c.country_id.code == 'BE')
        sick_work_entry_type_codes = [
            "122.00",     # days of illness after 30th day
            "123.00",     # Long Term Sick
        ]
        today = fields.Date.today()

        current_long_or_part_sick_leaves = self.env["hr.leave"].search([
            ('employee_company_id', 'in', belgian_companies.ids),
            ("state", "=", "validate"),
            ("work_entry_type_id.code", "in", sick_work_entry_type_codes),
            ("date_from", "<=", today),
            ("date_to", ">=", today),
        ])

        return current_long_or_part_sick_leaves.employee_id

    def _search_l10n_be_long_sick_leave(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError()
        belgian_companies = self.env.companies.filtered(lambda company: company.country_id.code == "BE")
        candidate_employees = self.search([
            ("company_id", "in", belgian_companies.ids),
        ])
        matching_employees = (candidate_employees._get_l10n_be_versions_on_mutual_health())
        search_for_matching = (operator == "=" and value or operator == "!=" and not value)
        return [(
                "id",
                "in" if search_for_matching else "not in",
                matching_employees.ids,
            )]

    def _get_l10n_be_mobility_budget_amount_prorated(self, reference_date=None, year=None):
        """
        reference_date: if earlier than the end of the year, the last version is assumed to end at this date.
        year: year for which the prorated mobility budget is calculated. Defaults to the current year.
        """
        today = fields.Date.context_today(self)
        reference_date = reference_date or today
        year = int(year or today.year)

        start_of_year = date(year, 1, 1)
        end_of_year = date(year, 12, 31)
        end_of_period = max(start_of_year, min(end_of_year, reference_date))
        days_in_year = (end_of_year - start_of_year).days + 1

        version_periods = self._get_version_periods(start_of_year, end_of_period)
        mobility_budget_amount_prorated_by_employee = {}

        for employee in self:
            mobility_budget_amount_prorated = 0.0
            versions_in_year = version_periods.get(employee, [])

            employee_end_date = (min(end_of_period, employee.departure_date) if employee.departure_date else end_of_period)

            for date_start, date_end, version in versions_in_year:
                if not version.l10n_be_mobility_budget or date_start > employee_end_date:
                    continue

                date_end = min(date_end, employee_end_date)
                period_days = (date_end - date_start).days + 1
                mobility_budget_amount_prorated += version.l10n_be_mobility_budget_amount * period_days / days_in_year

            mobility_budget_amount_prorated_by_employee[employee.id] = mobility_budget_amount_prorated

        return mobility_budget_amount_prorated_by_employee

    def _get_l10n_be_mobility_payslip_lines(self, date_start, date_end):
        """
        Batch-fetch MOBILITY_TO_PAY amounts for all BEMONTHLY payslips (validated/paid) of the employees in self, within [date_start, date_end], in a single query.
        Returns a list of (employee_id, date_from, amount) tuples
        """
        payslips = self.env['hr.payslip'].sudo().search([
            ('employee_id', 'in', self.ids),
            ('date_from', '>=', date_start),
            ('date_from', '<=', date_end),
            ('state', 'in', ('validated', 'paid')),
            ('struct_id.code', '=', 'BEMONTHLY'),
        ])
        if not payslips:
            return []

        line_values = payslips._get_line_values(['MOBILITY_TO_PAY', 'MOBILITY_PAYMENT'])

        return [
            (
                slip.employee_id.id,
                slip.date_from,
                line_values['MOBILITY_TO_PAY'][slip.id]['total'],
                line_values['MOBILITY_PAYMENT'][slip.id]['total'],
            )
            for slip in payslips
        ]

    def _get_l10n_be_paid_mobility_amounts(self, date_start, date_end):
        """
        Return mobility amounts already paid through validated/paid payslips during the given period.
        Returns:
            yearly_amounts: {(employee_id, year): amount}
            monthly_amounts: {(employee_id, year, month): amount}

        Extended in l10n_be_hr_payroll_expense with reimbursed mobility expenses.
        """
        yearly_amounts = defaultdict(float)
        monthly_amounts = defaultdict(float)

        payslip_lines = self._get_l10n_be_mobility_payslip_lines(date_start=date_start, date_end=date_end)

        for employee_id, payslip_date, pillar_2_amount, pillar_3_amount in payslip_lines:
            yearly_amounts[employee_id, payslip_date.year] += pillar_2_amount + pillar_3_amount
            monthly_amounts[employee_id, payslip_date.year, payslip_date.month] += pillar_2_amount + pillar_3_amount

        return yearly_amounts, monthly_amounts


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    mobility_card = fields.Char(readonly=True)
