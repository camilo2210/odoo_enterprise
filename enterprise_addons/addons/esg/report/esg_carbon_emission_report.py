from collections import Counter

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools import SQL


class EsgCarbonEmissionReport(models.Model):
    _name = 'esg.carbon.emission.report'
    _description = 'ESG Carbon Emissions Report'
    _auto = False

    date = fields.Date(required=True)
    date_end = fields.Date()
    esg_emission_factor_id = fields.Many2one(
        'esg.emission.factor',
        string='Emission Factor',
        domain="[('compute_method', 'in',  ['monetary', 'physically' if id > 0 or uom_id else 'monetary'])]",
        help='A value that quantifies the amount of greenhouse gas emissions produced per unit of activity.',
    )
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)
    name = fields.Text()
    note = fields.Text()
    quantity = fields.Integer(required=True)
    esg_emissions_value = fields.Float(string='Emissions', readonly=True, digits='Carbon Emissions')
    esg_uncertainty_absolute_value = fields.Float(string='Uncertainty (kgCO₂e)', readonly=True, digits='Carbon Emissions')
    esg_emissions_value_t = fields.Float(string='tCO₂e', readonly=True, digits='Carbon Emissions')
    esg_uncertainty_value = fields.Float(related='esg_emission_factor_id.esg_uncertainty_value')
    partner_id = fields.Many2one(related='move_id.partner_id')
    product_id = fields.Many2one('product.product')
    product_category_id = fields.Many2one('product.category', related='product_id.categ_id')
    source_id = fields.Many2one(related='esg_emission_factor_id.source_id')
    scope = fields.Selection(related='source_id.scope')
    uom_id = fields.Many2one('uom.uom', string='UoM', compute='_compute_uom_id', store=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', store=True)
    compute_method = fields.Selection(related='esg_emission_factor_id.compute_method')
    price_subtotal = fields.Monetary(string='Amount', currency_field='currency_id', readonly=True)
    database_id = fields.Many2one(string='Source Database', related='esg_emission_factor_id.database_id')
    company_id = fields.Many2one('res.company')
    account_id = fields.Many2one('account.account', readonly=True)
    activity_type_ids = fields.Many2many('esg.activity.type', related='esg_emission_factor_id.activity_type_ids')

    @property
    def WRITE_ACCOUNT_EMISSION_FIELDS(self):
        return {
            'esg_emission_factor_id',
        }

    @property
    def READ_ACCOUNT_EMISSION_FIELDS(self):
        return self.WRITE_ACCOUNT_EMISSION_FIELDS | {
            'esg_emissions_value',
            'esg_uncertainty_value',
            'esg_uncertainty_absolute_value',
        }

    @property
    def WRITE_OTHER_EMISSION_FIELDS(self):
        return {
            'esg_emission_factor_id',
            'date',
            'date_end',
            'quantity',
            'note',
            'uom_id',
            'currency_id',
            'name',
            'company_id',
        }

    @property
    def READ_OTHER_EMISSION_FIELDS(self):
        return self.WRITE_OTHER_EMISSION_FIELDS | {
            'esg_emissions_value',
            'esg_uncertainty_value',
            'esg_uncertainty_absolute_value',
        }

    @api.depends('esg_emission_factor_id')
    def _compute_uom_id(self):
        for emission in self:
            if not emission._origin.id or emission._origin.id > 0:
                emission.uom_id = emission.esg_emission_factor_id.uom_id

    @api.depends('esg_emission_factor_id')
    def _compute_currency_id(self):
        for emission in self:
            if not emission._origin.id or emission._origin.id > 0:
                emission.currency_id = emission.esg_emission_factor_id.currency_id

    def _other_emission_select(self):
        return SQL("""
            oe.id AS id,
            oe.date AS date,
            oe.date_end as date_end,
            oe.esg_emission_factor_id AS esg_emission_factor_id,
            NULL AS move_id,
            oe.name as name,
            oe.note AS note,
            oe.quantity as quantity,
            ef.esg_emissions_value * oe.esg_emission_multiplicator as esg_emissions_value,
            ef.esg_emissions_value * oe.esg_emission_multiplicator * ef.esg_uncertainty_value as esg_uncertainty_absolute_value,
            (ef.esg_emissions_value * oe.esg_emission_multiplicator) / 1000 as esg_emissions_value_t,
            oe.uom_id as uom_id,
            oe.currency_id as currency_id,
            NULL as price_subtotal,
            NULL as partner_id,
            NULL as product_id,
            oe.company_id as company_id,
            NULL as account_id
        """)

    def _other_emission_from(self):
        return SQL("""
            esg_other_emission oe
            LEFT JOIN esg_emission_factor ef ON ef.id = oe.esg_emission_factor_id
        """)

    def _move_lines_select(self):
        return SQL("""
            -aml.id AS id,
            aml.date AS date,
            NULL as date_end,
            aml.esg_emission_factor_id AS esg_emission_factor_id,
            aml.move_id as move_id,
            aml.name as name,
            NULL AS note,
            aml.quantity as quantity,
            ef.esg_emissions_value * aml.esg_emission_multiplicator as esg_emissions_value,
            ef.esg_emissions_value * aml.esg_emission_multiplicator * ef.esg_uncertainty_value as esg_uncertainty_absolute_value,
            (ef.esg_emissions_value * aml.esg_emission_multiplicator) / 1000 as esg_emissions_value_t,
            aml.product_uom_id as uom_id,
            aml.currency_id as currency_id,
            aml.price_subtotal as price_subtotal,
            aml.partner_id as partner_id,
            aml.product_id as product_id,
            aml.company_id as company_id,
            aml.account_id as account_id
        """)

    def _move_lines_from(self):
        return SQL("""
            account_move_line aml
            LEFT JOIN esg_emission_factor ef ON ef.id = aml.esg_emission_factor_id
            LEFT JOIN account_account aa ON aa.id = aml.account_id
        """)

    def _move_lines_where(self):
        return SQL("""
            aml.quantity > 0
            AND aml.parent_state = 'posted'
            AND aa.account_type IN %s
        """, tuple(self.env['account.account'].ESG_VALID_ACCOUNT_TYPES))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""
     CREATE OR REPLACE VIEW %s AS (
                SELECT %s
                  FROM %s
             UNION ALL
                SELECT %s
                  FROM %s
                 WHERE %s
            )
            """,
            SQL.identifier(self._table),
            self._other_emission_select(),
            self._other_emission_from(),
            self._move_lines_select(),
            self._move_lines_from(),
            self._move_lines_where(),
        ))

    def action_create_other_emission(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'esg.other.emission',
        }

    def _update_field_value(self, field, value):
        field_description = self._fields.get(field)
        if field_description.relational:
            value = value.id or None
        field_description._update_cache(self, value)

    def write(self, vals):
        # To refactor
        other_emissions_from_report = self.filtered(lambda rec: rec.id > 0)
        account_emissions_from_report = self.filtered(lambda rec: rec.id < 0)

        other_emissions = self.env['esg.other.emission'].browse(other_emissions_from_report.ids)
        account_emissions = self.env['account.move.line'].browse(account_emissions_from_report.mapped(lambda aml: -aml.id))

        res = other_emissions.write({k: v for k, v in vals.items() if k in self.WRITE_OTHER_EMISSION_FIELDS}) and \
        account_emissions.write({k: v for k, v in vals.items() if k in self.WRITE_ACCOUNT_EMISSION_FIELDS})

        for other_emission_from_report, other_emission in zip(other_emissions_from_report, other_emissions):
            for field in self.READ_OTHER_EMISSION_FIELDS:
                other_emission_from_report._update_field_value(field, other_emission[field])

        for account_emission_from_report, account_emission in zip(account_emissions_from_report, account_emissions):
            for field in self.READ_ACCOUNT_EMISSION_FIELDS:
                account_emission_from_report._update_field_value(field, account_emission[field])

        return res

    def unlink(self):
        account_emissions_from_report = self.filtered(lambda rec: rec.id < 0)
        if account_emissions_from_report:
            raise UserError(self.env._('You cannot delete journal items from here.'))  # pylint: disable=E8503

        other_emissions_from_report = self.filtered(lambda rec: rec.id > 0)
        other_emissions = self.env['esg.other.emission'].browse(other_emissions_from_report.ids)
        res = other_emissions.unlink()
        return res

    def copy(self, default=None):
        account_emissions_from_report = self.filtered(lambda rec: rec.id < 0)
        if account_emissions_from_report:
            raise UserError(self.env._('You cannot copy emissions linked to journal items.'))

        other_emissions_from_report = self.filtered(lambda rec: rec.id > 0)
        other_emissions = self.env['esg.other.emission'].browse(other_emissions_from_report.ids)
        other_emissions.copy(default)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        return self.browse(self.env['esg.other.emission'].create(vals_list).ids)

    def action_generate_assignation_rules(self):
        def get_most_common(vals, total_count):
            if not vals:
                return False
            # Find the most common non-False value
            counts = Counter(v for v in vals if v)
            if not counts:
                return False
            most_common_val, count = counts.most_common(1)[0]
            # Heuristic: Must appear in more than 50% of records to be "representative"
            if count > (total_count / 2):
                return most_common_val
            return False

        valid_emissions = self.filtered(lambda line: line.id < 0)
        if not valid_emissions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('No valid emissions were selected. Please select emissions linked to journal items.'),
                },
            }

        existing_assignation_rules = self.env['esg.assignation.line'].search(
            [('esg_emission_factor_id', 'in', self.esg_emission_factor_id.ids)]
        )
        existing_assignation_rules = {
            (rule.product_id.id, rule.partner_id.id, rule.account_id.id, rule.product_category_id.id)
            for rule in existing_assignation_rules
        }
        assignation_rules_vals = []
        for emission_factor, lines in self.grouped('esg_emission_factor_id').items():
            if not emission_factor:
                continue
            if len(lines) == 1:
                rule = (lines.product_id.id, lines.partner_id.id, lines.account_id.id, lines.product_category_id.id)
                if not any(rule) or rule in existing_assignation_rules:
                    continue
                vals = {
                    'product_id': lines.product_id.id,
                    'partner_id': lines.partner_id.id,
                    'account_id': lines.account_id.id,
                    'product_category_id': lines.product_category_id.id,
                    'esg_emission_factor_id': emission_factor.id,
                }
                assignation_rules_vals.append(vals)
                existing_assignation_rules.add(rule)
            # Multiple lines share the same emission factor: create a "generic" rule
            else:
                total_count = len(lines)
                rule = (
                    get_most_common([line.product_id.id for line in lines], total_count),
                    get_most_common([line.partner_id.id for line in lines], total_count),
                    get_most_common([line.account_id.id for line in lines], total_count),
                    get_most_common([line.product_category_id.id for line in lines], total_count),
                )
                # Count how many fields were actually populated
                set_fields = [v for v in rule if v]
                if len(set_fields) < 2 or rule in existing_assignation_rules:
                    continue  # Should not produce any rule
                vals = {
                    'product_id': rule[0],
                    'partner_id': rule[1],
                    'account_id': rule[2],
                    'product_category_id': rule[3],
                    'esg_emission_factor_id': emission_factor.id,
                }
                assignation_rules_vals.append(vals)
                existing_assignation_rules.add(rule)
        if not assignation_rules_vals:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': self.env._('No assignment rules were created for the selected emission lines. Emission factors may be missing, or rules already exist.'),
                },
            }
        assignation_rules = self.env['esg.assignation.line'].create(assignation_rules_vals)
        return {
            **self.env['ir.actions.actions']._for_xml_id('esg.action_view_assignation_rule'),
            'display_name': self.env._('Generated Rules'),
            'context': {'search_default_group_by_emission_factor': True, 'create': False},
            'domain': [('id', 'in', assignation_rules.ids)],
        }
