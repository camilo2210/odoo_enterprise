# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

PRORATA_COMPUTATION_SELECTION = [
    ('none', "No Prorata"),
    ('constant_periods', "Constant Periods"),
    ('daily_computation', "Based on days per period"),
]


class DepreciationModel(models.Model):
    _name = 'account.depreciation.model'
    _description = 'Depreciation Models for Assets'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'method desc, method_period desc, method_number, method_progress_factor'
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of

    name = fields.Char(
        compute='_compute_name', store=True, readonly=False,
        inverse='_inverse_name',
        tracking=True,
    )
    is_name_custom = fields.Boolean(
        default=False,
        help="Set when the name is entered manually, so that it is no longer regenerated from the model's configuration.",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        domain=lambda self: [('id', 'in', self.env.companies.ids)],
        help="Select a specific company to limit this model's use, or leave it empty to make this model available across all companies."
    )
    active = fields.Boolean(default=True)

    method = fields.Selection(
        selection=[
            ('linear', "Straight Line"),
            ('degressive', "Declining"),
            ('degressive_then_linear', "Declining then Straight Line"),
            ('no_depreciation', "No depreciation"),
        ],
        string="Method",
        default='linear',
        required=True,
        help="Choose the method to use to compute the amount of depreciation lines.\n"
             "  * No Depreciation\n"
             "  * Straight Line: Calculated on basis of: Gross Value / Duration\n"
             "  * Declining: Calculated on basis of: Residual Value * Declining Factor\n"
             "  * Declining then Straight Line: Like Declining but with a minimum depreciation value equal to the straight line value.",
    )
    method_mode = fields.Selection(
        selection=[('duration', "Duration"), ('rate', "Rate")],
        default='duration',
        help="Choose whether the straight-line depreciation is driven by a duration or an annual rate.",
    )
    method_number = fields.Float(string="Duration", required=True, default=5, help="The number of depreciations needed to depreciate your asset")
    method_period = fields.Selection(
        selection=[('1', "Month"), ('12', "Year")],
        string="Number of Months in a Period",
        required=True,
        default='12',
        help="The amount of time between two depreciations",
    )
    method_rate = fields.Float(
        string="Depreciation Rate",
        digits=(16, 4),  # shown as a percentage, so 4 digits here are 2 decimals on screen
        compute='_compute_linear_rate', inverse='_inverse_linear_rate',
    )
    method_progress_factor = fields.Float(string="Declining Factor", default=0.0)
    prorata_computation_type = fields.Selection(
        selection=PRORATA_COMPUTATION_SELECTION,
        string="Computation",
        required=True, default='constant_periods',
    )
    salvage_value_percent = fields.Float(
        string="Not Depreciable",
        help="It is the amount you plan to have that you cannot depreciate.",
        default=0.0,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Journal",
        company_dependent=True,
        copy=True,
        check_company=True,
        domain="[('type', '=', 'general')]",
        compute='_compute_journal_id', store=True, readonly=False,
        help="Journal used for asset creation. The value is stored per company, so a model shared"
             " across companies posts to the journal of the company using it.",
    )
    is_ledger_journal = fields.Boolean(compute='_compute_is_ledger_journal')
    has_locking_assets = fields.Boolean(
        compute='_compute_has_locking_assets',
        help="Whether an asset using this model is confirmed, on hold or closed, which freezes its depreciation configuration.",
    )

    # Ledger accounts
    ledger_depreciation_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Accumulated Account",
        domain=[('account_type', 'in', ('asset_fixed', 'asset_non_current', 'equity'))],
        company_dependent=True,
        copy=True,
    )
    ledger_expense_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Expense Account",
        domain=[('account_type', 'in', ('expense_depreciation', 'expense_other', 'expense'))],
        company_dependent=True,
        copy=True,
    )
    ledger_recovery_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Recovery Account",
        domain=[('account_type', 'in', ('income', 'income_other'))],
        company_dependent=True,
        copy=True,
        help="Account used to record the reversal of excess depreciation when statutory depreciation catches up or the asset is disposed of.",
    )

    asset_ids = fields.One2many(
        comodel_name='account.asset.variant',
        inverse_name='model_id',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('company_id')
    def _compute_journal_id(self):
        """ Fill in a default journal for the context company only: 'journal_id' is
            company-dependent, so each company gets its own value. Models the active company
            cannot use are left untouched, their journal belongs to another company.
        """
        company = self.env.company
        journal_domain = self.env['account.journal']._check_company_domain(company)
        to_compute = self.filtered(
            lambda m: (not m.company_id or m.company_id == company)
            # empty, or pointing to a journal the active company may not use
            and not m.journal_id.filtered_domain(journal_domain)
        )
        domain = [*journal_domain, ('type', '=', 'general')]
        if self.env.context.get('ledger_journal_only'):
            domain.append(('journal_group_id', '!=', False))
            if excluded_ledger_group_ids := self.env.context.get('excluded_ledger_group_ids', []):
                domain.append(('journal_group_id', 'not in', excluded_ledger_group_ids))
        else:
            domain.append(('journal_group_id', '=', False))
        to_compute.journal_id = self._get_journal(company, domain=domain, create_missing=False, include_parents=False)

    def _get_locking_model_companies(self):
        """ Return the (model, company) pairs for which an asset freezes the configuration of
            the model.
        """
        return set(self.env['account.asset.variant'].sudo()._read_group(
            domain=[('model_id', 'in', self.ids), ('state', 'in', ['open', 'paused', 'close'])],
            groupby=['model_id', 'company_id'],
        ))

    @api.depends('asset_ids.state')
    def _compute_has_locking_assets(self):
        locking_models = {model for model, _company in self._get_locking_model_companies()}
        for model in self:
            model.has_locking_assets = model in locking_models

    @api.depends('journal_id')
    @api.depends_context('company')
    def _compute_is_ledger_journal(self):
        for model in self:
            model.is_ledger_journal = bool(model.journal_id.journal_group_id)

    @api.depends('method', 'method_mode', 'method_number', 'method_period', 'method_progress_factor',
                 'prorata_computation_type', 'salvage_value_percent', 'company_id', 'journal_id', 'is_name_custom')
    def _compute_name(self):
        default_name_models = self.filtered(lambda m: not m.is_name_custom)
        if not default_name_models:
            return

        existing_configs = self._get_existing_configs()
        for model in default_name_models:
            model.name = model._get_default_name(existing_configs)

    @api.onchange('name')
    def _inverse_name(self):
        existing_configs = self._get_existing_configs()
        for model in self:
            if model.name:
                model.is_name_custom = model.name != model._get_default_name(existing_configs)
            else:
                model.is_name_custom = False
                model.name = model._get_default_name(existing_configs)

    def _get_existing_configs(self):
        """ Return the existing model configurations other than ``self``, whose names
            may need a journal to tell them apart.
        """
        return set(
            self._read_group(
                domain=[*self._check_company_domain(self.env.company), ('id', 'not in', self.ids)],
                groupby=['method', 'method_number', 'method_period', 'method_progress_factor', 'salvage_value_percent'],
            )
        )

    def _get_default_name(self, existing_configs=None):
        self.ensure_one()
        if existing_configs is None:
            existing_configs = self._get_existing_configs()

        method_name = {
            **dict(self._fields['method']._description_selection(self.env)),
            'linear': self.env._("Linear"),
            'degressive_then_linear': self.env._("Declining then Linear"),
        }
        prorata_computation_name = {
            **dict(self._fields['prorata_computation_type']._description_selection(self.env)),
            'daily_computation': self.env._("Daily Computation"),
        }

        journal = self.with_company(self.company_id).journal_id if self.company_id else self.env['account.journal']
        model_exists = (self.method, self.method_number, self.method_period, self.method_progress_factor, self.salvage_value_percent) in existing_configs
        return self.env._(
            "%(progress_factor)s%(duration)s%(method)s%(prorata_name)s%(salvage_percent)s%(journal_name)s",
            progress_factor=(f"{self.method_progress_factor * 100:g}%, " if self.method in ('degressive', 'degressive_then_linear') else ""),
            duration=(f"{duration} " if (duration := self._get_display_duration()) else ""),
            method=(f"{method_name.get(self.method)} " if self.method not in ('linear', 'degressive') else ""),
            prorata_name=(f"{prorata_computation_name.get(self.prorata_computation_type)} " if (self.prorata_computation_type != 'constant_periods') else ""),
            salvage_percent=(self.env._(", %(percent)g%% salvage ", percent=self.salvage_value_percent * 100) if self.salvage_value_percent > 0.0 else ""),
            journal_name=(f"({journal.name})" if (journal.journal_group_id or model_exists) and journal else ""),
        ).strip()

    @api.depends('method_number')
    def _compute_linear_rate(self):
        for model in self:
            if model.method_number:
                model.method_rate = 1 / model.method_number

    @api.onchange('method_rate')
    def _inverse_linear_rate(self):
        for model in self:
            if model.method_rate and model.method == 'linear' and model.method_mode == 'rate':
                model.method_number = 1 / model.method_rate

    # -------------------------------------------------------------------------
    # CONSTRAINT METHODS
    # -------------------------------------------------------------------------

    @api.constrains('journal_id', 'ledger_recovery_account_id')
    def _check_ledger_recovery_account(self):
        for model in self:
            if model.is_ledger_journal and not model.ledger_recovery_account_id:
                raise ValidationError(self.env._(
                    "A Recovery Account is required on the depreciation model %(model)s: "
                    "its journal %(journal)s belongs to the ledger %(ledger)s.",
                    model=model.display_name,
                    journal=model.journal_id.display_name,
                    ledger=model.journal_id.journal_group_id.display_name,
                ))

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('method')
    def _onchange_method(self):
        if self.method == 'no_depreciation':
            self.method_number = 0
            self.method_progress_factor = 0
            self.prorata_computation_type = 'constant_periods'
            self.salvage_value_percent = 0

    @api.onchange('company_id')
    def _onchange_company_id(self):
        company_count = self.env['res.company'].search_count([])
        if self._origin.id and not self._origin.company_id and self.company_id and company_count > 1:
            return {
                'warning': {
                    'title': self.env._("Important Change"),
                    'message': self.env._("Please note that by doing this, you will remove this model from other companies"),
                }
            }

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------

    def write(self, vals):
        editable_fields = {
            'active', 'name', 'is_name_custom',
            'journal_id', 'prorata_computation_type', 'salvage_value_percent',
            'ledger_depreciation_account_id', 'ledger_expense_account_id', 'ledger_recovery_account_id',
        }
        is_shared_with_all_companies = 'company_id' in vals and not vals['company_id']
        if is_shared_with_all_companies:
            editable_fields.add('company_id')
        must_check_assets = any(
            record._fields[fname].convert_to_write(record[fname], record) != value
            for fname, value in vals.items()
            if fname not in editable_fields
            for record in self
        )
        if must_check_assets:
            locking_companies = {company for _model, company in self._get_locking_model_companies()}
            if self.env.company in locking_companies:
                raise UserError(self.env._("Cannot update a depreciation model that has non-draft or non-cancelled assets."))
            elif locking_companies:
                raise UserError(self.env._("Cannot update a depreciation model being used by another company."))
        result = super().write(vals)
        if is_shared_with_all_companies:
            for company in self.env['res.company'].sudo().search([('parent_id', '=', False)]):
                self.sudo().with_company(company)._compute_journal_id()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        depreciation_models = super().create(vals_list)
        if self.env.context.get('ledger_journal_only'):
            for model in depreciation_models:
                if not model.journal_id.journal_group_id:
                    raise ValidationError(self.env._("A journal with a ledger is required to create a depreciation model in this context."))
        for company in self.env['res.company'].sudo().search([('parent_id', '=', False)]):
            depreciation_models.sudo().with_company(company)._compute_journal_id()
        return depreciation_models

    # -------------------------------------------------------------------------
    # PUBLIC ACTIONS
    # -------------------------------------------------------------------------

    def action_open_model_assets(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Related Assets'),
            'view_mode': 'list,form',
            'res_model': 'account.asset',
            'domain': [('variant_ids.model_id', '=', self.id)],
        }

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    def _get_journal(self, company, domain=(), create_missing=True, include_parents=True):
        """ Return the journal an asset depreciating with this model should post to.
            Could either by 'journal_id', first MISC journal in company, or newly created
            MISC journal if the model has a company set.
        """
        if not self:
            return self.env['account.journal']

        journal_domain = [*domain, *self.env['account.journal']._check_company_domain(company)]
        journal = self.with_company(company).journal_id
        if include_parents and not journal:
            journal = next(
                (journal for candidate in company.parent_ids[::-1]
                if (journal := self.with_company(candidate).journal_id.filtered_domain(journal_domain))),
                self.env['account.journal'],
            )
        if not journal:
            journal = self.env['account.journal'].search([
                *journal_domain,
                ('type', '=', 'general'),
            ], limit=1)
        if create_missing and not journal and company:
            journal = self.env['account.journal'].create({
                'name': self.env._('Miscellaneous Operations'),
                'type': 'general',
                'show_on_dashboard': False,
                'company_id': company.id,
            })
        return journal

    def _get_display_duration(self):
        self.ensure_one()
        if self.method == 'no_depreciation' or not self.method_number:
            return ""

        period = dict(self._fields['method_period']._description_selection(self.env))[self.method_period]
        return f"{self._get_rounded_duration():g} {period}"

    def _get_rounded_duration(self):
        """Return the number of periods for this model for a given rate.

        `method_rate` is entered as a percentage not stored and only its inverse (`method_number`)
        is stored. The inverse of the rate lands just short of the round figure that was meant.
        Try the shortest representation of the inverse first, and keep the first one that still
        renders as the rate that was entered.

            entered rate       method_number   returns
            2.78 % per month   35.9712         36     -> 3 years, as meant
            4.17 % per month   23.9808         24     -> 2 years, as meant
            33.33 % per year   3.0003          3
            22.22 % per year   4.5005          4.5    -> a deliberate half-period is kept
            15 % per year      6.6667          6.67   -> no shorter form renders as 15 %

        Only rate-based linear models need this; every other mode already stores the duration
        that was typed.
        """
        self.ensure_one()
        DURATION_DISPLAY_DECIMALS = 2

        rounded = round(self.method_number, DURATION_DISPLAY_DECIMALS)
        if self.method != 'linear' or self.method_mode != 'rate' or not rounded:
            return rounded

        _precision, rate_digits = self._fields['method_rate'].get_digits(self.env)
        for decimals in range(DURATION_DISPLAY_DECIMALS):
            candidate = round(self.method_number, decimals)
            if candidate and float_compare(1 / candidate, self.method_rate, precision_digits=rate_digits) == 0:
                return candidate
        return rounded
