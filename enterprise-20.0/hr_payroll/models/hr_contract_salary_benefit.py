# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrContractSalaryBenefit(models.Model):
    _name = 'hr.contract.salary.benefit'
    _description = 'Salary Package Benefit'
    _order = 'sequence'

    def _get_field_domain(self):
        fields_ids = self.env['hr.version']._get_benefit_fields(triggers=False)
        return [
            ('model', '=', 'hr.version'),
            ('name', 'in', fields_ids),
            ('ttype', 'not in', ('one2many', 'many2one', 'many2many'))]

    def _get_public_field_names(self):
        return [(field.id, field.field_description) for field in self.sudo().env['ir.model.fields'].search(self._get_field_domain())]

    name = fields.Char(translate=True, required=True)
    active = fields.Boolean(default=True)
    source = fields.Selection([
        ('field', 'Field'),
        ('rule', 'Salary Rule')
    ], string="Benefit Source", default='field', required=True)
    res_field_id = fields.Many2one(
        'ir.model.fields',
        string="Employee Record Related Field",
        required=False,
        domain="[('id', 'in', allowed_field)]",
        ondelete='cascade',
        help="Select the contract's field where the value of the benefit will be written",
    )
    allowed_field = fields.Many2many('ir.model.fields', compute="_compute_allowed_field", readonly=True, compute_sudo=True)
    cost_res_field_id = fields.Many2one(
        'ir.model.fields',
        string="Cost Field",
        domain="[('id', 'in', allowed_field)]",
        ondelete='cascade',
        help="Select the contract's field to consider in salary computation",
    )
    # LUL rename into field and cost_field to be consistent with fold_field and manual_field?
    res_field_public = fields.Selection(
        selection="_get_public_field_names",
        string="Benefit Field",
        readonly=False,
        compute="_compute_res_field_public",
        inverse="_inverse_res_field_public",
    )
    cost_res_field_public = fields.Selection(
        selection="_get_public_field_names",
        string="Cost Field (Public)",
        readonly=False,
        compute="_compute_cost_res_field_public",
        inverse="_inverse_cost_res_field_public",
    )
    field = fields.Char(compute="_compute_field", store=True, readonly=True, compute_sudo=True)
    cost_field = fields.Char(related="cost_res_field_id.name", string="Cost Field Name", readonly=True, compute_sudo=True)
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string="Salary Rule",
        domain="[('input_usage_employee', '=', True), ('input_used_in_definition', '=', True), ('struct_ids', 'any', [('type_id', '=', structure_type_id)])]",
        help="Select the salary rule associated with this benefit",
    )
    sequence = fields.Integer(default=100)
    benefit_type_id = fields.Many2one(
        'hr.contract.salary.benefit.type', required=True, string="Benefit Type",
        default=lambda self: self.env.ref('hr_payroll.l10n_be_monthly_benefit', raise_if_not_found=False),
        help="Allow to define the periodicity and output type of the advantage")
    country_id = fields.Many2one(
        'res.country',
        related='structure_type_id.country_id',
        string='Country',
        store=True,
        readonly=True)
    structure_type_id = fields.Many2one('hr.payroll.structure.type', string="Salary Structure Type", required=True, index=True)
    description = fields.Html('Description', translate=True)
    has_admin_access = fields.Boolean(compute='_compute_has_admin_access')

    user_has_access = fields.Boolean(
        compute='_compute_user_has_access',
        search='_search_user_has_access',
        string='User Has Access to Benefits'
    )

    view_ids = fields.Many2many(
        'ir.ui.view',
        string="Related Views",
        context={'active_test': False},
        help="Views that will be automatically archived/unarchived when this benefit is archived/unarchived."
    )

    salary_rule_ids = fields.Many2many(
        'hr.salary.rule',
        string="Related Salary Rules",
        context={'active_test': False},
        domain='[("struct_ids", "any", [("type_id", "=", structure_type_id)])]',
        help="Salary rules that will be automatically archived/unarchived when this benefit is archived/unarchived."
    )

    def _compute_user_has_access(self):
        countries = self.env.companies.country_id
        for record in self:
            record.user_has_access = (
                    not record.structure_type_id or
                    not record.structure_type_id.country_id or
                    record.structure_type_id.country_id in countries
            )

    def _search_user_has_access(self, operator, value):
        countries = self.env.companies.country_id.ids + [False]
        domain = [
            '|',
            ('structure_type_id', '=', False),
            ('structure_type_id.country_id', 'in', countries)
        ]
        return domain

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.view_ids:
                # sudo needed for payroll admins to write on `ir.ui.view`
                record.view_ids.sudo().write({'active': record.active})
            if record.salary_rule_ids:
                record.salary_rule_ids.write({'active': record.active})
        return records

    # Override write to handle the toggle logic
    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals:
            #  sudo needed for payroll admins to write on `ir.ui.view`
            self.view_ids.sudo().write({'active': vals['active']})
            self.salary_rule_ids.write({'active': vals['active']})
        return res

    @api.depends('structure_type_id.country_id')
    def _compute_allowed_field(self):
        all_possible_fields = self.env['ir.model.fields'].search(self._get_field_domain())

        def _filter_by_country(field, country):
            return any("l10n" not in module or country and f"l10n_{country.code.lower()}" in module for module in field.modules.split(","))

        for record in self:
            country = record.structure_type_id.country_id
            record.allowed_field = all_possible_fields.filtered(lambda f: _filter_by_country(f, country))

    @api.depends('res_field_id')
    def _compute_field(self):
        for record in self:
            if record.source == 'field':
                record.field = record.res_field_id.name
            elif record.source == 'rule':
                record.field = record.salary_rule_id.name
            else:
                record.field = False

    @api.depends('res_field_id')
    def _compute_res_field_public(self):
        for record in self:
            record.res_field_public = record.res_field_id.id

    @api.depends('cost_res_field_id')
    def _compute_cost_res_field_public(self):
        for record in self:
            record.cost_res_field_public = record.cost_res_field_id.id

    def _inverse_res_field_public(self):
        Fields = self.sudo().env['ir.model.fields']
        for record in self:
            field_id = record.res_field_public and int(record.res_field_public)
            record.res_field_id = Fields.browse(field_id)

    def _inverse_cost_res_field_public(self):
        Fields = self.sudo().env['ir.model.fields']
        for record in self:
            field_id = record.cost_res_field_public and int(record.cost_res_field_public)
            record.cost_res_field_id = Fields.browse(field_id)

    @api.depends_context('uid')
    def _compute_has_admin_access(self):
        self.has_admin_access = self.env.user._is_system()


class HrContractSalaryBenefitType(models.Model):
    _name = 'hr.contract.salary.benefit.type'
    _description = 'Contract Benefit Type'
    _order = 'sequence'

    name = fields.Char(translate=True)
    periodicity = fields.Selection([
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], default='monthly')
    sequence = fields.Integer(default=100)
