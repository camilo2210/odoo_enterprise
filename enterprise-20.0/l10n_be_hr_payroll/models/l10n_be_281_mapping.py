from datetime import date

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10n_Be281_Mapping(models.Model):
    _name = "l10n.be.281.mapping"
    _description = "HR Payroll 281.XX Declaration Mapping"

    date_from = fields.Date(string="From Date", required=True)
    date_to = fields.Date(string="To Date")
    tag = fields.Char(string="Tag", required=True)
    evaluation_type = fields.Selection(
        [
            ("salary_rule", "Salary Rule"),
            ("python", "Python"),
            ("control", "Control"),
        ],
        string="Evaluation Type",
        required=True,
    )
    salary_rule_ids = fields.Many2many(
        'hr.salary.rule', 'l10n_be_281_mapping_salary_rule_rel',
        string="Salary Rules", domain=[('country_code', '=', 'BE')], ondelete='restrict')
    control_mapping_ids = fields.Many2many(
        'l10n.be.281.mapping', 'l10n_be_281_mapping_control_rel',
        'mapping_id', 'control_mapping_id', string="Control Rows", ondelete='restrict')
    controlled_by_mapping_ids = fields.Many2many(
        'l10n.be.281.mapping', 'l10n_be_281_mapping_control_rel',
        'control_mapping_id', 'mapping_id', string="Controlled By")
    evaluation_value = fields.Text(string="Evaluation Value")
    is_monetary = fields.Boolean(string="Monetary")
    skip_if_falsy = fields.Boolean(string="Skip If Falsy")
    declaration_code = fields.Selection(
        [
            ("281.45", "281.45"),
            ("273S", "273S"),
        ],
        string="Declaration Code",
        required=True,
    )

    _date_range = models.Constraint(
        "CHECK(date_to IS NULL OR date_to >= date_from)",
        "The mapping end date must be on or after its start date.",
    )

    @api.onchange('evaluation_type')
    def _onchange_evaluation_type(self):
        for mapping in self:
            if mapping.evaluation_type != 'python':
                mapping.evaluation_value = False
                mapping.is_monetary = False
            if mapping.evaluation_type != 'salary_rule':
                mapping.salary_rule_ids = [Command.clear()]
            if mapping.evaluation_type != 'control':
                mapping.control_mapping_ids = [Command.clear()]

    @api.constrains('evaluation_type', 'salary_rule_ids', 'control_mapping_ids', 'controlled_by_mapping_ids', 'evaluation_value')
    def _check_evaluation_type_consistency(self):
        for mapping in self:
            evaluation_type = mapping.evaluation_type
            if evaluation_type == 'salary_rule':
                if not mapping.salary_rule_ids:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s must have at least one salary rule.", tag=mapping.tag,
                    ))
                if mapping.control_mapping_ids or mapping.evaluation_value:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s is a Salary Rule row and can't have control links or a python expression.",
                        tag=mapping.tag,
                    ))
            elif evaluation_type == 'control':
                if not mapping.control_mapping_ids:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s must have at least one control target.", tag=mapping.tag,
                    ))
                if mapping.salary_rule_ids or mapping.evaluation_value:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s is a Control row and can't have salary rules or a python expression.",
                        tag=mapping.tag,
                    ))
                if any(target.evaluation_type == 'control' for target in mapping.control_mapping_ids):
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s is a Control row and can't reference another Control row.",
                        tag=mapping.tag,
                    ))
                if mapping.controlled_by_mapping_ids:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s is a Control row and can't itself be a control target.",
                        tag=mapping.tag,
                    ))
            elif evaluation_type == 'python':
                if not mapping.evaluation_value:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s must have a python expression.", tag=mapping.tag,
                    ))
                if mapping.control_mapping_ids or mapping.salary_rule_ids:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s is a Python row and can't have control links or salary rules.", tag=mapping.tag,
                    ))

    @api.constrains('salary_rule_ids')
    def _check_salary_rule_country(self):
        for mapping in self:
            if any(rule.country_code != 'BE' for rule in mapping.salary_rule_ids):
                raise ValidationError(self.env._(
                    "Mapping row %(tag)s can only link to Belgian salary rules.", tag=mapping.tag,
                ))

    @api.constrains('control_mapping_ids', 'controlled_by_mapping_ids', 'declaration_code')
    def _check_control_declaration_code(self):
        # Checked both ways, so it also catches a target's own declaration_code changing later.
        for mapping in self:
            for target in mapping.control_mapping_ids:
                if target.declaration_code != mapping.declaration_code:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s can only control rows from the same declaration.",
                        tag=mapping.tag,
                    ))
            for controller in mapping.controlled_by_mapping_ids:
                if controller.declaration_code != mapping.declaration_code:
                    raise ValidationError(self.env._(
                        "Mapping row %(tag)s can only be controlled by rows from the same declaration.",
                        tag=mapping.tag,
                    ))

    @api.constrains('declaration_code', 'evaluation_type')
    def _check_273s_evaluation_type(self):
        # 273S sums raw codes directly; it never calls _evaluate on the mapping row.
        # python/control would be silently ignored or read as an empty code list.
        for mapping in self:
            if mapping.declaration_code == '273S' and mapping.evaluation_type != 'salary_rule':
                raise ValidationError(self.env._(
                    "273S mapping row %(tag)s must use the Salary Rule evaluation type.", tag=mapping.tag,
                ))

    @api.constrains('date_from', 'date_to')
    def _check_calendar_year_dates(self):
        for mapping in self:
            if mapping.date_from and (mapping.date_from.month, mapping.date_from.day) != (1, 1):
                raise ValidationError(self.env._("A mapping must start on January 1."))
            if mapping.date_to and (mapping.date_to.month, mapping.date_to.day) != (12, 31):
                raise ValidationError(self.env._("A mapping must end on December 31."))

    @api.constrains('declaration_code', 'tag', 'date_from', 'date_to')
    def _check_date_range_overlap(self):
        for mapping in self:
            domain = [
                ('id', '!=', mapping.id),
                ('declaration_code', '=', mapping.declaration_code),
                ('tag', '=', mapping.tag),
                '|', ('date_to', '=', False), ('date_to', '>=', mapping.date_from),
            ]
            if mapping.date_to:
                domain.append(('date_from', '<=', mapping.date_to))
            if mapping.search_count(domain, limit=1):
                raise ValidationError(self.env._(
                    "The year range for tag %(tag)s overlaps another %(declaration)s mapping.",
                    tag=mapping.tag, declaration=mapping.declaration_code,
                ))

    @api.depends('declaration_code', 'tag', 'date_from', 'date_to')
    def _compute_display_name(self):
        for mapping in self:
            date_range = f"{mapping.date_from} - {mapping.date_to}" if mapping.date_to else f"{mapping.date_from}+"
            mapping.display_name = f"{mapping.declaration_code} {mapping.tag} ({date_range})"

    def _get_codes(self):
        salary_mappings = self.filtered(lambda mapping: mapping.evaluation_type == 'salary_rule')
        # Archived rules still contribute to declarations for past payslips.
        codes = salary_mappings.with_context(active_test=False).salary_rule_ids.mapped('code')
        return list(dict.fromkeys(codes))

    def _tag_domain(self, declaration_code, tag, year):
        return [
            ('declaration_code', '=', declaration_code),
            ('tag', '=', tag),
            ('date_from', '<=', date(int(year), 1, 1)),
            '|', ('date_to', '=', False), ('date_to', '>=', date(int(year), 12, 31)),
        ]

    def _search_for_tag(self, declaration_code, tag, year):
        mappings = self.search(self._tag_domain(declaration_code, tag, year))
        if not mappings:
            raise UserError(self.env._(
                "No l10n.be.281.mapping row found for %(declaration)s tag %(tag)s and year %(year)s.",
                declaration=declaration_code, tag=tag, year=year,
            ))
        if len(mappings) > 1:
            raise UserError(self.env._(
                "Multiple l10n.be.281.mapping rows match %(declaration)s tag %(tag)s for year %(year)s; their year ranges overlap.",
                declaration=declaration_code, tag=tag, year=year,
            ))
        return mappings

    def _get_codes_for_tag(self, declaration_code, tag, year):
        if not self.search_count(self._tag_domain(declaration_code, tag, year)):
            return []
        return self._search_for_tag(declaration_code, tag, year)._get_codes()
