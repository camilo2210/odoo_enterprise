# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayrollStructure(models.Model):
    _name = 'hr.payroll.structure'
    _description = 'Salary Structure'
    _order = 'sequence'

    @api.model
    def _get_default_report_id(self):
        return self.env.ref('hr_payroll.action_report_payslip', False)

    @api.model
    def _get_default_rule_ids(self):
        default_structure = self.env.ref('hr_payroll.default_structure', False)
        if not default_structure or not (default_rules := default_structure.with_context(active_test=False).rule_ids):
            return []
        vals_list = [rule.copy_data(default={'name': rule.name, 'active': True, 'country_id': self.env.company.country_id})[0] for rule in default_rules]
        return [(0, 0, vals) for vals in vals_list]

    def _get_domain_report(self):
        if self.env.company.country_code:
            return [
                ('model', '=', 'hr.payslip'),
                ('report_type', '=', 'qweb-pdf'),
                '|',
                ('report_name', 'ilike', 'l10n_' + self.env.company.country_code.lower()),
                '&',
                ('report_name', 'ilike', 'hr_payroll'),
                ('report_name', 'not ilike', 'l10n')
            ]
        else:
            return [
                ('model', '=', 'hr.payslip'),
                ('report_type', '=', 'qweb-pdf'),
                ('report_name', 'ilike', 'hr_payroll'),
                ('report_name', 'not ilike', 'l10n')
            ]

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    code = fields.Char()
    active = fields.Boolean(default=True)
    type_id = fields.Many2one(
        'hr.payroll.structure.type', required=True, index=True)
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id,
        domain=lambda self: [('id', 'in', self.env.companies.country_id.ids)]
    )
    country_code = fields.Char(related='country_id.code', depends=['country_id'])
    note = fields.Html(string='Description')
    rule_ids = fields.Many2many(
        'hr.salary.rule', relation='hr_payroll_structure_hr_salary_rule_rel',
        string='Salary Rules', default=_get_default_rule_ids)
    report_id = fields.Many2one('ir.actions.report',
        string="Template", domain=_get_domain_report, default=_get_default_report_id)
    payslip_name = fields.Char(string="Payslip Name", translate=True,
        help="Name to be set on a payslip. Example: 'End of the year bonus'. If not set, the default value is 'Salary Slip'")
    hide_basic_on_pdf = fields.Boolean(help="Enable this option if you don't want to display the Basic Salary on the printed pdf.")
    use_worked_day_lines = fields.Boolean(default=True, help="Worked days won't be computed/displayed in payslips.")
    schedule_pay = fields.Selection(related='type_id.default_schedule_pay')
    ytd_computation = fields.Boolean(default=False, string='Year to Date Computation',
        help="Adds a column in the payslip that shows the accumulated amount paid for different rules during the year")

    version_properties_definition = fields.PropertiesDefinition("Version Properties Definition")
    employee_type_ids = fields.Many2many(
        "hr.employee.type",
        string="Employee Types",
        domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]",
    )

    def _sync_properties_to_definition(self):
        """
        Sync the version-side properties definition based on all active rules of the
        structure that are marked input_usage_employee, whatever their condition type.

        Payslip-side properties are no longer used: per-payslip values now live as
        hr.payslip.input rows pointing at the rule via salary_rule_id.
        """
        for struct in self:
            employee_input_rules = struct.rule_ids.filtered(
                lambda r: r.active and r.input_usage_employee
            )

            def _build_definition(rules_for_definition):
                def _sort_definition(definition):
                    groups = []
                    current_group = None
                    for prop in definition:
                        if prop.get("type") == "separator":
                            if current_group:
                                groups.append(current_group)
                            current_group = [prop, []]
                        elif current_group:
                            current_group[1].append(prop)
                    if current_group:
                        groups.append(current_group)
                    cat_ids = []
                    for g in groups:
                        sep = g[0]
                        if sep["name"].startswith("separator_"):
                            cat_id = int(sep["name"][10:])
                            cat_ids.append(cat_id)
                    categories = self.env["hr.salary.rule.section"].browse(cat_ids)
                    seq_map = {c.id: c.sequence for c in categories}
                    groups.sort(
                        key=lambda g: seq_map.get(int(g[0]["name"][10:]), float("inf"))
                    )
                    new_def = []
                    for sep, props in groups:
                        new_def.append(sep)
                        new_def.extend(props)
                    return new_def

                definition = []
                for rule in rules_for_definition:
                    category = rule.input_section
                    if not category:
                        continue

                    separator_name = f"separator_{category.id}"
                    property_name = rule.code

                    input_name = rule.input_name or rule.name
                    suffix = rule.input_suffix or ""
                    default = rule._get_property_default_value()

                    new_property = {
                        "name": property_name,
                        "type": "float",
                        "string": input_name,
                        "default": default,
                    }

                    if suffix:
                        new_property["suffix"] = suffix

                    sep_index = None
                    for i, prop in enumerate(definition):
                        if (
                            prop.get("type") == "separator"
                            and prop.get("name") == separator_name
                        ):
                            sep_index = i
                            break

                    if sep_index is not None:
                        next_sep_index = len(definition)
                        for j in range(sep_index + 1, len(definition)):
                            if definition[j].get("type") == "separator":
                                next_sep_index = j
                                break
                        definition.insert(next_sep_index, new_property)
                    else:
                        new_separator = {
                            "name": separator_name,
                            "type": "separator",
                            "string": category.name,
                            "fold_by_default": False,
                        }
                        definition.append(new_separator)
                        definition.append(new_property)

                return _sort_definition(definition)

            version_properties_definition = _build_definition(employee_input_rules)

            struct.write({"version_properties_definition": version_properties_definition})
