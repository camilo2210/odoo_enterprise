# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.fields import Domain
from odoo.tools import float_is_zero, formatLang

from odoo.addons.account.models.product import ACCOUNT_DOMAIN


class AccountAsset(models.Model):
    _name = 'account.asset'
    _description = 'Asset/Revenue Recognition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'analytic.mixin']

    # Asset Values
    name = fields.Char(
        string="Asset Name",
        compute='_compute_name', store=True, readonly=False,
        required=True,
        tracking=True,
        translate=True,
    )
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    is_multi_ledger_company = fields.Boolean(related='company_id.has_ledger')
    country_code = fields.Char(related='company_id.account_fiscal_country_id.code')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    account_asset_id = fields.Many2one(
        'account.account',
        string='Fixed Asset Account',
        compute='_compute_account_asset_id',
        store=True, readonly=False, precompute=True,
        check_company=True,
        domain="[('account_type', '!=', 'off_balance')]",
        help="Account used to record the purchase of the asset at its original price.",
    )
    asset_group_id = fields.Many2one('account.asset.group', string='Asset Group', tracking=True, index=True)
    active = fields.Boolean(default=True)

    original_value = fields.Monetary(string="Asset Value", compute='_compute_value', store=True, readonly=False)
    non_deductible_tax_value = fields.Monetary(string="Non Deductible Tax Value", compute="_compute_non_deductible_tax_value", store=True, readonly=True)
    related_purchase_value = fields.Monetary(compute='_compute_related_purchase_value')
    acquisition_date = fields.Date(
        compute='_compute_acquisition_date', store=True, precompute=True,
        readonly=False,
        copy=True,
        string="Date",
    )

    original_move_line_ids = fields.Many2many('account.move.line', 'asset_move_line_rel', 'asset_id', 'line_id', string='Journal Items', copy=False)
    original_move_lines_count = fields.Integer(compute='_compute_original_move_lines_count')

    origin_asset_id = fields.Many2one(
        comodel_name='account.asset',
        string="Original Asset",
        readonly=True,
        copy=False,
        index='btree_not_null',
        check_company=True,
    )
    derived_asset_ids = fields.One2many(
        comodel_name='account.asset',
        inverse_name='origin_asset_id',
        string="Derived Assets",
    )

    asset_properties = fields.Properties('Properties', definition='account_asset_id.asset_properties_definition', copy=True)

    linked_assets_ids = fields.One2many(
        comodel_name='account.asset',
        string="Linked Assets",
        compute='_compute_linked_assets',
    )
    count_linked_asset = fields.Integer(compute="_compute_linked_assets")
    warning_count_assets = fields.Boolean(compute="_compute_linked_assets")

    variant_ids = fields.One2many(
        comodel_name='account.asset.variant',
        inverse_name='asset_id',
        copy=False,
        string="Asset Variants",
    )
    variant_count = fields.Integer(compute="_compute_variant_info")
    variant_ledger_names = fields.Char(compute='_compute_variant_info')
    warning_sub_assets = fields.Boolean(compute="_compute_variant_info")

    # Main Variant Values
    main_variant_id = fields.Many2one(
        comodel_name='account.asset.variant',
        compute='_compute_main_variant_id',
        string="Main Asset", store=True, copy=False,
    )
    is_main_variant = fields.Boolean(compute='_compute_is_main_variant')
    main_variant_state = fields.Selection(related='main_variant_id.state', copy=False, readonly=True)   # Main variant state used in list view
    main_variant_model_name = fields.Char(related='main_variant_id.model_id.display_name', string="Main Asset Model Name")
    main_variant_parent_id = fields.Many2one(
        related='main_variant_id.parent_id',
        string="Main Variant Parent"
    )

    # Current Selected Variant Values
    current_selected_variant_id = fields.Many2one(
        comodel_name='account.asset.variant',
        compute='_compute_current_selected_variant_id',
        search='_search_current_selected_variant_id',
    )
    is_ledger_variant = fields.Boolean(related='current_selected_variant_id.is_ledger_variant')
    state = fields.Selection(     # Variant state used in form view
        selection=[
            ('draft', 'Draft'),
            ('open', 'Running'),
            ('paused', 'On Hold'),
            ('close', 'Closed'),
            ('cancelled', 'Cancelled')],
        compute='_compute_variant_state',
        string="Variant Status",
    )
    model_id = fields.Many2one(
        comodel_name='account.depreciation.model',
        related='current_selected_variant_id.model_id',
        readonly=False,
    )
    method = fields.Selection(related='current_selected_variant_id.method')
    book_value = fields.Monetary(related='current_selected_variant_id.book_value')
    value_residual = fields.Monetary(related='current_selected_variant_id.value_residual')
    salvage_value = fields.Monetary(related='current_selected_variant_id.salvage_value', readonly=False)
    gross_increase_value = fields.Monetary(related='current_selected_variant_id.gross_increase_value')
    already_depreciated_amount_import = fields.Monetary(related='current_selected_variant_id.already_depreciated_amount_import', readonly=False)
    prorata_date = fields.Date(related='current_selected_variant_id.prorata_date')
    prorata_computation_type = fields.Selection(
        related='current_selected_variant_id.prorata_computation_type',
        readonly=False,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Journal",
        related='current_selected_variant_id.journal_id',
    )
    parent_id = fields.Many2one(comodel_name='account.asset.variant', related='current_selected_variant_id.parent_id')

    depreciation_move_ids = fields.One2many(
        'account.move', related='current_selected_variant_id.depreciation_move_ids', readonly=False, string="Depreciation Lines"
    )
    depreciation_entries_count = fields.Integer(related='current_selected_variant_id.depreciation_entries_count')
    gross_increase_count = fields.Integer(related='current_selected_variant_id.gross_increase_count')
    total_depreciation_entries_count = fields.Integer(related='current_selected_variant_id.total_depreciation_entries_count')

    # Import fields
    import_account_depreciation_id = fields.Many2one(
        comodel_name='account.account', check_company=True, store=False,
        domain=ACCOUNT_DOMAIN,
    )
    import_account_depreciation_expense_id = fields.Many2one(
        comodel_name='account.account', check_company=True, store=False,
        domain=ACCOUNT_DOMAIN,
    )

    # -------------------------------------------------------------------------
    # COMPUTE & SEARCH METHODS
    # -------------------------------------------------------------------------
    @api.depends('current_selected_variant_id.state')
    def _compute_variant_state(self):
        for asset in self:
            asset.state = asset.current_selected_variant_id.state or 'draft'

    @api.depends_context('variant_id')
    @api.depends('main_variant_id', 'current_selected_variant_id')
    def _compute_is_main_variant(self):
        for asset in self:
            asset.is_main_variant = asset.main_variant_id == asset.current_selected_variant_id

    @api.depends('variant_ids')
    def _compute_main_variant_id(self):
        for asset in self:
            if not asset.main_variant_id:
                # if there is no main variant set then take first variant that doesn't have a ledger
                asset.main_variant_id = asset.variant_ids.filtered(lambda v: not v.is_ledger_variant)[:1] or asset.variant_ids.sorted('id')[:1]

    @api.depends_context('variant_id')
    @api.depends('main_variant_id')
    def _compute_current_selected_variant_id(self):
        for asset in self:
            variant = self.env['account.asset.variant'].browse(self.env.context.get('variant_id'))
            if variant and variant.asset_id == asset:
                asset.current_selected_variant_id = variant
            if not asset.current_selected_variant_id:
                asset.current_selected_variant_id = asset.main_variant_id

    def _search_current_selected_variant_id(self, operator, value):
        context_variant = self.env['account.asset.variant'].browse(self.env.context.get('variant_id')).exists()
        context_variant_matches = bool(context_variant.filtered_domain([('id', operator, value)]))
        asset = context_variant.asset_id
        main_variant_domain = Domain('main_variant_id', operator, value)
        if not context_variant:
            return main_variant_domain
        if context_variant_matches:
            return main_variant_domain | Domain('id', '=', asset.id)
        return main_variant_domain & Domain('id', '!=', asset.id)

    @api.depends('original_move_line_ids', 'non_deductible_tax_value')
    def _compute_value(self):
        for asset in self:
            if asset.state != 'draft' or not asset.original_move_line_ids:
                asset.original_value = asset.original_value or False
                continue
            if any(line.move_id.state == 'draft' for line in asset.original_move_line_ids):
                raise UserError(self.env._("All the lines should be posted"))
            asset.original_value = asset.related_purchase_value
            if asset.non_deductible_tax_value:
                asset.original_value += asset.non_deductible_tax_value

    @api.depends('original_move_line_ids')
    def _compute_account_asset_id(self):
        for asset in self.filtered(lambda a: a.state == 'draft'):
            if asset.original_move_line_ids:
                if len(asset.original_move_line_ids.account_id) > 1:
                    raise UserError(self.env._("All the lines should be from the same account"))
                asset.account_asset_id = asset.original_move_line_ids.account_id

    @api.depends('original_move_line_ids')
    def _compute_related_purchase_value(self):
        for asset in self:
            related_purchase_value = sum(
                line.balance * line.deductible_percentage
                for line in asset.original_move_line_ids
                if not line.tax_repartition_line_id and not line.tax_line_id
            )
            asset.related_purchase_value = related_purchase_value

    @api.depends('original_move_line_ids')
    def _compute_acquisition_date(self):
        today = fields.Date.context_today(self)
        for asset in self.filtered(lambda a: a.state == 'draft'):
            asset.acquisition_date = asset.acquisition_date or min(
                [(aml.invoice_date or aml.date) for aml in asset.original_move_line_ids] + [today]
            )

    @api.depends('original_move_line_ids')
    def _compute_name(self):
        for asset in self.filtered(lambda a: a.state == 'draft'):
            asset.name = asset.name or (asset.original_move_line_ids and asset.original_move_line_ids[0].name or '')

    @api.depends('original_move_line_ids')
    def _compute_non_deductible_tax_value(self):
        for asset in self.filtered(lambda a: a.state == 'draft'):
            asset.non_deductible_tax_value = 0.0
            for line in asset.original_move_line_ids:
                if line.non_deductible_tax_value:
                    converted_non_deductible_tax_value = line.currency_id._convert(line.non_deductible_tax_value, asset.currency_id, asset.company_id, line.date)
                    converted_non_deductible_tax_value *= line.deductible_percentage
                    asset.non_deductible_tax_value += asset.currency_id.round(converted_non_deductible_tax_value)

    @api.depends('original_move_line_ids.asset_ids')
    def _compute_linked_assets(self):
        for asset in self:
            asset.linked_assets_ids = asset.original_move_line_ids.asset_ids - self
            asset.count_linked_asset = len(asset.linked_assets_ids)
            confirmed_assets = asset.linked_assets_ids.filtered(lambda x: x.state == "open")
            # The warning_count_assets is useful to put the smart button in red, in case at least one asset has been confirmed
            asset.warning_count_assets = len(confirmed_assets) > 0

    @api.depends('original_move_line_ids')
    def _compute_analytic_distribution(self):
        for asset in self.filtered(lambda a: a.state == 'draft'):
            distribution_asset = {}
            amount_total = sum(asset.original_move_line_ids.mapped("balance"))
            if not float_is_zero(amount_total, precision_rounding=asset.currency_id.rounding):
                for line in asset.original_move_line_ids._origin:
                    if line.analytic_distribution:
                        for account, distribution in line.analytic_distribution.items():
                            distribution_asset[account] = distribution_asset.get(account, 0) + distribution * line.balance
                for account, distribution_amount in distribution_asset.items():
                    distribution_asset[account] = distribution_amount / amount_total
            asset.analytic_distribution = distribution_asset if distribution_asset else asset.analytic_distribution

    @api.depends('original_move_line_ids')
    def _compute_original_move_lines_count(self):
        for asset in self:
            asset.original_move_lines_count = len(asset.original_move_line_ids)

    @api.depends('variant_ids', 'variant_ids.state', 'main_variant_id')
    def _compute_variant_info(self):
        for asset in self:
            asset.variant_count = len(asset.variant_ids)
            sub_assets = asset.variant_ids.filtered(lambda v: v != asset.main_variant_id)
            asset.warning_sub_assets = 'draft' in sub_assets.mapped('state')
            ledger_names = sub_assets.journal_id.journal_group_id.mapped('name')
            if ledger_names:
                asset.variant_ledger_names = ledger_names[0] + ("..." if len(sub_assets) > 1 else "")
            else:
                asset.variant_ledger_names = str(len(sub_assets)) if sub_assets else ''

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('account_asset_id')
    def _onchange_account_asset_id(self):
        self.model_id = self.account_asset_id.depreciation_model_id
        self.prorata_computation_type = self.account_asset_id.depreciation_model_id.prorata_computation_type

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.prorata_computation_type = self.model_id.prorata_computation_type
        self.method = self.model_id.method
        self.journal_id = self.model_id._get_journal(self.company_id)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if not self.company_id or self.company_id not in self.account_asset_id.company_ids:
            self.account_asset_id = False

    @api.onchange('original_value', 'original_move_line_ids')
    def _display_original_value_warning(self):
        if self.state != 'draft':
            warning = {
                'title': self.env._("Warning for modifying bills for asset %s", self.name),
                'message': self.env._("New bills added/modified will not update the non-draft asset's values. "
                             "Please make sure this is what you want.")
            }
            return {'warning': warning}
        if self.original_move_line_ids:
            computed_original_value = self.related_purchase_value + self.non_deductible_tax_value
            if self.original_value != computed_original_value:
                warning = {
                    'title': self.env._("Warning for the Original Value of %s", self.name),
                    'message': self.env._("The amount you have entered (%(entered_amount)s) does not match the Related Purchase's value (%(purchase_value)s). "
                                 "Please make sure this is what you want.",
                                 entered_amount=formatLang(self.env, self.original_value, currency_obj=self.currency_id),
                                 purchase_value=formatLang(self.env, computed_original_value, currency_obj=self.currency_id))
                }
                return {'warning': warning}

    @api.onchange('original_move_line_ids')
    def _onchange_original_move_line_ids(self):
        # Force the recompute
        if self.state == 'draft':
            self.acquisition_date = False
            self._compute_acquisition_date()

    # -------------------------------------------------------------------------
    # CONSTRAINT METHODS
    # -------------------------------------------------------------------------
    @api.constrains('active')
    def _check_active(self):
        # Archiving the asset already flipped every variant inactive ('active' is related to
        # the asset), so 'variant_ids' has to be read past 'active_test' to see them at all.
        for asset in self.with_context(active_test=False):
            if not asset.active:
                if asset.main_variant_state != 'close':
                    raise UserError(self.env._('You cannot archive a record that is not closed'))
                if any(variant.state != 'close' for variant in asset.variant_ids):
                    raise UserError(self.env._('You cannot archive a record that has at least one variant that is not closed'))

    @api.constrains('original_move_line_ids')
    def _check_related_purchase(self):
        for asset in self:
            if asset.original_move_line_ids and asset.related_purchase_value == 0:
                raise UserError(self.env._("You cannot create an asset from lines containing credit and debit on the account or with a null amount"))
            if len(asset.original_move_line_ids.account_id) > 1:
                raise UserError(self.env._("All the lines should be from the same account"))

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------
    @api.ondelete(at_uninstall=True)
    def _unlink_if_draft(self):
        for asset in self:
            if asset.state in ['open', 'paused', 'close']:
                raise UserError(self.env._(
                    'You cannot delete a document that is in %s state.',
                    dict(self._fields['state']._description_selection(self.env)).get(asset.state)
                ))

    def unlink(self):
        if not self.env.context.get('delete_asset'):
            return self.current_selected_variant_id.unlink()
        else:
            for asset in self:
                for line in asset.original_move_line_ids:
                    if line.name:
                        body = self.env._('A document linked to %(move_line_name)s has been deleted: %(link)s',
                            move_line_name=line.name,
                            link=asset._get_html_link(),
                        )
                    else:
                        body = self.env._('A document linked to this move has been deleted: %s',
                            asset._get_html_link())
                    line.move_id.message_post(body=body)
                    if len(line.move_id.asset_ids) == 1:
                        line.move_id.asset_move_type = False
            return super().unlink()

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        for asset, vals in zip(self, vals_list):
            vals['account_asset_id'] = asset.account_asset_id.id
            vals['main_variant_id'] = False
        return vals_list

    def copy(self, default=None):
        new_assets = super().copy(default)
        for old_asset, new_asset in zip(self, new_assets):
            # Copying the main variant from the old asset and explicitly linking it to the new asset
            new_asset.main_variant_id = old_asset.main_variant_id.copy({
                'asset_id': new_asset.id,
            })
        return new_assets

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'state' in vals and vals['state'] != 'draft' and not (set(vals) - set({'account_depreciation_id', 'account_depreciation_expense_id', 'journal_id'})):
                raise UserError(self.env._("Some required values are missing"))

        # To keep the same asset creation
        # An asset variant in created implicitly
        # Need to separate the asset values and variant values to avoid unexpected behavior
        asset_vals_list, variant_vals_list = (
            zip(*(self._split_assets_variants_vals(vals) for vals in vals_list))
            if vals_list else ((), ())
        )

        new_recs = super(AccountAsset, self.with_context(mail_create_nolog=True)).create(asset_vals_list)

        # if original_value is passed in vals, make sure the right value is set (as a different original_value may have been computed by _compute_value())
        # creating the main asset variant implicitly and connect it to asset
        for asset, asset_vals, variant_vals in zip(new_recs, asset_vals_list, variant_vals_list):
            if 'original_value' in asset_vals:
                asset.original_value = asset_vals['original_value']
            if 'main_variant_id' not in asset_vals and not asset.main_variant_id:
                asset.main_variant_id = self.env['account.asset.variant'].create({
                        'asset_id': asset.id,
                        'account_depreciation_id': asset.import_account_depreciation_id,
                        'account_depreciation_expense_id': asset.import_account_depreciation_expense_id,
                        **variant_vals
                    }).id
        return new_recs

    def write(self, vals):
        asset_vals, variant_vals = self._split_assets_variants_vals(vals)
        result = super().write(asset_vals)
        if variant_vals:
            self.current_selected_variant_id.write(variant_vals)
        return result

    def _split_assets_variants_vals(self, vals):
        asset_fields = self._fields.keys()
        variant_fields = {name for name, field in self.env['account.asset.variant']._fields.items() if not field.readonly and not field.related} | {'analytic_distribution'}

        asset_vals = {k: vals[k] for k in vals if k in asset_fields}
        variant_vals = {k: vals[k] for k in vals if k in variant_fields}
        return asset_vals, variant_vals

    def _create_variants(self, depreciation_models, variant_vals=None):
        self.ensure_one()
        return self.env['account.asset.variant'].create([{
            'asset_id': self.id,
            'model_id': model.id,
            **(variant_vals or {}),
        } for model in depreciation_models])

    # -------------------------------------------------------------------------
    # PUBLIC ACTIONS
    # -------------------------------------------------------------------------
    def compute_depreciation_board(self, date=False):
        self.current_selected_variant_id.compute_depreciation_board(date=date)

    def action_open_linked_assets(self):
        action = self.linked_assets_ids.open_asset(['list', 'form'])
        action.get('context', {}).update({
            'from_linked_assets': 0,
        })
        return action

    def action_asset_modify(self):
        """ Returns an action opening the asset modification wizard for current variant
        """
        self.ensure_one()
        return self.current_selected_variant_id.action_asset_modify()

    def open_entries(self):
        return self.current_selected_variant_id.open_entries()

    def open_related_items(self):
        return {
            'name': self.env._('Journal Items'),
            'view_mode': 'list,pivot,graph,kanban',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.original_move_line_ids.ids)],
        }

    def open_increase(self):
        return self.current_selected_variant_id.open_increase()

    def open_variant_parent_id(self):
        return self.current_selected_variant_id.open_parent_id()

    def open_origin_asset(self):
        self.ensure_one()
        return self.origin_asset_id.open_asset(['form'])

    def open_derived_assets(self):
        self.ensure_one()
        return self.derived_asset_ids.open_asset(['list', 'form'])

    def validate(self):
        ref_track_fnames = [
            'model_id',
            'salvage_value',
            'original_move_line_ids',
        ]
        # Ensure all records are computed/saved before changing asset to running
        self.flush_recordset()
        for asset in self:
            if asset.is_main_variant:
                asset._track_add(
                    {asset.id: dict.fromkeys(ref_track_fnames)},
                    body=self.env._('Asset created'),
                )
                variants = asset.main_variant_id if asset.main_variant_parent_id else asset.variant_ids.filtered(lambda v: v.state == 'draft')
            else:
                if asset.main_variant_state != 'open':
                    raise UserError(self.env._("Cannot confirm current asset while main asset is not running"))
                variants = asset.current_selected_variant_id
            variants.validate()

            if asset.is_main_variant:
                for move_id in asset.original_move_line_ids.mapped('move_id'):
                    move_id.message_post(body=self.env._('An asset has been created for this move: %(link)s', link=asset._get_html_link()))

    def set_to_close(self, invoice_line_ids, date=None, message=None):
        self.ensure_one()
        return self.current_selected_variant_id.set_to_close(invoice_line_ids, date=date, message=message)

    def set_to_cancelled(self):
        for asset in self:
            if asset.is_main_variant:
                asset.variant_ids.set_to_cancelled()
                asset._message_log(body=self.env._(
                    "Asset cancelled.%(variant_message)s",
                    variant_message=self.env._(" All variants cancelled.") if asset.variant_count > 1 else "",
                ))
            else:
                asset.current_selected_variant_id.set_to_cancelled()
                asset._message_log(body=self.env._(
                    "Variant %(variant_name)s cancelled.",
                    variant_name=asset.current_selected_variant_id.name,
                ))

    def set_to_draft(self):
        for asset in self:
            if asset.is_main_variant:
                asset.variant_ids.set_to_draft()
                asset._message_log(body=self.env._(
                    "Asset reset to draft.%(variant_message)s",
                    variant_message=self.env._(" All variants set to draft.") if asset.variant_count > 1 else "",
                ))
            else:
                asset.current_selected_variant_id.set_to_draft()
                asset._message_log(body=self.env._(
                    "Variant %(variant_name)s reset to draft.",
                    variant_name=asset.current_selected_variant_id.name,
                ))

    def set_to_running(self):
        for asset in self:
            if asset.is_main_variant:
                asset.variant_ids.set_to_running()
                asset._message_log(body=self.env._(
                    "Asset set to running.%(variant_message)s",
                    variant_message=self.env._(" All variants reopened.") if asset.variant_count > 1 else "",
                ))
            else:
                asset.current_selected_variant_id.set_to_running()
                asset._message_log(body=self.env._(
                    "Variant %(variant_name)s set to running.",
                    variant_name=asset.current_selected_variant_id.name,
                ))

    def resume_after_pause(self):
        """ Sets an asset in 'paused' state back to 'open'.
        A Depreciation line is created automatically to remove  from the
        depreciation amount the proportion of time spent
        in pause in the current period.
        """
        self.ensure_one()
        return self.with_context(resume_after_pause=True).action_asset_modify()

    def open_asset(self, view_mode):
        if len(self) == 1:
            view_mode = ['form']
        views = [v for v in [(False, 'list'), (False, 'form')] if v[1] in view_mode]
        ctx = dict(self.env.context)
        ctx.pop('default_move_type', None)
        action = {
            'name': self.env._('Asset'),
            'view_mode': ','.join(view_mode),
            'type': 'ir.actions.act_window',
            'res_id': self.id if 'list' not in view_mode else False,
            'res_model': 'account.asset',
            'views': views,
            'domain': [('id', 'in', self.ids)],
            'context': ctx
        }
        return action

    def open_variants(self):
        self.ensure_one()
        if self.variant_count == 2:
            variant = self.variant_ids.filtered(lambda v: v != self.main_variant_id)
            ctx = dict(self.env.context)
            ctx['variant_id'] = variant.id
            return {
                'name': self.env._('Asset Variant'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.asset',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'current',
                'context': ctx,
            }
        return {
            'name': self.env._('Asset Variants'),
            'view_mode': 'list',
            'type': 'ir.actions.act_window',
            'res_model': 'account.asset.variant',
            'views': [(False, 'list')],
            'domain': [('asset_id', 'in', self.ids)],
        }

    def open_main_variant(self):
        ctx = dict(self.env.context)
        ctx['variant_id'] = self.main_variant_id.id
        return {
            'name': self.env._('Main Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.asset',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': ctx,
        }

    def action_depreciation_ledger(self):
        self.ensure_one()
        if not self.env['account.journal'].search_count([('journal_group_id', '!=', False)]):
            action = self.env.ref('account.action_account_journal_form')
            raise RedirectWarning(
                self.env._("At least one Journal must be linked to a Ledger in order to create an asset depreciation"),
                action.id,
                self.env._("Journals"),
            )
        if self.main_variant_id.method == 'no_depreciation':
            raise UserError(self.env._(
                "%(asset)s does not depreciate, so no ledger depreciation can be based on it.",
                asset=self.main_variant_id.name,
            ))

        new_wizard = self.env['depreciation.ledger.wizard'].create({
            'asset_id': self.id,
        })
        return {
            'name': self.env._('Depreciation Model'),
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_model': 'depreciation.ledger.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': new_wizard.id,
            'context': self.env.context,
        }

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _post_non_deductible_tax_value(self):
        # If the asset has a non-deductible tax, the value is posted in the chatter to explain why
        # the original value does not match the related purchase(s).
        if self.non_deductible_tax_value:
            currency = self.env.company.currency_id
            msg = self.env._('A non deductible tax value of %(tax_value)s was added to %(name)s\'s initial value of %(purchase_value)s',
                    tax_value=formatLang(self.env, self.non_deductible_tax_value, currency_obj=currency),
                    name=self.name,
                    purchase_value=formatLang(self.env, self.related_purchase_value, currency_obj=currency))
            self.message_post(body=msg)
