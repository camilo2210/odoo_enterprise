# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.addons.l10n_ph.models.res_partner import split_name  # noqa: OLS03003

import re

VAT_REG = re.compile(r"^\d{3}-?\d{3}-?\d{3}-?(\d{3,5})?$")


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Note: this is needed for employee tax declarations. It should also affect the withholding tax calculation, this will be done separately.
    l10n_ph_hr_payroll_is_main_employment = fields.Boolean(readonly=False, related="version_id.l10n_ph_hr_payroll_is_main_employment", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ph_hr_payroll_minimum_wage_earner = fields.Boolean(readonly=False, related="version_id.l10n_ph_hr_payroll_minimum_wage_earner", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ph_hr_payroll_employee_rank = fields.Selection(readonly=False, related="version_id.l10n_ph_hr_payroll_employee_rank", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ph_hr_payroll_prev_employment_id = fields.Many2one(
        readonly=False,
        related="version_id.l10n_ph_hr_payroll_prev_employment_id",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
        domain="[('employee_id', '=', id)]",
        tracking=True,
    )
    l10n_ph_hr_payroll_philhealth_pin = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_philhealth_pin", inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_sss_number = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_sss_number", inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_pag_ibig_mid = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_pag_ibig_mid", inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_rdo_code = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_rdo_code", inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_registered_address = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_registered_address", tracking=True, inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_registered_zip = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_registered_zip", tracking=True, inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_foreign_address = fields.Char(readonly=False, related="version_id.l10n_ph_hr_payroll_foreign_address", tracking=True, inherited=True, groups="hr.group_hr_user")
    l10n_ph_hr_payroll_daily_wage = fields.Monetary(readonly=False, related="version_id.l10n_ph_hr_payroll_daily_wage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ph_hr_payroll_work_tin = fields.Char('TIN', store=True, readonly=False, tracking=True, compute="_compute_work_contact_details", inverse='_inverse_work_contact_details', groups="hr.group_hr_user")
    l10n_ph_hr_payroll_work_tin_branch_code = fields.Char('Branch Code', compute="_compute_l10n_ph_branch_code", groups="hr.group_hr_user")
    # We need the last name separately for legal declaration, as it is part of the file name of 2316 and we need 1604-C to be alphabetically ordered by the last name.
    l10n_ph_legal_first_name = fields.Char(compute="_compute_l10n_ph_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ph_legal_middle_name = fields.Char(compute="_compute_l10n_ph_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ph_legal_last_name = fields.Char(compute="_compute_l10n_ph_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")
    l10n_ph_legal_suffix = fields.Char(compute="_compute_l10n_ph_legal_name", store=True, readonly=False, tracking=True, groups="hr.group_hr_user")

    @api.depends('work_contact_id.vat')
    def _compute_work_contact_details(self):
        super()._compute_work_contact_details()
        for employee in self:
            if employee.country_code != 'PH':
                continue
            if employee.work_contact_id:
                if len(employee.work_contact_id.employee_ids) <= 1:
                    employee.l10n_ph_hr_payroll_work_tin = employee.work_contact_id.vat

    @api.depends('l10n_ph_hr_payroll_work_tin')
    def _compute_l10n_ph_branch_code(self):
        for employee in self:
            if employee.country_code != 'PH' or not employee.l10n_ph_hr_payroll_work_tin:
                employee.l10n_ph_hr_payroll_work_tin_branch_code = False
                continue

            match = VAT_REG.match(employee.l10n_ph_hr_payroll_work_tin)
            branch_code = (match and match.group(1)) or employee.l10n_ph_hr_payroll_work_tin_branch_code
            employee.l10n_ph_hr_payroll_work_tin_branch_code = branch_code

    def _inverse_work_contact_details(self):
        super()._inverse_work_contact_details()
        for employee in self:
            if employee.country_code != 'PH':
                continue
            if len(employee.work_contact_id.employee_ids) <= 1:
                employee.work_contact_id.sudo().vat = employee.l10n_ph_hr_payroll_work_tin

    def _get_splitting_legal_name_countries(self):
        return super()._get_splitting_legal_name_countries() + ['PH']

    @api.depends("name")
    def _compute_l10n_ph_legal_name(self):
        for employee in self:
            if employee.country_code != 'PH':
                continue

            first, middle, last, suffix = split_name(employee.name) if employee.name else ('', '', '', '')

            employee.l10n_ph_legal_first_name = first or False
            employee.l10n_ph_legal_middle_name = middle or False
            employee.l10n_ph_legal_last_name = last or False
            employee.l10n_ph_legal_suffix = suffix or False

    @api.depends('l10n_ph_legal_first_name', 'l10n_ph_legal_middle_name', 'l10n_ph_legal_last_name')
    def _compute_legal_name(self):
        ph_employees = self.filtered(lambda e: e.country_code == 'PH')
        for employee in ph_employees:
            # We keep middle name optional, though very common
            if employee.l10n_ph_legal_first_name and employee.l10n_ph_legal_last_name:
                employee.legal_name = ' '.join(
                    filter(None, [employee.l10n_ph_legal_first_name, employee.l10n_ph_legal_middle_name, employee.l10n_ph_legal_last_name])
                )
            else:
                employee.legal_name = employee.name
        super(HrEmployee, self - ph_employees)._compute_legal_name()

    def _l10n_ph_get_previous_employment(self, at_date):
        """
        Small helper to return the previous employment only if it is relevant to the provided date.
        Returns an empty recordset if no previous employment is available or if it isn't relevant to the provided_date.
        """
        self.ensure_one()
        is_first_year = self.first_contract_date and self.first_contract_date.year == at_date.year
        return self.l10n_ph_hr_payroll_prev_employment_id if is_first_year else self.env['l10n_ph_hr_payroll.previous_employment']
