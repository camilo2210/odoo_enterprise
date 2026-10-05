from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_list


class EsgAssignationLine(models.Model):
    _name = 'esg.assignation.line'
    _description = 'Assignation Line'

    esg_emission_factor_id = fields.Many2one('esg.emission.factor', string='Emission Factor', index=True, required=True, ondelete='cascade')
    account_id = fields.Many2one(
        'account.account',
        groups='account.group_account_invoice',
        domain=lambda self: [('account_type', 'in', self.env['account.account'].ESG_VALID_ACCOUNT_TYPES)],
    )
    partner_id = fields.Many2one('res.partner')
    product_id = fields.Many2one('product.product')
    product_category_id = fields.Many2one('product.category')

    _at_least_one_field_filled = models.Constraint(
        "CHECK(product_id IS NOT NULL OR partner_id IS NOT NULL OR account_id IS NOT NULL OR product_category_id IS NOT NULL)",
        "The assignation rule must have at least one field filled",
    )

    @api.depends('account_id', 'partner_id', 'product_id', 'product_category_id')
    def _compute_display_name(self):
        for line in self:
            if not line.id:
                line.display_name = False
                continue
            parts = []
            if line.account_id:
                parts.append(self.env._('Account: %s', line.account_id.name))
            if line.partner_id:
                parts.append(self.env._('Partner: %s', line.partner_id.name))
            if line.product_id:
                parts.append(self.env._('Product: %s', line.product_id.name))
            if line.product_category_id:
                parts.append(self.env._('Category: %s', line.product_category_id.display_name))
            line.display_name = ', '.join(parts)

    @api.constrains('account_id', 'partner_id', 'product_id', 'product_category_id')
    def _check_unique_assignation_line_from_all_factors(self):
        if any(account_type not in self.env['account.account'].ESG_VALID_ACCOUNT_TYPES for account_type in self.account_id.mapped('account_type')):
            raise ValidationError(self.env._(
                'The account type must be of type %(valid_account_type_names)s.',
                valid_account_type_names=format_list(self.env, self.env['account.account'].ESG_VALID_ACCOUNT_TYPE_NAMES, 'or'),
            ))
        data = self.env['esg.assignation.line']._read_group(
            domain=[
                '|', '|', '|',
                ('product_id', 'in', self.product_id.ids),
                ('product_category_id', 'in', self.product_category_id.ids),
                ('partner_id', 'in', self.partner_id.ids),
                ('account_id', 'in', self.account_id.ids),
            ],
            groupby=['product_id', 'product_category_id', 'partner_id', 'account_id'],
            aggregates=['esg_emission_factor_id:recordset', 'esg_emission_factor_id:count'],
        )
        factors_per_rule = {(product, product_category, partner, account): (emission_factors, count) for product, product_category, partner, account, emission_factors, count in data}

        for assignation_line in self:
            rule = (assignation_line.product_id, assignation_line.product_category_id, assignation_line.partner_id, assignation_line.account_id)
            emission_factors, count = factors_per_rule.get(rule, (self.env['esg.emission.factor'], 0))
            if len(emission_factors) > 1:
                emission_factor = emission_factors - assignation_line.esg_emission_factor_id
            else:
                emission_factor = emission_factors
            if count > 1 or (emission_factor and emission_factor != assignation_line.esg_emission_factor_id):
                raise ValidationError(self.env._(
                    "An assignation with the rules (%(account_name)s, %(partner_name)s, %(product_name)s, %(product_category_name)s) already exists in the emission factor '%(factor_name)s'.",
                    account_name=assignation_line.account_id.name or self.env._('Any Account'),
                    partner_name=assignation_line.partner_id.name or self.env._('Any Partner'),
                    product_name=assignation_line.product_id.name or self.env._('Any Product'),
                    product_category_name=assignation_line.product_category_id.complete_name or self.env._('Any Product Category'),
                    factor_name=emission_factor.name,
                ))
