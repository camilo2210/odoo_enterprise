from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

import re


class HrWorkLocation(models.Model):
    _inherit = 'hr.work.location'

    name = fields.Char(compute='_compute_name', store=True, readonly=False, translate=True, required=True, precompute=True)
    bce_code = fields.Char(string="BCE Code", help="The local establishment unit identification number is the number assigned by the Crossroads Bank for Enterprises which uniquely identifies an establishment unit.")
    nace_code_id = fields.Many2one(
        'l10n.be.nace.code', string="NACE Code",
        compute='_compute_nace', store=True, readonly=False, precompute=True,
    )
    date_start = fields.Date(string="Validity Period From")
    date_end = fields.Date(string="Validity Period To")
    competence = fields.Selection([
        ('fl', "FL (Flanders)"),
        ('br', "BR (Brussels)"),
        ('wa', "WA (Wallonia)"),
        ('cg', "CG (German Community)"),
    ], string="Competence")
    payslip_language_domain = fields.Char(compute='_compute_payslip_language_domain')
    payslip_language_id = fields.Many2one(
        'res.lang',
        string="Payslip Language",
        help="Language in which payslips should be generated for this work location.",
    )
    address_display_name = fields.Char(related='address_id.contact_address_complete', store=True, readonly=True)
    location_type = fields.Selection(selection_add=[('dmfa_unit', 'DMFA Unit')], ondelete={"dmfa_unit": "cascade"})
    total_employee = fields.Integer(compute='_compute_total_employee')
    version_ids = fields.One2many('hr.version', 'work_location_id', string="Versions")
    employee_ids = fields.Many2one(related="version_ids.employee_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for unit in self:
            if unit.date_start and unit.date_end and unit.date_start > unit.date_end:
                raise ValidationError(self.env._("Start date should precede the end date."))

    @api.constrains('bce_code')
    def _check_bce_code(self):
        for location in self:
            if location.bce_code:
                if not location.bce_code.isdigit() or not re.match(r'^[2-8]\d{9}$', location.bce_code):
                    raise ValidationError(self.env._("The DMFA establishment unit code must be 10 digits long. The first digit must be between 2 and 8."))

    @api.model
    def action_list_view(self):
        if self.env.company.country_id.code != "BE":
            raise UserError(self.env._('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return self.env["ir.actions.act_window"]._for_xml_id("l10n_be_hr_payroll.l10n_be_dmfa_work_locations_action")

    @api.depends('competence')
    def _compute_payslip_language_domain(self):
        for location in self:
            if location.competence == 'fl':
                location.payslip_language_domain = "[('code', '=', 'nl_BE')]"
            elif location.competence == 'br':
                location.payslip_language_domain = "[('code', 'in', ['fr_BE', 'nl_BE'])]"
            elif location.competence == 'wa':
                location.payslip_language_domain = "[('code', '=', 'fr_BE')]"
            elif location.competence == 'cg':
                location.payslip_language_domain = "[('code', '=', 'de_DE')]"
            else:
                location.payslip_language_domain = "[('code', 'in', ['fr_BE', 'nl_BE', 'de_DE'])]"

    @api.onchange('competence')
    def _onchange_competence_set_payslip_language(self):
        for location in self:
            if location.competence == 'fl':
                location.payslip_language_id = self.env.ref('base.lang_nl_BE', raise_if_not_found=False)
            elif location.competence == 'wa':
                location.payslip_language_id = self.env.ref('base.lang_fr_BE', raise_if_not_found=False)
            elif location.competence == 'cg':
                location.payslip_language_id = self.env.ref('base.lang_de', raise_if_not_found=False)
            else:
                location.payslip_language_id = False

    @api.onchange('address_id')
    def _onchange_l10n_be_working_address_competence(self):
        for location in self:
            city = location.address_id.city_id or self.env['res.city'].search([('name', '=', location.address_id.city), ('zipcode', '=', location.address_id.zip)])
            match city.l10n_be_language:
                case 'N':
                    location.competence = 'fl'
                case 'F':
                    location.competence = 'wa'
                case 'NF':
                    location.competence = 'br'
                case 'D':
                    location.competence = 'cg'

    def _get_belgian_payslip_languages(self):
        lang_fr = self.env.ref('base.lang_fr_BE', raise_if_not_found=False)
        lang_nl = self.env.ref('base.lang_nl_BE', raise_if_not_found=False)
        lang_de = self.env.ref('base.lang_de', raise_if_not_found=False)
        return lang_fr, lang_nl, lang_de

    def _get_hr_versions_to_recompute(self):
        partner_ids = self.address_id.ids
        if not partner_ids:
            return self.env['hr.version']

        return self.env['hr.version'].search([('address_id', 'in', partner_ids)]).filtered(lambda v: v.country_code == 'BE')

    @api.depends('company_id')
    def _compute_nace(self):
        for unit in self:
            unit.nace_code_id = unit.company_id.current_payroll_config_id.l10n_be_nace_code_id

    def _get_code(self):
        self.ensure_one()
        return self.bce_code

    @api.depends('address_id')
    def _compute_name(self):
        for unit in self:
            unit.name = unit.name or unit.address_id.name or ''

    def _compute_total_employee(self):
        for unit in self:
            unit.total_employee = self.env['hr.employee'].search_count([('work_location_id', 'in', unit.ids)])

    @api.model_create_multi
    def create(self, vals_list):
        locations = super().create(vals_list)
        locations._activate_language()
        for location in locations:
            versions = location._get_hr_versions_to_recompute()
            versions.l10n_be_location_unit = location

        return locations

    def write(self, vals):
        versions_before = self._get_hr_versions_to_recompute()
        res = super().write(vals)
        self._activate_language()
        if 'address_id' in vals:
            versions_before.l10n_be_location_unit = False
            for record in self:
                versions_after = record._get_hr_versions_to_recompute()
                versions_after.l10n_be_location_unit = record

        return res

    def action_view_employees_from_establishment_unit(self):
        self.ensure_one()
        search_view_id = self.env.ref('hr.view_employee_filter').id
        return {
            'name': 'Employees',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,kanban,form',
            'search_view_id': [search_view_id, 'search'],
            'domain': [("work_location_id", "in", [self.id])],
        }

    def _activate_language(self):
        for language in self.payslip_language_id:
            if not language.active:
                self.env['base.language.install'].create({'lang_ids': [(6, 0, language.ids)]}).lang_install()

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                hr_work_location_dmfa_unit_company_address_uniq
            ON hr_work_location (company_id, address_id)
            WHERE location_type = 'dmfa_unit'
        """)
        return res
