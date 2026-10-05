# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from markupsafe import Markup

from odoo import api, fields, models, Command
from odoo.exceptions import UserError, ValidationError, RedirectWarning
from odoo.tools import float_compare, _, SQL
from odoo.tools.misc import formatLang
from dateutil.relativedelta import relativedelta


class AccountMove(models.Model):
    _inherit = 'account.move'

    asset_variant_id = fields.Many2one('account.asset.variant', string='Asset', index=True, ondelete='cascade', copy=False, domain="[('company_id', '=', company_id)]")
    asset_remaining_value = fields.Monetary(string='Depreciable Value', compute='_compute_depreciation_cumulative_value')
    asset_depreciated_value = fields.Monetary(string='Cumulative Depreciation', compute='_compute_depreciation_cumulative_value')
    # true when this move is the result of the changing of value of an asset
    asset_value_change = fields.Boolean()
    #  how many days of depreciation this entry corresponds to
    asset_number_days = fields.Integer(string="Number of days", copy=False) # deprecated
    asset_depreciation_beginning_date = fields.Date(string="Date of the beginning of the depreciation", copy=False) # technical field stating when the depreciation associated with this entry has begun
    depreciation_value = fields.Monetary(
        string="Depreciation",
        compute="_compute_depreciation_value", inverse="_inverse_depreciation_value", store=True,
    )

    asset_ids = fields.One2many('account.asset', string='Assets', compute="_compute_asset_ids", compute_sudo=True)
    asset_id_display_name = fields.Char(compute="_compute_asset_ids", compute_sudo=True)   # just a button label. That's to avoid a plethora of different buttons defined in xml
    count_asset = fields.Integer(compute="_compute_asset_ids", compute_sudo=True)
    draft_asset_exists = fields.Boolean(compute="_compute_asset_ids", compute_sudo=True)
    asset_move_type = fields.Selection(
        selection=[
            ('depreciation', 'Depreciation'),
            ('sale', 'Sale'),
            ('purchase', 'Purchase'),
            ('disposal', 'Disposal'),
            ('negative_revaluation', 'Negative revaluation'),
            ('positive_revaluation', 'Positive revaluation'),
        ],
        string='Asset Move Type',
        compute='_compute_asset_move_type', store=True,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('asset_variant_id', 'depreciation_value', 'asset_variant_id.total_depreciable_value', 'asset_variant_id.already_depreciated_amount_import', 'state')
    def _compute_depreciation_cumulative_value(self):
        self.asset_depreciated_value = 0
        self.asset_remaining_value = 0

        # make sure to protect all the records being assigned, because the
        # assignments invoke method write() on non-protected records, which may
        # cause an infinite recursion in case method write() needs to read one
        # of these fields (like in case of a base automation)
        fields = [self._fields['asset_remaining_value'], self._fields['asset_depreciated_value']]
        with self.env.protecting(fields, self.asset_variant_id.depreciation_move_ids):
            for variant in self.asset_variant_id:
                depreciated = variant.already_depreciated_amount_import
                remaining = variant.total_depreciable_value - variant.already_depreciated_amount_import
                for move in variant.depreciation_move_ids.sorted(lambda mv: (mv.date, mv._origin.id)):
                    if move.state != 'cancel':
                        remaining -= move.depreciation_value
                        depreciated += move.depreciation_value
                    move.asset_remaining_value = remaining
                    move.asset_depreciated_value = depreciated

    @api.depends('line_ids.balance')
    def _compute_depreciation_value(self):
        for move in self:
            variant = move.asset_variant_id or move.reversed_entry_id.asset_variant_id  # reversed moves are created before being assigned to the asset
            if variant:
                depreciation_lines = move._get_asset_depreciation_line()
                asset_depreciation = sum(depreciation_lines.mapped('balance'))
                # Special case of closing entry
                if any(
                    line.account_id == variant.account_asset_id
                    and float_compare(-line.balance, variant.original_value, precision_rounding=variant.currency_id.rounding) == 0
                    for line in move.line_ids
                ):
                    disposal_date = move.date
                    all_moves_before_disposal = (variant.depreciation_move_ids - move).filtered(lambda x: x.date <= disposal_date)
                    depreciation_lines = all_moves_before_disposal._get_asset_depreciation_line()
                    depreciated_amount = variant.currency_id.round(sum(depreciation_lines.mapped('balance')) + variant.already_depreciated_amount_import)
                    asset_depreciation = (
                        variant.original_value
                        - variant.salvage_value
                        - depreciated_amount
                    )
                elif not variant.is_main_variant and move.line_ids:
                    ledger_depreciation_line = move._get_asset_ledger_depreciation_line()
                    asset_depreciation = sum(ledger_depreciation_line.mapped('balance'))
            else:
                asset_depreciation = 0
            move.depreciation_value = asset_depreciation

    @api.depends('asset_variant_id', 'asset_ids')
    def _compute_asset_move_type(self):
        for move in self:
            if move.asset_ids:
                move.asset_move_type = 'positive_revaluation' if move.asset_ids.parent_id else 'purchase'
            elif not move.asset_move_type or not move.asset_variant_id:
                move.asset_move_type = False

    # -------------------------------------------------------------------------
    # INVERSE METHODS
    # -------------------------------------------------------------------------
    def _inverse_depreciation_value(self):
        for move in self:
            depreciation_lines = set(move._get_asset_depreciation_line())
            move.write({'line_ids': [
                Command.update(line.id, {
                    'balance': move.depreciation_value * (1 if line in depreciation_lines else -1),
                })
                for line in move.line_ids
            ]})

    # -------------------------------------------------------------------------
    # CONSTRAINT METHODS
    # -------------------------------------------------------------------------
    @api.constrains('state', 'asset_variant_id')
    def _constrains_check_asset_state(self):
        for move in self.filtered(lambda mv: mv.asset_variant_id):
            variant = move.asset_variant_id
            if variant.state == 'draft' and move.state == 'posted':
                raise ValidationError(_("You can't post an entry related to a draft asset. Please post the asset before."))

    def _post(self, soft=True):
        # OVERRIDE
        posted = super()._post(soft)

        # log the post of a depreciation
        posted._log_depreciation_asset()

        # look for any asset to create, in case we just posted a bill on an account
        # configured to automatically create assets
        posted.sudo()._auto_create_asset()

        # update asset in case bill has asset and values changed
        posted.sudo()._auto_update_asset()

        return posted

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if default_values_list is None:
            default_values_list = [{} for _i in self]
        asset_messages = defaultdict(list)
        for move, default_values in zip(self, default_values_list):
            # Report the value of this move to the next draft move or create a new one
            if move.asset_variant_id:
                # Recompute the status of the asset for all depreciations posted after the reversed entry

                first_draft = min(move.asset_variant_id.depreciation_move_ids.filtered(lambda m: m.state == 'draft'), key=lambda m: m.date, default=None)
                if first_draft:
                    # If there is a draft, simply move/add the depreciation amount here
                    first_draft.depreciation_value += move.depreciation_value
                elif move.asset_variant_id.state != 'close':
                    # If there was no draft move left, create one.
                    # Unless the asset is being closed, then the closing move
                    # takes care of balancing the asset.
                    last_date = max(move.asset_variant_id.depreciation_move_ids.mapped('date'))
                    method_period = move.asset_variant_id.method_period

                    self.create(self._prepare_move_for_asset_depreciation(
                        asset_variant=move.asset_variant_id,
                        amount=move.depreciation_value,
                        depreciation_beginning_date=last_date + (relativedelta(months=1) if method_period == "1" else relativedelta(years=1)),
                        date=last_date + (relativedelta(months=1) if method_period == "1" else relativedelta(years=1)),
                        asset_number_days=0,
                    ))

                msg = self.env._(
                    "Depreciation entry %(name)s reversed (%(value)s)",
                    name=move.name,
                    value=formatLang(self.env, move.depreciation_value, currency_obj=move.company_id.currency_id),
                )
                asset_messages[move.asset_variant_id].append(msg)
                default_values['asset_variant_id'] = move.asset_variant_id.id
                default_values['asset_number_days'] = -move.asset_number_days
                default_values['asset_depreciation_beginning_date'] = default_values.get('date', move.date)

        for variant, messages in asset_messages.items():
            variant.asset_id.message_post(body=Markup("%s:<br>") % variant.name + Markup('<br>').join(messages))

        return super(AccountMove, self)._reverse_moves(default_values_list, cancel)

    def button_cancel(self):
        # OVERRIDE
        res = super(AccountMove, self).button_cancel()
        self.env['account.asset'].sudo().search([('original_move_line_ids.move_id', 'in', self.ids)]).write({'active': False})
        return res

    def button_draft(self):
        for move in self:
            # Cancelling all assets linked to move
            move.asset_ids.filtered(lambda a: a.state == 'open').set_to_cancelled()

            # Remove any draft asset that could be linked to the account move being reset to draft
            move.asset_ids.filtered(lambda x: x.state == 'draft').unlink()
        return super(AccountMove, self).button_draft()

    def _log_depreciation_asset(self):
        for variant, moves in self.filtered(lambda m: m.asset_variant_id).grouped('asset_variant_id').items():
            variant.asset_id.message_post(body=Markup("%s:<br>") % variant.name + Markup('<br>').join([
                self.env._(
                    "Depreciation entry %(name)s posted (%(value)s)",
                    name=move.name,
                    value=formatLang(self.env, move.depreciation_value, currency_obj=move.company_id.currency_id),
                )
                for move in moves
            ]))

    def _auto_create_asset(self):
        create_list = []
        for move in self:
            if not move.is_invoice() or move.state != 'posted':
                continue

            for move_line in move.line_ids:
                if (
                    move_line.account_id
                    and move_line.account_id.can_create_asset
                    and move_line.account_id.depreciation_model_id
                    and not (move_line.currency_id or move.currency_id).is_zero(move_line.price_total)
                    and not move_line.asset_ids
                    and not move_line.tax_line_id
                    and move_line.price_total > 0
                    and not (move.move_type in ('out_invoice', 'out_refund') and move_line.account_id.internal_group == 'asset')
                ):
                    if not move_line.name:
                        if move_line.product_id:
                            move_line.name = move_line.product_id.display_name
                        else:
                            raise UserError(_('Journal Items of %(account)s should have a label in order to generate an asset', account=move_line.account_id.display_name))

                    if (
                        move_line.account_id.depreciation_model_id.method != 'no_depreciation'
                        and not (
                            move_line.account_id.asset_depreciation_account_id
                            and move_line.account_id.asset_expense_account_id
                        )
                    ):
                        raise UserError(self.env._(
                            "Account %(account)s should have accumulated depreciation and depreciation"
                            " expense accounts set in order to generate an asset",
                            account=move_line.account_id.display_name,
                        ))

                    vals = {
                        'name': move_line.name,
                        'company_id': move_line.company_id.id,
                        'currency_id': move_line.company_currency_id.id,
                        'analytic_distribution': move_line.analytic_distribution,
                        'original_move_line_ids': [(6, False, move_line.ids)],
                        'state': 'draft',
                        'acquisition_date': move.invoice_date if not move.reversed_entry_id else move.reversed_entry_id.invoice_date,
                        'model_id': move_line.depreciation_model_id.id,
                    }
                    create_list.append(vals)

        assets = self.env['account.asset'].with_context({}).create(create_list)
        for asset, vals in zip(assets, create_list):
            # Create variants if depreciation ledger is defined on the account
            asset._create_variants(asset.account_asset_id.ledger_depreciation_model_ids)

            asset.validate()
            invoice = asset.original_move_line_ids.move_id
            if invoice:
                asset.message_post(body=Markup(_('Asset created from invoice: <b>%s</b>')) % invoice._get_html_link())
                asset._post_non_deductible_tax_value()
        return assets

    def _auto_update_asset(self):
        for move in self:
            asset_ids = move.asset_ids.filtered(lambda a: a.state in ('draft', 'cancelled'))
            if not move.is_invoice() or move.state != 'posted' or not asset_ids:
                continue

            asset_ids.filtered(lambda a: a.state != 'draft').set_to_draft()
            assets_to_update = self.env['account.asset']
            for line in move.line_ids.filtered(lambda aml: aml.asset_ids):
                line.asset_ids.write({
                    'name': line.name,
                    'company_id': line.company_id.id,
                    'currency_id': line.company_currency_id.id,
                    'analytic_distribution': line.analytic_distribution,
                    'acquisition_date': move.reversed_entry_id.invoice_date or move.invoice_date,
                })
                if line.depreciation_model_id:
                    line.asset_ids.model_id = line.depreciation_model_id
                assets_to_update |= line.asset_ids

            # To update asset values in case line values were updated
            assets_to_update.modified(['original_move_line_ids'])
            assets_to_ignore = self.env['account.asset']
            for asset in assets_to_update:
                line_account = asset.original_move_line_ids.account_id
                if len(line_account) > 1:
                    raise UserError(_(
                        "You cannot update the account for asset '%s' because it is linked to "
                        "journal items from multiple different accounts.",
                        asset.name
                    ))
                # Line account changed to a non fixed asset account so we delete the asset
                if not (line_account.can_create_asset and asset.original_move_line_ids.depreciation_model_id):
                    assets_to_ignore += asset

            assets_to_update -= assets_to_ignore
            assets_to_ignore.set_to_cancelled()
            assets_to_update.validate()
            for asset in assets_to_update:
                asset.message_post(body=_('Asset updated from invoice: %s', move._get_html_link()))
                asset._post_non_deductible_tax_value()

    @api.model
    def _prepare_move_for_asset_depreciation(
        self,
        *,
        asset_variant,
        amount,
        depreciation_beginning_date,
        date,
        asset_number_days,
        depreciation_account_id=False,
        expense_account_id=False,
        asset_value_change=False,
        asset_move_type='depreciation',
    ):
        variant = asset_variant
        depreciation_account_id = depreciation_account_id or variant.account_depreciation_id.id
        expense_account_id = expense_account_id or variant.account_depreciation_expense_id.id
        analytic_distribution = variant.analytic_distribution
        current_currency = variant.currency_id
        # Keep the partner on the original invoice if there is only one
        partner = variant.original_move_line_ids.partner_id
        partner = partner[:1] if len(partner) <= 1 else self.env['res.partner']
        name = _("%s: Depreciation", variant.name)
        move_line_1, move_line_2 = self._prepare_move_line_for_asset_depreciation(
            asset_variant=variant,
            amount=amount,
            date=date,
            name=name,
            depreciation_account_id=depreciation_account_id,
            expense_account_id=expense_account_id,
        )
        # Only set the 'analytic_distribution' key if there is an analytic distribution on the asset.
        # Otherwise, it prevents the computation of the analytic distribution.
        if analytic_distribution:
            move_line_1['analytic_distribution'] = analytic_distribution
            move_line_2['analytic_distribution'] = analytic_distribution
        move_vals = {
            'partner_id': partner.id,
            'date': date,
            'journal_id': variant.journal_id.id,
            'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
            'asset_variant_id': variant.id,
            'ref': name,
            'asset_depreciation_beginning_date': depreciation_beginning_date,
            'asset_number_days': asset_number_days,
            'asset_value_change': asset_value_change,
            'move_type': 'entry',
            'currency_id': current_currency.id,
            'asset_move_type': asset_move_type,
            'company_id': variant.company_id.id,
        }
        return move_vals

    @api.model
    def _prepare_move_line_for_asset_depreciation(
        self,
        *,
        asset_variant,
        amount,
        date,
        name,
        depreciation_account_id,
        expense_account_id,
    ):
        variant = asset_variant
        company_currency = variant.company_id.currency_id
        current_currency = variant.currency_id
        amount_currency = amount
        balance = current_currency._convert(amount_currency, company_currency, variant.company_id, date)
        # Keep the partner on the original invoice if there is only one
        partner = variant.original_move_line_ids.partner_id
        partner = partner if len(partner) <= 1 else self.env['res.partner']
        move_line_1 = {
            'name': name,
            'partner_id': partner.id,
            'account_id': depreciation_account_id,
            'balance': -balance,
            'currency_id': current_currency.id,
            'amount_currency': -amount_currency,
        }
        move_line_2 = {
            'name': name,
            'partner_id': partner.id,
            'account_id': expense_account_id,
            'balance': balance,
            'currency_id': current_currency.id,
            'amount_currency': amount_currency,
        }
        return move_line_1, move_line_2

    def _get_asset_depreciation_line(self):
        variant = self.asset_variant_id
        return self.line_ids.filtered(lambda line: line.account_id.internal_group == 'expense' or line.account_id == variant.account_depreciation_expense_id)

    def _get_asset_ledger_depreciation_line(self):
        variant = self.asset_variant_id
        return self.line_ids.filtered(lambda line:
            line.account_id.internal_group == 'expense'
            or line.account_id.internal_group == 'income'
            or line.account_id == variant.account_depreciation_expense_id
            or line.account_id == variant.recovery_account_id
        )

    @api.depends('line_ids.asset_ids')
    def _compute_asset_ids(self):
        for record in self:
            record.asset_ids = record.line_ids.asset_ids
            record.count_asset = len(record.asset_ids)
            record.asset_id_display_name = _('Asset')
            record.draft_asset_exists = bool(record.asset_ids.filtered(lambda x: x.state == "draft"))

    def open_asset_view(self):
        return self.asset_variant_id.open_asset(['form'])

    def action_open_asset_ids(self):
        return self.asset_ids.open_asset(['list', 'form'])


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    asset_ids = fields.Many2many('account.asset', 'asset_move_line_rel', 'line_id', 'asset_id', string='Related Assets', copy=False)
    non_deductible_tax_value = fields.Monetary(compute='_compute_non_deductible_tax_value', currency_field='company_currency_id')

    depreciation_model_id = fields.Many2one(
        comodel_name='account.depreciation.model',
        compute='_compute_depreciation_model_id',
        store=True, readonly=False,
    )
    display_depreciation_model = fields.Boolean(compute='_compute_display_depreciation_model')

    def _get_computed_taxes(self):
        if self.move_id.asset_variant_id:
            return self.tax_ids
        return super()._get_computed_taxes()

    def turn_as_asset(self):
        if len(self.company_id) != 1:
            raise UserError(_("All the lines should be from the same company"))
        if any(line.move_id.state == 'draft' for line in self):
            raise UserError(_("All the lines should be posted"))
        account = self.account_id
        if len(account) != 1:
            raise UserError(_("All the lines should be from the same account"))
        if not account.can_create_asset:
            raise UserError(self.env._(
                "Account %(name)s cannot be used to create an asset. "
                "The account must be of the Fixed Asset type.",
                name=account.display_name))
        if not (account.depreciation_model_id and account.asset_depreciation_account_id and account.asset_expense_account_id):
            raise RedirectWarning(
                message=self.env._("Account %(name)s not setup to generate assets. Depreciation model and asset accounts need to be set on account.", name=account.display_name),
                action=account._get_records_action(),
                button_text=self.env._("Go to Account"),
            )
        ctx = self.env.context.copy()
        ctx.update({
            'default_original_move_line_ids': [(6, False, self.env.context['active_ids'])],
            'default_company_id': self.company_id.id,
        })
        return {
            "name": _("Turn as an asset"),
            "type": "ir.actions.act_window",
            "res_model": "account.asset",
            "views": [[False, "form"]],
            "target": "current",
            "context": ctx,
        }

    @api.depends('account_id')
    def _compute_depreciation_model_id(self):
        for line in self:
            line.depreciation_model_id = line.account_id.depreciation_model_id

    @api.depends('account_id', 'account_id.depreciation_model_id')
    def _compute_display_depreciation_model(self):
        for line in self:
            line.display_depreciation_model = bool(line.account_id.depreciation_model_id) and line.move_id.is_invoice()

    @api.depends('tax_ids.invoice_repartition_line_ids')
    def _compute_non_deductible_tax_value(self):
        """ Handle the specific case of non deductible taxes,
        such as "50% Non Déductible - Frais de voiture (Prix Excl.)" in Belgium.
        """
        non_deductible_tax_ids = self.tax_ids.filtered(lambda tax: tax.non_deductible_amount != 0)

        res = {}
        if non_deductible_tax_ids and self.ids:
            domain = [('move_id', 'in', self.move_id.ids)]
            tax_details_query = self._get_query_tax_details_from_domain(domain)

            self.flush_model()
            self.env.cr.execute(SQL(
                '''
                SELECT
                    tdq.base_line_id,
                    SUM(tdq.tax_amount_currency)
                FROM (%(tax_details_query)s) AS tdq
                JOIN account_move_line aml ON aml.id = tdq.tax_line_id
                JOIN account_tax_repartition_line trl ON trl.id = tdq.tax_repartition_line_id
                WHERE tdq.base_line_id IN %(base_line_ids)s
                AND trl.use_in_tax_closing IS FALSE
                GROUP BY tdq.base_line_id
                ''',
                tax_details_query=tax_details_query,
                base_line_ids=tuple(self.ids),
            ))

            res = {row['base_line_id']: row['sum'] for row in self.env.cr.dictfetchall()}

        for record in self:
            record.non_deductible_tax_value = res.get(record._origin.id, 0.0)

    def write(self, vals):
        initial_accounts = {line.id: line.account_id.id for line in self}
        result = super().write(vals)

        lines_changed = self.filtered(lambda line: line.account_id.id != initial_accounts[line.id])
        if lines_changed:
            lines_with_assets = lines_changed.filtered(lambda line: line.asset_ids)
            lines_with_no_assets = lines_changed.filtered(lambda line: not line.asset_ids and line.account_id.depreciation_model_id)
            # Create assets for move lines
            if lines_with_no_assets:
                lines_with_no_assets.move_id.sudo()._auto_create_asset()
            # Update asset values or delete assets
            if lines_with_assets:
                lines_with_assets.asset_ids.filtered(lambda a: a.state == 'open').set_to_cancelled()
                lines_with_assets.move_id.sudo()._auto_update_asset()

        return result
