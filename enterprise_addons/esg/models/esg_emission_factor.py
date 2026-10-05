from odoo import api, fields, models
from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)


class EsgEmissionFactor(models.Model):
    _name = 'esg.emission.factor'
    _description = 'Emission Factor'
    _inherit = [
        'mail.thread',
    ]

    name = fields.Char(required=True)
    sequence = fields.Integer()
    active = fields.Boolean(default=True)

    code = fields.Char(string="Code", index=True)  # required=True

    esg_emissions_value = fields.Float(compute='_compute_esg_emissions_value', digits='Carbon Emissions', string='Emissions', store=True, readonly=False, tracking=True)
    source_id = fields.Many2one('esg.emission.source', required=True, index=True, help="The activity or process that generates greenhouse gas emissions.")
    scope = fields.Selection(related='source_id.scope')
    company_id = fields.Many2one('res.company')

    valid_from = fields.Date(help="The time period under which this emission factor applies.")
    valid_to = fields.Date()

    esg_uncertainty_value = fields.Float(string="Uncertainty", help="Estimated margin of error for this emission factor, expressed as a percentage.")
    compute_method = fields.Selection(selection=[
            ('physically', 'Physically (Quantity)'),
            ('monetary', 'Monetary'),
        ],
        required=True,
        default='physically',
        help="The approach used to calculate emissions, based on either physical quantities or monetary values.",
    )
    unit_name = fields.Char(compute='_compute_unit_name')
    database_id = fields.Many2one('esg.database', help="The reference source or database where this emission factor is obtained.")
    gas_line_ids = fields.One2many('esg.emission.factor.line', 'esg_emission_factor_id', tracking=True)
    assignation_line_ids = fields.One2many('esg.assignation.line', 'esg_emission_factor_id')
    description = fields.Html()
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', compute='_compute_uom_id', store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', store=True, readonly=False)
    activity_type_ids = fields.Many2many('esg.activity.type', string='Activity Types', compute='_compute_activity_type_ids', store=True)
    account_move_line_ids = fields.One2many('account.move.line', 'esg_emission_factor_id')
    esg_other_emission_ids = fields.One2many('esg.other.emission', 'esg_emission_factor_id')
    nb_linked_emissions = fields.Integer(compute='_compute_nb_linked_emissions')
    region = fields.Char('Region / Regional Conditions', help="The geographical area where this emission factor is relevant.")
    country_ids = fields.Many2many('res.country', string='Countries', help='The countries where this emission factor is relevant.', falsy_value_label=_lt("All Countries"))
    state_ids = fields.Many2many('res.country.state', string='States', compute='_compute_state_ids', readonly=False, store=True, domain="[('country_id', 'in', country_ids)]", help='The states where this emission factor is relevant.', falsy_value_label=_lt("All States"))
    is_user_company_country_included = fields.Boolean(compute='_compute_is_user_company_country_included', search='_search_is_user_company_country_included', export_string_translation=False)

    @api.depends('uom_id', 'currency_id', 'compute_method')
    def _compute_unit_name(self):
        for factor in self:
            if factor.compute_method == 'monetary':
                factor.unit_name = factor.currency_id.name
            else:
                factor.unit_name = factor.uom_id.name

    @api.depends('gas_line_ids.esg_emissions_value')
    def _compute_esg_emissions_value(self):
        for factor in self:
            factor.esg_emissions_value = sum(factor.gas_line_ids.mapped('esg_emissions_value'))

    @api.depends('compute_method')
    def _compute_uom_id(self):
        for factor in self:
            if factor.compute_method == 'monetary':
                factor.uom_id = False

    @api.depends('compute_method')
    def _compute_currency_id(self):
        for factor in self:
            if factor.compute_method == 'physically':
                factor.currency_id = False

    @api.depends('gas_line_ids.activity_type_id')
    def _compute_activity_type_ids(self):
        for factor in self:
            factor.activity_type_ids = factor.gas_line_ids.activity_type_id

    @api.depends('account_move_line_ids', 'esg_other_emission_ids')
    def _compute_nb_linked_emissions(self):
        for factor in self:
            factor.nb_linked_emissions = len(
                factor.account_move_line_ids.filtered(lambda aml: aml.parent_state == 'posted'),
            ) + len(factor.esg_other_emission_ids)

    @api.depends('country_ids')
    def _compute_state_ids(self):
        for factor in self:
            for state in factor.state_ids:
                if state.country_id in factor.country_ids:
                    continue
                factor.state_ids -= state

    @api.depends('country_ids')
    def _compute_is_user_company_country_included(self):
        user_country = self.env.company.country_id
        for factor in self:
            if not factor.country_ids:
                factor.is_user_company_country_included = True
            elif user_country:
                factor.is_user_company_country_included = user_country in factor.country_ids
            else:
                factor.is_user_company_country_included = False

    def _search_is_user_company_country_included(self, operator, value):
        user_country = self.env.company.country_id
        searching_for_true = bool(
            (operator in ('=', 'in') and value) or (operator in ('!=', 'not in') and not value)
        )

        if searching_for_true:
            return ['|',
                ('country_ids', '=', False),
                ('country_ids', 'in', user_country.ids),
            ]
        return [
            ('country_ids', '!=', False),
            ('country_ids', 'not in', user_country.ids),
        ]

    def action_open_linked_emissions(self):
        self.ensure_one()
        return {
            'name': self.env._("Emissions using %(emission_factor)s", emission_factor=self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,kanban,graph,pivot',
            'res_model': 'esg.carbon.emission.report',
            'domain': [('esg_emission_factor_id', '=', self.id)],
        }
