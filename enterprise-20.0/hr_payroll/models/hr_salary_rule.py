# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from collections import defaultdict

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from ast import literal_eval

_logger = logging.getLogger(__name__)


class HrSalaryRule(models.Model):
    _name = 'hr.salary.rule'
    _order = 'sequence, id'
    _description = 'Salary Rule'
    _explanation = "Defines how specific components of a salary (e.g., basic wage, allowances, taxes, deductions) are computed and applied to a payslip based on conditions and Python expressions."

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True,
        help="The code of salary rules can be used as reference in computation of other rules. "
             "In that case, it is case sensitive.")
    struct_ids = fields.Many2many(
        'hr.payroll.structure',
        string="Pay Structures",
        required=True,
        index=True,
        ondelete='cascade',
        domain="[('country_id', '=', country_id)]",
        help='The pay structures where the salary rule is applicable'
    )
    country_id = fields.Many2one('res.country',
        domain=lambda self: [('id', 'in', self.env.companies.country_id.ids)],
        default=lambda self: self.env.company.country_id,
        index=True,
    )
    country_code = fields.Char(related='country_id.code')
    sequence = fields.Integer(required=True, index=True, default=5,
        help='Enter a number to define where the rule will be placed')
    quantity = fields.Char(default='1.0',
        help="It is used in computation for percentage and fixed amount. "
             "E.g. a rule for Meal Voucher having fixed amount of "
             u"1€ per worked day can have its quantity defined in expression "
             "like worked_days['002.00'].number_of_days.")
    category_ids = fields.Many2many('hr.salary.rule.category', 'hr_salary_rule_hr_salary_rule_category_rel', string='Categories', domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]")
    active = fields.Boolean(default=True,
        help="If the active field is set to false, it will allow you to hide the salary rule without removing it.")
    appears_on_payslip = fields.Selection([
        ('always', 'Always'),
        ('never', 'Never'),
        ('non_zero', 'If Result is not zero')
    ], string='Visibility', default='always',
        help="Used to display the salary rule on payslip.")
    appears_on_employee_cost_dashboard = fields.Boolean(string='Contributes to Employer Cost', default=False,
        help="Used to compute the employer cost of a payslip.")
    condition_select = fields.Selection([
        ('none', 'Always Present'),
        ('property_input', 'Input Value'),
        ('domain', 'Domain'),
        ('python', 'Python Expression'),
    ], string="Based on", default='none', required=True)
    condition_python = fields.Text(string='Python Condition', required=True,
        default='''
result = result_rules['NET']['total'] > categories['NET'] * 0.10''',
        help='Applied this rule for calculation if condition is true. You can specify condition like basic > 1000.')
    condition_domain = fields.Char(string='Applicability Domain', help="Define the applicability rules for this rule.")
    amount_select = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('property_input', 'Input Value'),
            ('fix', 'Fixed Amount'),
            ('code', 'Python Code'),
        ],
        string='Amount Type',
        compute='_compute_amount_select',
        store=True,
        readonly=False,
        index=True,
        required=True,
        precompute=True,
        help="The computation method for the rule amount.")
    amount_fix = fields.Float(string='Fixed Amount', digits='Payroll')
    amount_percentage = fields.Float(string='Percentage (%)', digits='Payroll Rate',
        help='For example, enter 50.0 to apply a percentage of 50%')

    amount_python_compute = fields.Text(string='Python Code',
        default='''
result = version.wage
result_rate = 10''')
    amount_percentage_base = fields.Char(string='Percentage based on', help='result will be affected to a variable')
    partner_id = fields.Many2one('res.partner', string='Partner',
        help="Eventual third party involved in the salary payment of the employees.")
    note = fields.Html(string='Description', help="If set, the field will be displayed instead of the Rule Name. This can be also used to provide an additional description if needed.", translate=True)
    color = fields.Char('Color', default='#000000')
    title = fields.Boolean(string="Title only", help="When selected, this salary rule will only be displayed as a title with its description, without numeric values.")
    bold = fields.Boolean(string="Bold")
    underline = fields.Boolean(string="Underline")
    italic = fields.Boolean(string="Italic")
    indented = fields.Boolean(string="Indented")
    space_above = fields.Boolean(string="Space Above")

    input_name = fields.Char(compute='_compute_input_name', store=True, readonly=False)
    input_usage_employee = fields.Boolean()
    input_usage_payslip = fields.Boolean(
        string="Available on Payslip",
        help="Let this rule be used as a payslip input, either entered manually on the "
             "payslip, or fed by a salary adjustment of the employee. The entered value "
             "is available to every rule computation of the structure as inputs['<code>'].")
    input_default_value = fields.Float("Default Value")
    input_selected_by_default = fields.Boolean("Selected by Default",
        help="Automatically add an input line for this rule on new payslips, "
             "prefilled with the default value.")
    input_section = fields.Many2one('hr.salary.rule.section', string="Section", default=lambda self: self.env.ref('hr_payroll.default_salary_rule_section', raise_if_not_found=False), domain="['|', ('struct_ids', 'in', struct_ids), ('struct_ids', '=', False)]")
    input_suffix = fields.Char(translate=True)
    input_used_in_definition = fields.Boolean(compute='_compute_input_used_in_definition', search='_search_input_used_in_definition')
    display_in_pdf_extra_info = fields.Boolean(string='Show in extra info section', help='The amount of the rule will appear in an "Additional Information" section of the payslip.')
    explanation_template = fields.Text(string="Explanation Template", help="Use Python f-string logic or expressions. E.g., Basic Wage ({wage}) * Days ({number_of_days})", translate=True)
    hide_amount = fields.Boolean(string='Hide Amount', help='Hide the base amount of this salary rule in the payslip.')
    user_instructions = fields.Html(string='User Instructions', help='Instructions for the user to fill in the input value of this salary rule on the payslip.', translate=True)

    modified_by_user = fields.Boolean(readonly=True, copy=False)
    created_by_user = fields.Boolean(readonly=True, default=lambda self: self.env.uid != SUPERUSER_ID, copy=False)
    round_of_computation = fields.Integer(default=0, string='Round at which the rule is computed', help='Some rules results can depend on the result of rules of other payslips. (i.e. Withholding tax exemption). Set this value to make sure that required values are computed before this one. Note that the lowest values have the highest priority.')

    @api.constrains('code', 'struct_ids')
    def _check_unique_code_per_struct(self):
        duplicates = self.search([
            ('code', 'in', self.mapped('code')),
            ('struct_ids', 'in', self.struct_ids.ids),
        ])
        for rule in self:
            if any(d.id != rule.id and d.code == rule.code and d.struct_ids & rule.struct_ids for d in duplicates):
                raise ValidationError(
                    self.env._("Salary rule code should be unique by structure!")
                )

    @api.constrains('condition_select', 'amount_select', 'input_usage_employee', 'input_usage_payslip')
    def _check_property_input_usage(self):
        # A 'Salary Input' rule only fires when an input line carries its code; without
        # any availability, no input can ever be entered and the rule is dead.
        for rule in self:
            if (
                (rule.condition_select == 'property_input' or rule.amount_select == 'property_input')
                and not rule.input_usage_employee
                and not rule.input_usage_payslip
            ):
                raise ValidationError(
                    self.env._(
                        "A Salary Input rule must be available on the employee or on the "
                        "payslip, otherwise it can never receive a value (rule %(code)s).",
                        code=rule.code,
                    )
                )

    @api.depends('name')
    def _compute_input_name(self):
        for rule in self:
            rule.input_name = rule.name

    @api.depends('condition_select')
    def _compute_amount_select(self):
        for rule in self:
            if rule.condition_select == 'property_input':
                rule.amount_select = 'property_input'
            else:
                rule.amount_select = rule.amount_select or 'fix'

    def _compute_input_used_in_definition(self):
        all_structures = self.struct_ids
        definitions_inputs_by_structure = defaultdict(set)

        for struct in all_structures:
            definitions_inputs_by_structure[struct] = {
                prop['name'] for prop in struct.version_properties_definition if not prop['name'].startswith('separator_')
            }

        for rule in self:
            rule.input_used_in_definition = any(rule.code in definitions_inputs_by_structure[struct] for struct in rule.struct_ids)

    def _search_input_used_in_definition(self, operator, value):
        # operator should be '=' or '!='
        # value is True/False
        if operator not in ('=', '!='):
            raise UserError(self.env._("Unsupported operator %s") % operator)

        # collect all struct->input_names mapping
        all_structures = self.env['hr.payroll.structure'].search([])
        definitions_inputs_by_structure = defaultdict(set)
        for struct in all_structures:
            definitions_inputs_by_structure[struct.id] = {
                prop['name'] for prop in struct.version_properties_definition if not prop['name'].startswith('separator_')
            }

        # find rule ids that match the condition
        matching_rules = []
        rules = self.env['hr.salary.rule'].search([])
        for rule in rules:
            if any(rule.code in definitions_inputs_by_structure.get(struct.id, set()) for struct in rule.struct_ids):
                matching_rules.append(rule.code)

        domain = [('code', 'in', matching_rules)]
        if (operator == '=' and not value) or (operator == '!=' and value):
            domain = [('code', 'not in', matching_rules)]

        return domain

    def _get_property_default_value(self):
        self.ensure_one()
        return self.input_default_value or 0.0

    def _raise_error(self, localdict, error_type, e):
        raise UserError(_("""%(error_type)s
- Employee: %(employee)s
- Version: %(version)s
- Payslip: %(payslip)s
- Salary rule: %(name)s (%(code)s)
- Error: %(error_message)s""",
            error_type=error_type,
            employee=localdict['employee'].name,
            version=localdict['version'].name,
            payslip=localdict['payslip'].name,
            name=self.name,
            code=self.code,
            error_message=e))

    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the current computation environment
        :return: returns a tuple (amount, qty, rate)
        :rtype: (float, float, float)
        """
        self.ensure_one()
        localdict['localdict'] = localdict

        if self.amount_select == 'property_input':
            input_line = localdict['inputs'].get(self.code)
            if not input_line:
                return 0.0, 1.0, 100.0, {}
            return input_line.amount, 1.0, 100.0, localdict.get('explanation_info', {})

        if self.amount_select == 'fix':
            try:
                return self.amount_fix or 0.0, float(safe_eval(self.quantity, localdict)), 100.0, localdict.get('explanation_info', {})
            except Exception as e:
                self._raise_error(localdict, _("Wrong quantity defined for:"), e)
        if self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage or 0.0, localdict.get('explanation_info', {}))
            except Exception as e:
                self._raise_error(localdict, _("Wrong percentage base or quantity defined for:"), e)
        # python code
        try:
            safe_eval(self.amount_python_compute or 0.0, localdict, mode='exec')
            return float(localdict['result']), localdict.get('result_qty', 1.0), localdict.get('result_rate', 100.0), localdict.get('explanation_info', {})
        except Exception as e:
            self._raise_error(localdict, _("Wrong python code defined for:"), e)

    def _satisfy_condition(self, localdict):
        self.ensure_one()
        localdict['localdict'] = localdict
        if self.condition_select == 'none':
            return True
        if self.condition_select == 'domain':
            return localdict['payslip'].filtered_domain(literal_eval(self.condition_domain or '[]'))
        if self.condition_select == 'property_input':
            input_line = localdict['inputs'].get(self.code)
            return bool(input_line and input_line.amount)
        # python code
        try:
            safe_eval(self.condition_python, localdict, mode='exec')
            return localdict.get('result', False)
        except Exception as e:
            self._raise_error(localdict, _("Wrong python condition defined for:"), e)

    def _get_report_field_name(self):
        self.ensure_one()
        return 'x_l10n_%s_%s' % (
            self.country_id.code.lower() if self.country_id.code else 'xx',
            self.code.lower().replace('.', '_').replace('-', '_').replace(' ', '_'),
        )

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        if default and 'name' in default:
            return vals_list
        return [
            dict(
                vals,
                code=f"{rule.code}_COPY",
            )
            for rule, vals in zip(self, vals_list)
        ]

    @api.constrains('category_ids', 'country_id')
    def _check_category_country(self):
        for rule in self:
            if rule.country_id and any(cat.country_id and cat.country_id != rule.country_id for cat in rule.category_ids):
                raise ValidationError(_("All selected categories must belong to the same country as the rule structure."))

    @api.ondelete(at_uninstall=False)
    def unlink_salary_rule(self):
        if self.env.uid != SUPERUSER_ID and SUPERUSER_ID in self.create_uid.mapped('id'):
            raise UserError(self.env._('You cannot delete a salary rule created by the system.\nArchive it instead.'))
        self._sync_properties_definition()
        return

    def _set_all_external_identifiers_noupdate(self, noupdate):
        self.env['ir.model.data'].sudo().search([
            ('model', '=', "hr.salary.rule"), ('res_id', 'in', self.ids)
        ]).write({'noupdate': noupdate})
        self.env.flush_all()

    @api.model
    def _get_critical_fields(self):
        return [
            'code', 'category_ids', 'struct_ids', 'country_id', 'sequence',
            'condition_select', 'condition_python', 'condition_domain', 'amount_select', 'amount_fix',
            'amount_percentage', 'amount_percentage_base', 'amount_python_compute', 'quantity',
        ]

    @api.model
    def _get_reset_required_explicit_fields(self, vals):
        """Fields which should always be explicitly set in module data.

        When payroll static data is reloaded (e.g. via reset/update), only the
        fields explicitly present in XML are written back. If a field is omitted
        from the data file and later changed in the database, the reload won't
        restore the original value.

        :param dict vals: values coming from module data loading
        :return: set of field names expected to be explicit in the XML
        :rtype: set
        """
        base_required_fields = {'condition_select', 'amount_select', 'category_ids', 'country_id'}
        condition_required_fields = {
            'python': {'condition_python'},
            'domain': {'condition_domain'},
        }
        property_input_required_fields = {
            'input_usage_employee',
            'input_usage_payslip',
        }
        amount_required_fields = {
            'fix': {'amount_fix', 'quantity'},
            'percentage': {'amount_percentage', 'amount_percentage_base', 'quantity'},
            'code': {'amount_python_compute'},
        }

        required = set(base_required_fields)
        condition_select = vals.get('condition_select')
        required.update(condition_required_fields.get(condition_select, ()))

        if condition_select == 'property_input':
            # `amount_select` is forced to `property_input` (stored compute)
            # so it does not need to be explicit in module data for resets.
            required.discard('amount_select')
            required.update(property_input_required_fields)

        amount_select = vals.get('amount_select')
        required.update(amount_required_fields.get(amount_select, ()))

        return required

    def _validate_category_ids_field(self, vals):
        category_ids = vals.get('category_ids')
        if len(category_ids) != 1 or len(category_ids[0]) != 3:
            return False
        command, x, y = command_tuple = category_ids[0]
        return (command_tuple == (5, 0, 0)) or (command == 6 and x == 0 and len(y))

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._sync_properties_definition()

        install_filename = self.env.context.get("install_filename")
        install_module = self.env.context.get("install_module")
        if not (
            self.env.context.get("install_mode") and install_filename and install_module
        ):
            return rules

        for vals, rule in zip(vals_list, rules):
            required_fields = self._get_reset_required_explicit_fields(vals)
            missing_fields = sorted(required_fields.difference(vals))
            if not missing_fields:
                if not self._validate_category_ids_field(vals):
                    _logger.warning(
                        "Salary rule created from module data with potentially wrong category_ids. "
                        "Be sure to use the [(5, 0, 0)] CLEAR or [(6, 0, ids)] SET command to properly configure the categories. "
                        "Rule: %(rule)s, code=%(code)s, module=%(module)s, file=%(file)s",
                        {
                            'rule': rule.display_name,
                            'code': rule.code,
                            'module': install_module,
                            'file': install_filename,
                        },
                    )
                continue
            _logger.warning(
                "Salary rule created from module data without explicit %(missing)s; "
                "this may prevent payroll data reset from restoring the original values. "
                "Rule: %(rule)s, code=%(code)s, module=%(module)s, file=%(file)s",
                {
                    'missing': ", ".join(missing_fields),
                    'rule': rule.display_name,
                    'code': rule.code,
                    'module': install_module,
                    'file': install_filename,
                },
            )
        return rules

    def write(self, vals):
        rules_created_by_system = self.filtered(
            lambda r: r.create_uid.id == SUPERUSER_ID
        )
        if (
            self.env.uid != SUPERUSER_ID
            and rules_created_by_system
            and any(f in vals for f in self._get_critical_fields())
        ):
            rules_created_by_system._set_all_external_identifiers_noupdate(True)
            vals["modified_by_user"] = True
        result = super().write(vals)
        self._sync_properties_definition()
        return result

    def _sync_properties_definition(self):
        self.struct_ids._sync_properties_to_definition()

    @api.constrains('code', 'condition_select')
    def _validate_code(self):
        for rule in self:
            if rule.condition_select == 'property_input' and not re.match(r'^[a-zA-Z0-9_]+$', rule.code):
                raise ValidationError(self.env._("Invalid Code: %s\nThe code must contain only letters, numbers, and underscores (e.g., 'BASIC_SALARY' or 'rule_01').", rule.code))

    def action_reset_rule(self):
        self.ensure_one()
        self._set_all_external_identifiers_noupdate(False)
        self.env['hr.payslip'].with_user(SUPERUSER_ID)._update_payroll_data(self.country_id.code)
        self.with_user(SUPERUSER_ID).write({
            'modified_by_user': False,
            'active': True,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': self.env._("Salary Rule successfully reset!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.depends('code', 'name')
    def _compute_display_name(self):
        if self.env.context.get('is_payslip_line_report', False):
            for rule in self:
                rule.display_name = f"{rule.name} [{rule.code}]" if rule.code else rule.name
        else:
            super()._compute_display_name()
