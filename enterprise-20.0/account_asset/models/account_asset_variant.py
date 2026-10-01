# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from math import copysign

import psycopg2
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, formatLang
from odoo.tools.date_utils import end_of

from odoo.addons.account.models.product import ACCOUNT_DOMAIN
from odoo.addons.account_asset.models.account_depreciation_model import (
    PRORATA_COMPUTATION_SELECTION,
)

DAYS_PER_MONTH = 30
DAYS_PER_YEAR = DAYS_PER_MONTH * 12


class AccountAssetVariant(models.Model):
    _name = 'account.asset.variant'
    _description = 'Asset Variant'

    # Depreciation Model fields
    model_id = fields.Many2one(
        comodel_name='account.depreciation.model',
        string="Depreciation Model",
        index=True,
        check_company=True,
        ondelete='restrict',
        compute='_compute_model_id', store=True, readonly=False, precompute=True,
        required=True,
    )
    method = fields.Selection(related='model_id.method')
    method_mode = fields.Selection(related='model_id.method_mode')
    method_number = fields.Float(related='model_id.method_number')
    method_period = fields.Selection(related='model_id.method_period')
    method_progress_factor = fields.Float(related='model_id.method_progress_factor')
    salvage_value_percent = fields.Float(related='model_id.salvage_value_percent')

    # Asset fields
    asset_id = fields.Many2one(comodel_name='account.asset', ondelete='cascade', required=True, index=True)
    active = fields.Boolean(related='asset_id.active')
    name = fields.Char(compute='_compute_name', readonly=True)
    company_id = fields.Many2one(related='asset_id.company_id')
    currency_id = fields.Many2one(related='asset_id.currency_id')
    account_asset_id = fields.Many2one(related='asset_id.account_asset_id')
    original_value = fields.Monetary(related='asset_id.original_value')
    acquisition_date = fields.Date(related='asset_id.acquisition_date')
    original_move_line_ids = fields.Many2many(related='asset_id.original_move_line_ids')
    analytic_distribution = fields.Json(related='asset_id.analytic_distribution')
    analytic_precision = fields.Integer(related='asset_id.analytic_precision')

    # Asset Variant fields
    state = fields.Selection(
        selection=[
            ('draft', "Draft"),
            ('open', "Running"),
            ('paused', "On Hold"),
            ('close', "Closed"),
            ('cancelled', "Cancelled")],
        string="Status",
        copy=False,
        default='draft',
        readonly=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string="Journal",
        check_company=True,
        domain="[('type', '=', 'general')]",
        compute='_compute_journal_id', store=True, readonly=True,
        index=True,
    )
    is_main_variant = fields.Boolean(compute='_compute_is_main_variant')

    prorata_computation_type = fields.Selection(
        selection=PRORATA_COMPUTATION_SELECTION,
        string="Computation",
        required=True,
        compute='_compute_prorata_computation_type',
        store=True, readonly=False, precompute=True,
    )
    prorata_date = fields.Date(
        string="Prorata Date",
        compute='_compute_prorata_date', store=True, readonly=False, precompute=True,
        help="Starting date of the period used in the prorata calculation of the first depreciation",
        required=True,
        copy=True,
    )
    paused_prorata_date = fields.Date(compute='_compute_paused_prorata_date')  # number of days to shift the computation of future deprecations
    account_depreciation_id = fields.Many2one(
        comodel_name='account.account',
        string="Depreciation Account",
        compute='_compute_depreciation_accounts', store=True, readonly=False,
        check_company=True,
        domain=ACCOUNT_DOMAIN,
        help="Account used in the depreciation entries, to decrease the asset value. Value obtained from Fixed Asset Account.",
    )
    account_depreciation_expense_id = fields.Many2one(
        comodel_name='account.account',
        string="Expense Account",
        compute='_compute_depreciation_accounts', store=True, readonly=False,
        check_company=True,
        domain=ACCOUNT_DOMAIN,
        help="Account used in the periodical entries, to record a part of the asset as expense. Value obtained from Fixed Asset Account.",
    )

    book_value = fields.Monetary(
        string="Book Value",
        compute='_compute_book_value', store=True, readonly=True,
        recursive=True,
        help="Sum of the depreciable value, the salvage value and the book value of all value increase items",
    )
    value_residual = fields.Monetary(string="Depreciable Value", compute='_compute_value_residual')
    salvage_value = fields.Monetary(
        string="Not Depreciable Value",
        help="It is the amount you plan to have that you cannot depreciate.",
        compute='_compute_salvage_value', store=True, readonly=False,
    )
    total_depreciable_value = fields.Monetary(compute='_compute_total_depreciable_value')
    gross_increase_value = fields.Monetary(string="Gross Increase Value", compute="_compute_gross_increase_value", compute_sudo=True)
    already_depreciated_amount_import = fields.Monetary(
        string="Depreciated at import",
        help="In case of an import from another software, you might need to use this field to have the right "
             "depreciation table report. This is the value that was already depreciated with entries not computed from this model",
    )

    disposal_date = fields.Date(readonly=False, compute='_compute_disposal_date', store=True)

    asset_lifetime_days = fields.Float(compute='_compute_lifetime_days', recursive=True)  # total number of days to consider for the computation of an asset depreciation board
    asset_paused_days = fields.Float(copy=False)

    net_gain_on_sale = fields.Monetary(string="Net gain on sale", help="Net value of gain or loss on sale of an asset", copy=False)

    parent_id = fields.Many2one('account.asset.variant', index=True, help="An asset has a parent when it is the result of gaining value")
    children_ids = fields.One2many('account.asset.variant', 'parent_id', help="The children are the gains in value of this asset")

    depreciation_move_ids = fields.One2many('account.move', 'asset_variant_id', string="Depreciation Lines")

    depreciation_entries_count = fields.Integer(compute='_compute_counts', string="# Posted Depreciation Entries")
    gross_increase_count = fields.Integer(compute='_compute_counts', string="# Gross Increases", help="Number of assets made to increase the value of the asset")
    total_depreciation_entries_count = fields.Integer(compute='_compute_counts', string="# Depreciation Entries", help="Number of depreciation entries (posted or not)")

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('asset_id.name', 'journal_id', 'is_main_variant')
    def _compute_name(self):
        for variant in self:
            if variant.is_main_variant:
                variant.name = variant.asset_id.name
            else:
                variant.name = self.env._("%(asset_name)s - %(journal_name)s",
                    asset_name=variant.asset_id.name,
                    journal_name=variant.journal_id.display_name,
                )

    @api.depends('asset_id.main_variant_id')
    def _compute_is_main_variant(self):
        for variant in self:
            variant.is_main_variant = variant == variant.asset_id.main_variant_id

    @api.depends('model_id', 'model_id.journal_id')
    def _compute_journal_id(self):
        for variant in self:
            variant.journal_id = variant.model_id._get_journal(variant.company_id)

    @api.depends('salvage_value', 'original_value')
    def _compute_total_depreciable_value(self):
        for variant in self:
            variant.total_depreciable_value = variant.original_value - variant.salvage_value

    @api.depends('original_value', 'model_id')
    def _compute_salvage_value(self):
        for variant in self:
            if not float_is_zero(variant.salvage_value_percent, 2):
                variant.salvage_value = variant.original_value * variant.salvage_value_percent

    @api.depends('depreciation_move_ids.date', 'state')
    def _compute_disposal_date(self):
        for variant in self:
            if variant.state == 'close':
                dates = variant.depreciation_move_ids.filtered('date').mapped('date')
                variant.disposal_date = dates and max(dates)
            else:
                variant.disposal_date = False

    @api.depends('account_asset_id', 'model_id', 'is_main_variant')
    def _compute_depreciation_accounts(self):
        for variant in self:
            variant.account_depreciation_id = variant.account_asset_id.asset_depreciation_account_id
            variant.account_depreciation_expense_id = variant.account_asset_id.asset_expense_account_id

    @api.depends('account_asset_id', 'account_asset_id.depreciation_model_id', 'original_move_line_ids')
    def _compute_model_id(self):
        for variant in self.filtered(lambda v: v.state == 'draft'):
            if len(variant.original_move_line_ids.depreciation_model_id) == 1:
                variant.model_id = variant.original_move_line_ids.depreciation_model_id
            else:
                variant.model_id = variant.account_asset_id.depreciation_model_id

    @api.depends('method_number', 'method_period', 'prorata_computation_type')
    def _compute_lifetime_days(self):
        for variant in self:
            if not variant.parent_id:
                if variant.prorata_computation_type == 'daily_computation':
                    months, days = variant._get_method_duration_months_and_days()
                    variant.asset_lifetime_days = (variant.prorata_date + relativedelta(months=months, days=days) - variant.prorata_date).days
                else:
                    variant.asset_lifetime_days = int(variant.method_period) * variant.method_number * DAYS_PER_MONTH
            else:
                # if it has a parent, we want the asset to only depreciate on the remaining days left of the parent
                if variant.prorata_computation_type == 'daily_computation':
                    parent_end_date = variant.parent_id.paused_prorata_date + relativedelta(days=int(variant.parent_id.asset_lifetime_days - 1))
                else:
                    parent_end_date = variant.parent_id.paused_prorata_date + relativedelta(
                        months=int(variant.parent_id.asset_lifetime_days / DAYS_PER_MONTH),
                        days=int(variant.parent_id.asset_lifetime_days % DAYS_PER_MONTH) - 1
                    )
                variant.asset_lifetime_days = variant._get_delta_days(variant.prorata_date, parent_end_date)

    @api.depends('model_id', 'model_id.prorata_computation_type')
    def _compute_prorata_computation_type(self):
        for variant in self:
            variant.prorata_computation_type = variant.model_id.prorata_computation_type or 'constant_periods'

    @api.depends('acquisition_date', 'company_id', 'prorata_computation_type')
    def _compute_prorata_date(self):
        for variant in self:
            if variant.prorata_computation_type == 'none' and variant.acquisition_date:
                fiscalyear_date = variant.company_id.compute_fiscalyear_dates(variant.acquisition_date).get('date_from')
                variant.prorata_date = fiscalyear_date
            else:
                variant.prorata_date = variant.acquisition_date

    @api.depends('prorata_date', 'prorata_computation_type', 'asset_paused_days')
    def _compute_paused_prorata_date(self):
        for variant in self:
            if variant.prorata_computation_type == 'daily_computation':
                variant.paused_prorata_date = variant.prorata_date + relativedelta(days=variant.asset_paused_days)
            else:
                variant.paused_prorata_date = variant.prorata_date + relativedelta(
                    months=int(variant.asset_paused_days / DAYS_PER_MONTH),
                    days=variant.asset_paused_days % DAYS_PER_MONTH
                )

    @api.depends(
        'original_value', 'salvage_value', 'already_depreciated_amount_import',
        'depreciation_move_ids.state',
        'depreciation_move_ids.depreciation_value',
        'depreciation_move_ids.reversal_move_ids'
    )
    def _compute_value_residual(self):
        grouped_moves = self.env['account.move']._read_group(
            domain=[('asset_variant_id', 'in', self.ids), ('state', '=', 'posted')],
            groupby=['asset_variant_id'],
            aggregates=['depreciation_value:sum'],
        )
        depreciation_sum_by_asset = {
            variant.id: total
            for variant, total in grouped_moves
        }
        for variant in self:
            variant_depreciation = depreciation_sum_by_asset.get(variant.id, 0.0)
            variant.value_residual = (
                variant.original_value
                - variant.salvage_value
                - variant.already_depreciated_amount_import
                - variant_depreciation
            )

    @api.depends(
        'value_residual', 'salvage_value', 'children_ids.book_value', 'state',
        'asset_id.main_variant_id.book_value', 'depreciation_move_ids.depreciation_value',
    )
    def _compute_book_value(self):
        for variant in self:
            variant.book_value = variant.value_residual + variant.salvage_value + sum(variant.children_ids.mapped('book_value'))
            if variant.state == 'close' and all(move.state == 'posted' for move in variant.depreciation_move_ids):
                variant.book_value -= variant.salvage_value

    @api.depends('children_ids.original_value')
    def _compute_gross_increase_value(self):
        for variant in self:
            variant.gross_increase_value = sum(variant.children_ids.mapped('original_value'))

    @api.depends('depreciation_move_ids.state', 'parent_id')
    def _compute_counts(self):
        depreciation_per_asset = {
            group.id: count
            for group, count in self.env['account.move']._read_group(
                domain=[
                    ('asset_variant_id', 'in', self.ids),
                    ('state', '=', 'posted'),
                ],
                groupby=['asset_variant_id'],
                aggregates=['__count'],
            )
        }
        for variant in self:
            variant.depreciation_entries_count = depreciation_per_asset.get(variant.id, 0)
            variant.total_depreciation_entries_count = len(variant.depreciation_move_ids)
            variant.gross_increase_count = len(variant.children_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('original_value', 'salvage_value', 'acquisition_date', 'method', 'method_progress_factor', 'method_period',
                 'method_number', 'prorata_computation_type', 'already_depreciated_amount_import', 'prorata_date')
    def _onchange_consistent_board(self):
        """ When changing the fields that should change the values of the entries, we unlink the entries, so the
         depreciation board is not inconsistent with the values of the asset"""
        self.write(
            {'depreciation_move_ids': [Command.set([])]}
        )

    # -------------------------------------------------------------------------
    # CONSTRAINT METHODS
    # -------------------------------------------------------------------------
    @api.constrains('state')
    def _check_state(self):
        for variant in self:
            if not variant.active and variant.state != 'close':
                raise UserError(self.env._('You cannot change the state of an archived asset'))

    @api.constrains('depreciation_move_ids')
    def _check_depreciations(self):
        for variant in self:
            if variant.state == 'open' and variant.depreciation_move_ids:
                last_move = variant.depreciation_move_ids.sorted(lambda x: (x.date, x.id))[-1]
                if variant.is_main_variant and not variant.currency_id.is_zero(last_move.asset_remaining_value):
                    raise UserError(self.env._("The remaining value on the last depreciation line must be 0"))
                if not variant.is_main_variant and not variant.currency_id.is_zero(last_move.asset_depreciated_value):
                    raise UserError(self.env._("The depreciated value on the last depreciation line for variant must be 0"))

    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------
    @api.ondelete(at_uninstall=True)
    def _unlink_if_draft(self):
        for variant in self:
            if variant.state in ['open', 'paused', 'close']:
                raise UserError(self.env._(
                    'You cannot delete an asset variant that is in %s state.',
                    dict(self._fields['state']._description_selection(self.env)).get(variant.state)
                ))

            posted_amount = len(variant.depreciation_move_ids.filtered(lambda x: x.state == 'posted'))
            if posted_amount > 0:
                raise UserError(self.env._('You cannot delete an asset linked to posted entries.'
                                  '\nYou should either confirm the asset, then, sell or dispose of it,'
                                  ' or cancel the linked journal entries.'))

    def unlink(self):
        assets_to_delete = self.filtered('is_main_variant').asset_id
        # Deleting these assets cascades (ondelete='cascade') to all their variants at the
        # database level, which bypasses this model's unlink()/_unlink_if_draft check for any
        # variant not explicitly part of `self`. Validate them here first so a
        # posted/non-draft sibling still blocks the deletion.
        assets_to_delete.variant_ids._unlink_if_draft()
        variants_to_delete = self.filtered(lambda v: v.asset_id not in assets_to_delete)
        assets_to_delete.with_context(delete_asset=True).unlink()
        return super(AccountAssetVariant, variants_to_delete).unlink()

    def write(self, vals):
        result = super().write(vals)
        if 'analytic_distribution' in vals:
            # Only draft entries to avoid recreating all the analytic items
            self.depreciation_move_ids.filtered(lambda m: m.state == 'draft').line_ids.analytic_distribution = vals['analytic_distribution']
        return result

    # -------------------------------------------------------------------------
    # BOARD COMPUTATION
    # -------------------------------------------------------------------------
    def _get_linear_amount(self, days_before_period, days_until_period_end, total_depreciable_value):

        amount_expected_previous_period = total_depreciable_value * days_before_period / self.asset_lifetime_days
        amount_after_expected = total_depreciable_value * days_until_period_end / self.asset_lifetime_days
        number_days_for_period = days_until_period_end - days_before_period
        # In case of a decrease, we need to lower the amount of the depreciation with the amount of the decrease
        # spread over the remaining lifetime
        amount_of_decrease_spread_over_period = [
            number_days_for_period * mv.depreciation_value / (self.asset_lifetime_days - self._get_delta_days(self.paused_prorata_date, mv.asset_depreciation_beginning_date))
            for mv in self.depreciation_move_ids.filtered(lambda mv: mv.asset_value_change)
        ]
        computed_linear_amount = self.currency_id.round(amount_after_expected - self.currency_id.round(amount_expected_previous_period) - sum(amount_of_decrease_spread_over_period))
        return computed_linear_amount

    def _compute_board_amount(self, residual_amount, period_start_date, period_end_date, days_already_depreciated,
                              days_left_to_depreciated, residual_declining, start_yearly_period=None, total_lifetime_left=None,
                              residual_at_compute=None, start_recompute_date=None):

        def _get_max_between_linear_and_degressive(linear_amount):
            """
            Compute the degressive amount that could be depreciated and returns the biggest between it and linear_amount
            The degressive amount corresponds to the difference between what should have been depreciated at the end of
            the period and the residual_amount (to deal with rounding issues at the end of each month)
            """
            fiscalyear_dates = self.company_id.compute_fiscalyear_dates(period_end_date)
            days_in_fiscalyear = self._get_delta_days(fiscalyear_dates['date_from'], fiscalyear_dates['date_to'])

            degressive_total_value = residual_declining * (1 - self.method_progress_factor * self._get_delta_days(start_yearly_period, period_end_date) / days_in_fiscalyear)
            degressive_amount = residual_amount - degressive_total_value
            return self._degressive_linear_amount(residual_amount, degressive_amount, linear_amount)

        if float_is_zero(self.asset_lifetime_days, 2) or float_is_zero(residual_amount, 2):
            return 0, 0

        days_until_period_end = self._get_delta_days(self.paused_prorata_date, period_end_date)
        days_before_period = self._get_delta_days(self.paused_prorata_date, period_start_date + relativedelta(days=-1))
        days_before_period = max(days_before_period, 0)  # if disposed before the beginning of the asset for example
        number_days = days_until_period_end - days_before_period

        # The amount to depreciate are computed by computing how much the asset should be depreciated at the end of the
        # period minus how much difference it is actually depreciated. It is done that way to avoid having the last move to take
        # every single small difference that could appear over the time with the classic computation method.
        if self.method == 'linear':
            if total_lifetime_left and float_compare(total_lifetime_left, 0, 2) > 0:
                computed_linear_amount = residual_amount - residual_at_compute * (1 - self._get_delta_days(start_recompute_date, period_end_date) / total_lifetime_left)
            else:
                computed_linear_amount = self._get_linear_amount(days_before_period, days_until_period_end, self.total_depreciable_value)
            amount = min(computed_linear_amount, residual_amount, key=abs)
        elif self.method == 'degressive':
            # Linear amount
            # We first calculate the total linear amount for the period left from the beginning of the year
            # to get the linear amount for the period in order to avoid big delta at the end of the period
            days_left_from_beginning_of_year = self._get_delta_days(start_yearly_period, period_start_date - relativedelta(days=1)) + days_left_to_depreciated
            expected_remaining_value_with_linear = residual_declining - residual_declining * self._get_delta_days(start_yearly_period, period_end_date) / days_left_from_beginning_of_year
            linear_amount = residual_amount - expected_remaining_value_with_linear

            amount = _get_max_between_linear_and_degressive(linear_amount)
        elif self.method == 'degressive_then_linear':
            if not self.parent_id:
                linear_amount = self._get_linear_amount(days_before_period, days_until_period_end, self.total_depreciable_value)
            else:
                # we want to know the amount before the reeval for the parent so the child can follow the same curve,
                # so it transitions from degressive to linear at the same moment
                parent_moves = self.parent_id.depreciation_move_ids.filtered(lambda mv: mv.date <= self.prorata_date).sorted(key=lambda mv: (mv.date, mv.id))
                parent_cumulative_depreciation = parent_moves[-1].asset_depreciated_value if parent_moves else self.parent_id.already_depreciated_amount_import
                parent_depreciable_value = parent_moves[-1].asset_remaining_value if parent_moves else self.parent_id.total_depreciable_value
                if self.currency_id.is_zero(parent_depreciable_value):
                    linear_amount = self._get_linear_amount(days_before_period, days_until_period_end, self.total_depreciable_value)
                else:
                    # To have the same curve as the parent, we need to have the equivalent amount before the reeval.
                    # The child's depreciable value corresponds to the amount that is left to depreciate for the parent.
                    # So, we use the proportion between them to compute the equivalent child's total to depreciate.
                    # We use it then with the duration of the parent to compute the depreciation amount
                    depreciable_value = self.total_depreciable_value * (1 + parent_cumulative_depreciation / parent_depreciable_value)
                    linear_amount = self._get_linear_amount(days_before_period, days_until_period_end, depreciable_value) * self.asset_lifetime_days / self.parent_id.asset_lifetime_days

            amount = _get_max_between_linear_and_degressive(linear_amount)

        amount = max(amount, 0) if self.currency_id.compare_amounts(residual_amount, 0) > 0 else min(amount, 0)
        amount = self._get_depreciation_amount_end_of_lifetime(residual_amount, amount, days_until_period_end)

        return number_days, self.currency_id.round(amount)

    def compute_depreciation_board(self, date=False):
        # Need to unlink draft moves before adding new ones because if we create new moves before, it will cause an error
        self.depreciation_move_ids.filtered(lambda mv: mv.state == 'draft' and (mv.date >= date if date else True)).unlink()

        new_depreciation_moves_data = []
        for variant in self:
            new_depreciation_moves_data.extend(variant._recompute_board(date))

        new_depreciation_moves = self.env['account.move'].create(new_depreciation_moves_data)
        new_depreciation_moves_to_post = new_depreciation_moves.filtered(lambda move: move.asset_variant_id.state == 'open')
        # In case of the asset is in running mode, we post in the past and set to auto post move in the future
        new_depreciation_moves_to_post._post()

    def _recompute_board(self, start_depreciation_date=False):
        self.ensure_one()
        # All depreciation moves that are posted
        posted_depreciation_move_ids = self.depreciation_move_ids.filtered(
            lambda mv: mv.state == 'posted' and not mv.asset_value_change
        ).sorted(key=lambda mv: (mv.date, mv.id))

        imported_amount = self.already_depreciated_amount_import
        residual_amount = self.value_residual - sum(self.depreciation_move_ids.filtered(lambda mv: mv.state == 'draft').mapped('depreciation_value'))
        if not posted_depreciation_move_ids:
            residual_amount += imported_amount
        residual_declining = residual_at_compute = residual_amount
        # start_yearly_period is needed in the 'degressive' and 'degressive_then_linear' methods to compute the amount when the period is monthly
        start_recompute_date = start_depreciation_date = start_yearly_period = start_depreciation_date or self.paused_prorata_date

        last_day_asset = self._get_last_day_asset()
        final_depreciation_date = self._get_end_period_date(last_day_asset)
        total_lifetime_left = self._get_delta_days(start_depreciation_date, last_day_asset)

        depreciation_move_values = []
        if not float_is_zero(self.value_residual, precision_rounding=self.currency_id.rounding):
            while not self.currency_id.is_zero(residual_amount) and start_depreciation_date < final_depreciation_date:
                period_end_depreciation_date = self._get_end_period_date(start_depreciation_date)
                period_end_fiscalyear_date = self.company_id.compute_fiscalyear_dates(period_end_depreciation_date).get('date_to')
                lifetime_left = self._get_delta_days(start_depreciation_date, last_day_asset)

                days, amount = self._compute_board_amount(residual_amount, start_depreciation_date, period_end_depreciation_date, False, lifetime_left, residual_declining, start_yearly_period, total_lifetime_left, residual_at_compute, start_recompute_date)
                residual_amount -= amount

                if not posted_depreciation_move_ids:
                    # self.already_depreciated_amount_import management.
                    # Subtracts the imported amount from the first depreciation moves until we reach it
                    # (might skip several depreciation entries)
                    if abs(imported_amount) <= abs(amount):
                        amount -= imported_amount
                        imported_amount = 0
                    else:
                        imported_amount -= amount
                        amount = 0

                if self.method == 'degressive_then_linear' and final_depreciation_date < period_end_depreciation_date:
                    period_end_depreciation_date = final_depreciation_date

                if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    # For deferred revenues, we should invert the amounts.
                    depreciation_move_values.append(self.env['account.move']._prepare_move_for_asset_depreciation(
                        amount=amount,
                        asset_variant=self,
                        depreciation_beginning_date=start_depreciation_date,
                        date=period_end_depreciation_date,
                        asset_number_days=days,
                    ))

                if period_end_depreciation_date == period_end_fiscalyear_date:
                    start_yearly_period = self.company_id.compute_fiscalyear_dates(period_end_depreciation_date + relativedelta(days=1)).get('date_from')
                    residual_declining = residual_amount

                start_depreciation_date = period_end_depreciation_date + relativedelta(days=1)

        return depreciation_move_values

    def _get_end_period_date(self, start_depreciation_date):
        """Get the end of the period in which the depreciation is posted.

        Can be the end of the month if the asset is depreciated monthly, or the end of the fiscal year is it is depreciated yearly.
        """
        self.ensure_one()
        fiscalyear_date = self.company_id.compute_fiscalyear_dates(start_depreciation_date).get('date_to')
        period_end_depreciation_date = fiscalyear_date if start_depreciation_date <= fiscalyear_date else fiscalyear_date + relativedelta(years=1)

        if self.method_period == '1':  # If method period is set to monthly computation
            max_day_in_month = end_of(datetime.date(start_depreciation_date.year, start_depreciation_date.month, 1), 'month').day
            period_end_depreciation_date = min(start_depreciation_date.replace(day=max_day_in_month), period_end_depreciation_date)
        return period_end_depreciation_date

    def _get_delta_days(self, start_date, end_date):
        """Compute how many days there are between 2 dates.

        The computation is different if the asset is in daily_computation or not.
        """
        self.ensure_one()
        if self.prorata_computation_type == 'daily_computation':
            # Compute how many days there are between 2 dates using a daily_computation method
            return (end_date - start_date).days + 1
        else:
            # Compute how many days there are between 2 dates counting 30 days per month
            # Get how many days there are in the start date month
            start_date_days_month = end_of(start_date, 'month').day
            # Get how many days there are in the start date month (e.g: June 20th: (30 * (30 - 20 + 1)) / 30 = 11)
            start_prorata = (start_date_days_month - start_date.day + 1) / start_date_days_month
            # Get how many days there are in the end date month (e.g: You're the August 14th: (14 * 30) / 31 = 13.548387096774194)
            end_prorata = end_date.day / end_of(end_date, 'month').day
            # Compute how many days there are between these 2 dates
            # e.g: 13.548387096774194 + 11 + 360 * (2020 - 2020) + 30 * (8 - 6 - 1) = 24.548387096774194 + 360 * 0 + 30 * 1 = 54.548387096774194 day
            return sum((
                start_prorata * DAYS_PER_MONTH,
                end_prorata * DAYS_PER_MONTH,
                (end_date.year - start_date.year) * DAYS_PER_YEAR,
                (end_date.month - start_date.month - 1) * DAYS_PER_MONTH
            ))

    def _get_last_day_asset(self):
        this = self.parent_id if self.parent_id else self
        months, days = this._get_method_duration_months_and_days()
        return this.paused_prorata_date + relativedelta(months=months, days=days - 1)

    # -------------------------------------------------------------------------
    # PUBLIC ACTIONS
    # -------------------------------------------------------------------------

    def action_asset_modify(self):
        """ Returns an action opening the asset modification wizard.
        """
        self.ensure_one()
        new_wizard = self.env['asset.modify'].create({
            'asset_variant_id': self.id,
            'modify_action': 'resume' if self.env.context.get('resume_after_pause') else 'dispose',
        })
        return {
            'name': self.env._('Modify Asset'),
            'view_mode': 'form',
            'res_model': 'asset.modify',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': new_wizard.id,
            'context': self.env.context,
        }

    def open_entries(self):
        return {
            'name': self.env._('Journal Entries'),
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'search_view_id': [self.env.ref('account.view_account_move_filter').id, 'search'],
            'views': [(self.env.ref('account.view_move_tree').id, 'list'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.depreciation_move_ids.ids)],
            'context': {**self.env.context, 'create': False},
        }

    def open_increase(self):
        result = {
            'name': self.env._('Gross Increase'),
            'view_mode': 'list,form',
            'res_model': 'account.asset',
            'context': {**self.env.context, 'create': False, 'variant_id': self.children_ids.id},
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.children_ids.asset_id.ids)],
            'views': [(False, 'list'), (False, 'form')],
        }
        if len(self.children_ids) == 1:
            result['views'] = [(False, 'form')]
            result['res_id'] = self.children_ids.asset_id.id
        return result

    def open_parent_id(self):
        ctx = dict(self.env.context)
        ctx['variant_id'] = self.parent_id.id
        result = {
            'name': self.env._('Parent Asset'),
            'view_mode': 'form',
            'res_model': 'account.asset',
            'type': 'ir.actions.act_window',
            'res_id': self.parent_id.asset_id.id,
            'views': [(False, 'form')],
            'context': ctx,
        }
        return result

    def action_open_variant_details(self):
        self.ensure_one()
        ctx = dict(self.env.context)
        ctx['variant_id'] = self.id
        return {
            'name': self.env._('Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.asset',
            'view_mode': 'form',
            'res_id': self.asset_id.id,
            'target': 'current',
            'context': ctx,
        }

    def validate(self):
        self.write({'state': 'open'})
        for asset, variants in self.grouped('asset_id').items():
            if len(variants) == 1:
                asset._message_log(body=self.env._(
                    "%(variant)s confirmed with %(model)s%(journal_message)s",
                    variant=self.env._("Asset") if variants == asset.main_variant_id else self.env._("Variant"),
                    model=variants.model_id._get_html_link(),
                    journal_message=self.env._(" in journal %s", variants.journal_id._get_html_link()),
                ))
            else:
                variant_lines = Markup('<br>').join(
                    self.env._(
                        "- %(model)s%(journal_message)s",
                        model=v.model_id._get_html_link(),
                        journal_message=self.env._(" in journal %s", v.journal_id._get_html_link()),
                    )
                    for v in variants
                )
                asset._message_log(body=self.env._("Asset confirmed with:") + Markup('<br>') + variant_lines)

        for variant in self:
            try:
                if not variant.depreciation_move_ids and variant.method != 'no_depreciation':
                    variant.compute_depreciation_board()
                variant._check_depreciations()
                variant.depreciation_move_ids.filtered(lambda move: move.state != 'posted')._post()
            except psycopg2.errors.CheckViolation:
                raise ValidationError(self.env._("At least one asset (%s) couldn't be set as running because it lacks any required information", variant.name))

    def set_to_close(self, invoice_line_ids, date=None, message=None):
        self.ensure_one()

        disposal_date = date or fields.Date.context_today(self)
        if disposal_date <= self.company_id._get_user_fiscal_lock_date(self.journal_id):
            raise UserError(self.env._("You cannot dispose of an asset before the lock date."))
        if invoice_line_ids and self.children_ids.filtered(lambda a: a.state in ('draft', 'open') or a.value_residual > 0):
            raise UserError(self.env._("You cannot automate the journal entry for an asset that has a running gross increase. Please use 'Dispose' on the increase(s)."))
        full_variant = (self + self.children_ids).filtered(lambda variant: variant.state not in ('close', 'cancelled'))
        full_variant.state = 'close'
        move_ids = full_variant._get_disposal_moves([invoice_line_ids] * len(full_variant), disposal_date)

        if invoice_line_ids:
            invoice_moves = invoice_line_ids.move_id
            invoice_links = Markup(', ').join(move._get_html_link() for move in invoice_moves)
            variant_body = self.env._(
                "Asset sold. %(message)s See %(invoice_links)s",
                message=message or "",
                invoice_links=invoice_links,
            )
            invoice_body = self.env._("Asset sold: %s", self.asset_id._get_html_link())
            invoice_moves._message_log_batch(bodies={invoice.id: invoice_body for invoice in invoice_moves})
        else:
            variant_body = self.env._(
                "Asset disposed. %(message)s",
                message=message or "",
            )
        full_assets = full_variant.asset_id
        full_assets._message_log_batch(bodies={asset.id: variant_body for asset in full_assets})

        selling_price = abs(sum(invoice_line.balance for invoice_line in invoice_line_ids))
        self.net_gain_on_sale = self.currency_id.round(selling_price - self.book_value)

        if move_ids:
            name = self.env._('Disposal Move')
            view_mode = 'form'
            if len(move_ids) > 1:
                name = self.env._('Disposal Moves')
                view_mode = 'list,form'
            return {
                'name': name,
                'view_mode': view_mode,
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': move_ids[0],
                'domain': [('id', 'in', move_ids)]
            }

    def set_to_cancelled(self):
        for variant in self:
            posted_moves = variant.depreciation_move_ids.filtered(lambda m: (
                not m.reversal_move_ids
                and not m.reversed_entry_id
                and m.state == 'posted'
            ))
            if posted_moves:
                depreciation_change = sum(posted_moves.line_ids.mapped(
                    lambda l: l.debit if l.account_id == variant.account_depreciation_expense_id else 0.0
                ))
                acc_depreciation_change = sum(posted_moves.line_ids.mapped(
                    lambda l: l.credit if l.account_id == variant.account_depreciation_id else 0.0
                ))
                entries = {
                    m.id: f'{m.ref} - {m.date} - '
                          f'{formatLang(self.env, m.depreciation_value, currency_obj=m.currency_id)} - '
                          f'{m.name}'
                    for m in posted_moves.sorted('date')
                }
                variant._cancel_future_moves(datetime.date.min)
                reversed_moves = posted_moves.exists()
                msg = (
                    self.env._("%(variant_name)s Cancellation:", variant_name=variant.name)
                    + Markup('<br>')
                    + self.env._(
                            "The account %(exp_acc)s has been credited by %(exp_delta)s, "
                            "while the account %(dep_acc)s has been debited by %(dep_delta)s.\n"
                            "This corresponds to %(move_count)s adjusted %(word)s.",
                            exp_acc=variant.account_depreciation_expense_id.display_name,
                            exp_delta=formatLang(self.env, depreciation_change, currency_obj=variant.currency_id),
                            dep_acc=variant.account_depreciation_id.display_name,
                            dep_delta=formatLang(self.env, acc_depreciation_change, currency_obj=variant.currency_id),
                            move_count=len(posted_moves),
                            word=self.env._('entries') if len(posted_moves) > 1 else self.env._('entry'),
                        )
                    )
                cancelled_move_count = len(posted_moves) - len(reversed_moves)
                if cancelled_move_count:
                    msg += Markup('<br>') + \
                        self.env._(
                            "Entries cancelled: %(cancelled_move_count)s",
                            cancelled_move_count=cancelled_move_count,
                        )
                    msg += Markup('<br>') + Markup('<br>').join([move_info for move_id, move_info in entries.items() if move_id not in reversed_moves.ids])
                if reversed_moves:
                    msg += Markup('<br>') + \
                        self.env._(
                            "Entries reversed: %(reversed_move_count)s",
                            reversed_move_count=len(reversed_moves),
                        )
                    msg += Markup('<br>') + Markup('<br>').join([move_info for move_id, move_info in entries.items() if move_id in reversed_moves.ids])
                variant.asset_id._message_log(body=msg)
            variant.depreciation_move_ids.filtered(lambda m: m.state == 'draft').with_context(force_delete=True).unlink()
            variant.asset_paused_days = 0
            variant.write({'state': 'cancelled'})

    def set_to_draft(self):
        self.filtered(lambda a: a.state != 'cancelled').set_to_cancelled()
        self.write({'state': 'draft'})

    def set_to_running(self):
        for variant in self:
            if variant.depreciation_move_ids and max(variant.depreciation_move_ids, key=lambda m: (m.date, m.id)).asset_remaining_value != 0:
                self.env['asset.modify'].create({'asset_variant_id': variant.id, 'name': self.env._('Reset to running')}).modify()
        self.write({
            'state': 'open',
            'net_gain_on_sale': 0
        })

    def resume_after_pause(self):
        """ Sets an asset in 'paused' state back to 'open'.
        A Depreciation line is created automatically to remove  from the
        depreciation amount the proportion of time spent
        in pause in the current period.
        """
        self.ensure_one()
        return self.with_context(resume_after_pause=True).action_asset_modify()

    def pause(self, pause_date, message=None):
        """ Sets an 'open' asset in 'paused' state, generating first a depreciation
        line corresponding to the ratio of time spent within the current depreciation
        period before putting the asset in pause. This line and all the previous
        unposted ones are then posted.
        """
        self.ensure_one()
        self._create_move_before_date(pause_date)
        self.write({'state': 'paused'})

    def open_asset(self, view_mode):
        if len(self) == 1:
            view_mode = ['form']
        views = [v for v in [(False, 'list'), (False, 'form')] if v[1] in view_mode]
        ctx = dict(self.env.context)
        ctx.pop('default_move_type', None)
        ctx['variant_id'] = self.id
        action = {
            'name': self.env._('Asset'),
            'view_mode': ','.join(view_mode),
            'type': 'ir.actions.act_window',
            'res_id': self.asset_id.id if 'list' not in view_mode else False,
            'res_model': 'account.asset',
            'views': views,
            'domain': [('id', 'in', self.asset_id.ids)],
            'context': ctx
        }
        return action

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _create_move_before_date(self, date):
        """Cancel all the moves after the given date and replace them by a new one.

        The new depreciation/move is depreciating the residual value.
        """
        self.env['account.move'].create(self._recompute_move_before_date(date))._post()

    def _recompute_move_before_date(self, date):
        """Cancel the moves after the given date and give the values of the one replacing them.

        :param date: the date the new depreciation move is posted on
        :return: a list of `account.move` values, empty when there is nothing left to depreciate
        """
        self.ensure_one()
        all_move_dates_before_date = (self.depreciation_move_ids.filtered(
            lambda x:
            x.date <= date
            and not x.reversal_move_ids
            and not x.reversed_entry_id
            and x.state == 'posted'
        ).sorted('date')).mapped('date')

        beginning_fiscal_year = self.company_id.compute_fiscalyear_dates(date).get('date_from') if self.method != 'linear' else False
        # For degressive methods, the fiscal year start must not precede the asset's
        # prorata date, otherwise day-count computations produce incorrect results.
        if beginning_fiscal_year:
            beginning_fiscal_year = max(beginning_fiscal_year, self.paused_prorata_date)
        first_fiscalyear_move = self.env['account.move']
        if all_move_dates_before_date:
            last_move_date_not_reversed = max(all_move_dates_before_date)
            # We don't know when begins the period that the move is supposed to cover
            # So, we use the earliest beginning of a move that comes after the last move not cancelled
            future_moves_beginning_date = self.depreciation_move_ids.filtered(
                lambda m: m.date > last_move_date_not_reversed and (
                    not m.reversal_move_ids and not m.reversed_entry_id and m.state == 'posted'
                    or m.state == 'draft'
                )
            ).mapped('asset_depreciation_beginning_date')
            beginning_depreciation_date = min(future_moves_beginning_date) if future_moves_beginning_date else self.paused_prorata_date

            if self.method != 'linear':
                # In degressive and degressive_then_linear, we need to find the first move of the fiscal year that comes after the last move not cancelled
                # in order to correctly compute the moves just before and after the pause date
                first_moves = self.depreciation_move_ids.filtered(
                    lambda m: m.asset_depreciation_beginning_date >= beginning_fiscal_year and (
                        not m.reversal_move_ids and not m.reversed_entry_id and m.state == 'posted'
                        or m.state == 'draft'
                    )
                ).sorted(lambda m: (m.asset_depreciation_beginning_date, m.id))
                first_fiscalyear_move = first_moves[:1] or first_fiscalyear_move
        else:
            beginning_depreciation_date = self.paused_prorata_date

        residual_declining = first_fiscalyear_move.asset_remaining_value + first_fiscalyear_move.depreciation_value
        self._cancel_future_moves(date)

        own_value_residual = self._get_own_value_residual()
        imported_amount = self.already_depreciated_amount_import if not all_move_dates_before_date else 0
        value_residual = own_value_residual + self.already_depreciated_amount_import if not all_move_dates_before_date else own_value_residual
        residual_declining = residual_declining or value_residual

        last_day_asset = self._get_last_day_asset()
        lifetime_left = self._get_delta_days(beginning_depreciation_date, last_day_asset)
        days_depreciated, amount = self._compute_board_amount(own_value_residual, beginning_depreciation_date, date, False, lifetime_left, residual_declining, beginning_fiscal_year, lifetime_left, value_residual, beginning_depreciation_date)

        if abs(imported_amount) <= abs(amount):
            amount -= imported_amount

        move_values = []
        if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            move_values.append(self.env['account.move']._prepare_move_for_asset_depreciation(
                amount=amount,
                asset_variant=self,
                depreciation_beginning_date=beginning_depreciation_date,
                date=date,
                asset_number_days=days_depreciated,
            ))
        return move_values

    def _cancel_future_moves(self, date):
        """Cancel all the depreciation entries after the date given as parameter.

        When possible, it will reset those to draft before unlinking them, reverse them otherwise.

        :param date: date after which the moves are deleted/reversed
        """
        for variant in self:
            obsolete_moves = variant.depreciation_move_ids.filtered(lambda m: m.state == 'draft' or (
                not m.reversal_move_ids
                and not m.reversed_entry_id
                and m.state == 'posted'
                and m.date > date
            ))
            obsolete_moves._unlink_or_reverse()

    def _get_disposal_moves(self, invoice_lines_list, disposal_date):
        """Create the move for the disposal of an asset.

        :param invoice_lines_list: list of recordset of `account.move.line`
            Each element of the list corresponds to one record of `self`
            These lines are used to generate the disposal move
        :param disposal_date: the date of the disposal
        """
        def get_line(name, variant, amount, account, is_sale):
            return (0, 0, {
                'name': name,
                'account_id': account.id,
                'balance': -amount,
                'analytic_distribution': analytic_distribution,
                'currency_id': variant.currency_id.id,
                'amount_currency': -variant.company_id.currency_id._convert(
                    from_amount=amount,
                    to_currency=variant.currency_id,
                    company=variant.company_id,
                    date=disposal_date,
                ),
                'is_storno': variant.company_id.account_storno and is_sale and (
                    account not in (variant.company_id.gain_account_id, variant.company_id.loss_account_id)
                )
            })

        move_ids = []
        assert len(self) == len(invoice_lines_list)
        for variant, invoice_line_ids in zip(self, invoice_lines_list):
            variant._create_move_before_date(disposal_date)

            analytic_distribution = variant.analytic_distribution

            line_datas = variant._get_disposal_line_datas(invoice_line_ids, disposal_date)
            if not line_datas:
                continue
            name = self.env._("%(asset)s: Disposal", asset=variant.name) if not invoice_line_ids else self.env._("%(asset)s: Sale", asset=variant.name)
            vals = {
                'asset_variant_id': variant.id,
                'ref': name,
                'asset_depreciation_beginning_date': disposal_date,
                'date': disposal_date,
                'journal_id': variant.journal_id.id,
                'move_type': 'entry',
                'asset_move_type': 'disposal' if not invoice_line_ids else 'sale',
                'line_ids': [get_line(name, variant, amount, account, invoice_line_ids) for amount, account in line_datas if account and amount],
            }
            variant.write({'depreciation_move_ids': [(0, 0, vals)]})
            move_ids += self.env['account.move'].search([('asset_variant_id', '=', variant.id), ('state', '=', 'draft')]).ids

        return move_ids

    def _get_disposal_line_datas(self, invoice_line_ids, disposal_date):
        """Give the (amount, account) pairs the disposal entry is made of.

        The amounts are the values leaving the books; `_get_disposal_moves` writes them
        with the opposite sign.

        :param invoice_line_ids: recordset of `account.move.line` the asset is sold with
        :param disposal_date: the date of the disposal
        """
        self.ensure_one()
        depreciated_amount = self._get_depreciated_amount_at_date(disposal_date)

        initial_amount = self.original_value
        initial_account = self.original_move_line_ids.account_id if len(self.original_move_line_ids.account_id) == 1 else self.account_asset_id
        depreciated_amount = self.currency_id.round(copysign(depreciated_amount, -initial_amount))

        dict_invoice = {}
        invoice_amount = 0
        for invoice_line in invoice_line_ids:
            dict_invoice[invoice_line.account_id] = copysign(invoice_line.balance, -initial_amount) + dict_invoice.get(invoice_line.account_id, 0)
            invoice_amount += copysign(invoice_line.balance, -initial_amount)
        list_accounts = [(amount, account) for account, amount in dict_invoice.items()]
        difference = -initial_amount - depreciated_amount - invoice_amount
        difference_account = self.company_id.gain_account_id if difference > 0 else self.company_id.loss_account_id
        return [(initial_amount, initial_account), (depreciated_amount, self.account_depreciation_id)] + list_accounts + [(difference, difference_account)]

    def _get_depreciated_amount_at_date(self, date):
        """Give the amount this variant has already depreciated on `date`."""
        self.ensure_one()
        return sum(
            self.depreciation_move_ids.filtered(lambda mv: mv.date <= date).mapped('depreciation_value')
        ) + self.already_depreciated_amount_import

    def _degressive_linear_amount(self, residual_amount, degressive_amount, linear_amount):
        if self.currency_id.compare_amounts(residual_amount, 0) > 0:
            return max(degressive_amount, linear_amount)
        else:
            return min(degressive_amount, linear_amount)

    def _get_depreciation_amount_end_of_lifetime(self, residual_amount, amount, days_until_period_end):
        if abs(residual_amount) < abs(amount) or days_until_period_end >= self.asset_lifetime_days:
            # If the residual amount is less than the computed amount, we keep the residual amount
            # If total_days is greater or equals to asset lifetime days, it should mean that
            # the asset will finish in this period and the value for this period is equal to the residual amount.
            amount = residual_amount
        return amount

    def _get_own_value_residual(self):
        """Give the value this variant still has to depreciate on its own books."""
        self.ensure_one()
        return self.value_residual

    def _get_own_book_value(self, date=None):
        self.ensure_one()
        return (self._get_residual_value_at_date(date) if date else self.value_residual) + self.salvage_value

    def _get_residual_value_at_date(self, date):
        """ Computes the theoretical value of the asset at a specific date.

            :param date: the date at which we want the asset's value
            :return: the value at date of the asset without taking reverse entries into account (as it should be in a "normal" flow of the asset)
        """
        current_and_previous_depreciation = self.depreciation_move_ids.filtered(
            lambda mv:
            mv.asset_depreciation_beginning_date < date
            and not mv.reversed_entry_id
        ).sorted('asset_depreciation_beginning_date', reverse=True)
        if not current_and_previous_depreciation:
            return 0

        if len(current_and_previous_depreciation) > 1:
            previous_value_residual = current_and_previous_depreciation[1].asset_remaining_value
        else:
            # If there is only one depreciation, we take the original depreciation value
            previous_value_residual = self.original_value - self.salvage_value - self.already_depreciated_amount_import

        # We compare the amount_residuals of the depreciations before and during the given date.
        # It applies the ratio of the period (to-given-date / total-days-of-the-period) to the amount of the depreciation.
        cur_depr_end_date = self._get_end_period_date(date)
        current_depreciation = current_and_previous_depreciation[0]
        cur_depr_beg_date = current_depreciation.asset_depreciation_beginning_date

        rate = self._get_delta_days(cur_depr_beg_date, date) / self._get_delta_days(cur_depr_beg_date, cur_depr_end_date)
        lost_value_at_date = (previous_value_residual - current_depreciation.asset_remaining_value) * rate
        residual_value_at_date = self.currency_id.round(previous_value_residual - lost_value_at_date)
        if self.currency_id.compare_amounts(self.original_value, 0) > 0:
            return max(residual_value_at_date, 0)
        else:
            return min(residual_value_at_date, 0)

    def _get_method_duration_months_and_days(self):
        self.ensure_one()

        total_months = int(self.method_period) * self.method_number
        whole_months = int(total_months)
        extra_days = round((total_months - whole_months) * DAYS_PER_MONTH)

        return whole_months, extra_days
