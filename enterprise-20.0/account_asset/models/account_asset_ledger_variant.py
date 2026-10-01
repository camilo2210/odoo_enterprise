# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AccountAssetVariant(models.Model):
    """Behaviour specific to the variants depreciating an asset in a secondary ledger.

    This is an extension of `account.asset.variant`, not a model of its own: a variant
    only becomes a ledger variant when its journal belongs to a journal group. Everything
    here is therefore an extension of the standard behaviour, applied to the ledger variants
    of `self` and delegated to `super()` for the others.
    """
    _inherit = 'account.asset.variant'

    journal_group_name = fields.Char(related='journal_id.journal_group_id.name')
    is_ledger_variant = fields.Boolean(compute='_compute_is_ledger_variant')
    recovery_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Recovery Account",
        compute='_compute_depreciation_accounts', store=True, readonly=False,
        check_company=True,
        domain=[('account_type', 'in', ('income', 'income_other'))],
        help="Account used to record the reversal of excess depreciation when statutory depreciation catches up or the asset is disposed of.",
    )

    def _is_ledger_sub_variant(self):
        """Whether this variant mirrors the depreciation of a main variant in its own ledger."""
        self.ensure_one()
        return self.is_ledger_variant and not self.is_main_variant

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('journal_id')
    def _compute_is_ledger_variant(self):
        for variant in self:
            variant.is_ledger_variant = bool(variant.journal_id.journal_group_id)

    def _compute_depreciation_accounts(self):
        # A ledger variant uses accounts of its depreciation model rather than on
        # the ones of the asset account, and keeps whatever was set manually. A model that
        # does not name its own accounts posts where the main variant does
        sub_variants = self.filtered(lambda variant: not variant.is_main_variant)
        main_variants = self - sub_variants
        super(AccountAssetVariant, main_variants)._compute_depreciation_accounts()
        main_variants.recovery_account_id = False
        for variant in sub_variants:
            main_variant = variant.asset_id.main_variant_id
            variant.account_depreciation_id = (
                variant.account_depreciation_id
                or variant.model_id.ledger_depreciation_account_id
                or main_variant.account_depreciation_id
            )
            variant.account_depreciation_expense_id = (
                variant.account_depreciation_expense_id
                or variant.model_id.ledger_expense_account_id
                or main_variant.account_depreciation_expense_id
            )
            variant.recovery_account_id = variant.recovery_account_id or variant.model_id.ledger_recovery_account_id

    @api.depends('is_ledger_variant')
    def _compute_model_id(self):
        # A ledger variant keeps the model it was created with, it does not follow the asset.
        super(AccountAssetVariant, self.filtered(lambda variant: not variant.is_ledger_variant))._compute_model_id()

    def _compute_book_value(self):
        # The entries of a ledger variant only hold the difference with the main variant,
        # so its book value is the one of the main variant shifted by its own depreciation.
        ledger_variants = self.filtered(lambda variant: variant._is_ledger_sub_variant())
        super(AccountAssetVariant, self - ledger_variants)._compute_book_value()
        for variant in ledger_variants:
            depreciation = sum(
                variant.depreciation_move_ids.filtered(lambda m: m.state == 'posted')
                .mapped('depreciation_value')
            )
            variant.book_value = variant.asset_id.main_variant_id.book_value - depreciation
            if variant.state == 'close' and all(move.state == 'posted' for move in variant.depreciation_move_ids):
                variant.book_value -= variant.salvage_value

    # -------------------------------------------------------------------------
    # CONSTRAINT METHODS
    # -------------------------------------------------------------------------
    @api.constrains('journal_id')
    def _check_unique_ledger_per_asset(self):
        for variant in self:
            # Search for other variants on the same asset with the same group
            if any(
                v != variant
                and v.journal_id.journal_group_id == variant.journal_id.journal_group_id
                for v in variant.asset_id.variant_ids
            ):
                raise UserError(self.env._("An asset cannot have two variants linked to the same ledger"))

    # -------------------------------------------------------------------------
    # BOARD COMPUTATION
    # -------------------------------------------------------------------------
    def _recompute_board(self, start_depreciation_date=False):
        depreciation_move_values = super()._recompute_board(start_depreciation_date)
        if self._is_ledger_sub_variant() and depreciation_move_values:
            self._mirror_main_variant_moves(depreciation_move_values)
        return depreciation_move_values

    def _recompute_move_before_date(self, date):
        move_values = super()._recompute_move_before_date(date)
        if self._is_ledger_sub_variant():
            self._mirror_main_variant_moves(move_values, main_move_date=date)
        return move_values

    def _mirror_main_variant_moves(self, depreciation_move_values, main_move_date=None):
        """Counter the depreciation of the main variant in the board of this ledger variant.

        The entries of a ledger sub-asset only hold the difference with the main variant, so
        every move of the main variant needs a counter-entry here: either merged into a move
        this variant already computed for that date, or added as a move of its own.

        :param depreciation_move_values: this variant's own move values, modified in place
        :param main_move_date: when set, only mirror the moves of the main variant up to that date
        """
        self.ensure_one()
        main_asset_depreciation_move_ids = self.asset_id.main_variant_id.depreciation_move_ids.filtered(
            lambda mv: mv.asset_move_type not in ('disposal', 'sale')
            and not mv.reversal_move_ids
            and not mv.reversed_entry_id
        ).sorted(key=lambda mv: (mv.date, mv.id))
        if not main_asset_depreciation_move_ids:
            raise UserError(self.env._("Cannot generate depreciation board for ledger variant before main asset variant"))
        if main_move_date is not None:
            already_mirrored_dates = set(self.depreciation_move_ids.mapped('date'))
            main_asset_depreciation_move_ids = main_asset_depreciation_move_ids.filtered(
                lambda m: m.date <= main_move_date and m.date not in already_mirrored_dates
            )

        main_moves_by_date = {}
        for move in main_asset_depreciation_move_ids:
            main_moves_by_date[move.date] = move

        depreciation_account = self.account_depreciation_id
        expense_account = self.account_depreciation_expense_id
        for move_vals in depreciation_move_values:
            date = move_vals['date']
            main_move = main_moves_by_date.get(date)
            if main_move is None:
                continue
            ledger_move_line_vals = self.env['account.move']._prepare_move_line_for_asset_depreciation(
                asset_variant=self,
                amount=-main_move.depreciation_value,
                date=date,
                name=move_vals['ref'],
                depreciation_account_id=depreciation_account.id,
                expense_account_id=expense_account.id,
            )
            move_vals['line_ids'].extend([Command.create(line_vals) for line_vals in ledger_move_line_vals])
            del main_moves_by_date[date]

        for date in sorted(main_moves_by_date):
            main_move = main_moves_by_date[date]
            depreciation_move_values.append(self.env['account.move']._prepare_move_for_asset_depreciation(
                amount=-main_move.depreciation_value,
                asset_variant=self,
                depreciation_beginning_date=main_move.asset_depreciation_beginning_date,
                date=main_move.date,
                asset_number_days=main_move.asset_number_days,
                depreciation_account_id=depreciation_account.id,
                expense_account_id=self.recovery_account_id.id,
            ))

    # -------------------------------------------------------------------------
    # PUBLIC ACTIONS
    # -------------------------------------------------------------------------
    def set_to_close(self, invoice_line_ids, date=None, message=None):
        self.ensure_one()
        if self._is_ledger_sub_variant():
            raise UserError(self.env._("A ledger sub-asset is closed together with its asset. Dispose of the asset instead."))

        ledger_variants = self.asset_id.variant_ids.filtered(
            lambda variant: variant._is_ledger_sub_variant() and variant.state not in ('close', 'cancelled')
        )
        if ledger_variants:
            # The sub-assets are named in the message logged by `super()`, but they can only be
            # closed afterwards: they mirror the catch-up depreciation of the main variant.
            message = self.env._(
                "Also closed: %(sub_assets)s. %(message)s",
                sub_assets=', '.join(ledger_variants.mapped('name')),
                message=message or "",
            )
        result = super().set_to_close(invoice_line_ids, date=date, message=message)
        ledger_variants._close_with_main_variant(date or fields.Date.context_today(self))
        return result

    def _close_with_main_variant(self, disposal_date):
        """Close the ledger sub-assets whose main variant has just been disposed of.

        :param disposal_date: the date of the disposal of the main variant
        """
        for variant in self:
            # A ledger variant posts in its own journal, which has its own lock date.
            if disposal_date <= variant.company_id._get_user_fiscal_lock_date(variant.journal_id):
                raise UserError(self.env._("You cannot dispose of a sub-asset before the lock date."))
        self.state = 'close'
        # A ledger variant is never sold: the proceeds are booked on the main variant only.
        move_ids = self._get_disposal_moves([self.env['account.move.line']] * len(self), disposal_date)
        self.env['account.move'].browse(move_ids)._post()

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _get_disposal_line_datas(self, invoice_line_ids, disposal_date):
        self.ensure_one()
        if not self._is_ledger_sub_variant():
            return super()._get_disposal_line_datas(invoice_line_ids, disposal_date)
        # The ledger variant is not sold: its entries are unwound against the recovery account.
        depreciated_amount = self.currency_id.round(self._get_depreciated_amount_at_date(disposal_date))
        if self.currency_id.is_zero(depreciated_amount):
            return []
        return [
            (-depreciated_amount, self.account_depreciation_id),
            (depreciated_amount, self.recovery_account_id),
        ]

    def _get_own_value_residual(self):
        self.ensure_one()
        if not self._is_ledger_sub_variant():
            return super()._get_own_value_residual()

        # On a ledger variant, the entries hold the difference between the variant's own
        # depreciation and the counter-entries of the main variant's, so `value_residual` cannot be
        # used as such: what the main variant depreciated over the countered periods has to be added
        # back to restore the sub-asset's own depreciable value. Only depreciation is looked at on
        # either side: a disposal writes off what is left instead of depreciating it.
        own_moves = self.depreciation_move_ids.filtered(lambda mv: mv.state == 'posted' and mv.asset_move_type == 'depreciation')
        countered_dates = set(own_moves.mapped('date'))
        main_depreciation = sum(self.asset_id.main_variant_id.depreciation_move_ids.filtered(lambda mv: (
            mv.state == 'posted'
            and mv.asset_move_type == 'depreciation'
            and mv.date in countered_dates
        )).mapped('depreciation_value'))
        return (
            self.total_depreciable_value
            - self.already_depreciated_amount_import
            - sum(own_moves.mapped('depreciation_value'))
            - main_depreciation
        )
