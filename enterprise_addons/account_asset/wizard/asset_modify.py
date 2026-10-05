# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import RedirectWarning, UserError
from odoo.fields import Domain
from odoo.tools import float_is_zero
from odoo.tools.misc import format_date


class AssetModify(models.TransientModel):
    _name = 'asset.modify'
    _description = 'Modify Asset'

    name = fields.Text(string='Note')
    asset_variant_id = fields.Many2one(string="Asset", comodel_name='account.asset.variant', required=True, help="The asset to be modified by this wizard", ondelete="cascade")
    method_mode = fields.Selection(selection=[('duration', 'By Duration'), ('rate', 'By Rate')], required=True)
    method_number = fields.Float(string='Duration', required=True)
    method_period = fields.Selection([('1', 'Month'), ('12', 'Year')], string='Number of Months in a Period', help="The amount of time between two depreciations")
    method_rate = fields.Float(string='Rate', compute="_compute_linear_rate", inverse="_inverse_linear_rate", required=True)
    show_duration = fields.Boolean(compute='_compute_show_duration')
    value_residual = fields.Monetary(string="Depreciable Amount", help="New residual amount for the asset", compute="_compute_value_residual", store=True, readonly=False)
    salvage_value = fields.Monetary(string="Not Depreciable Amount", help="New salvage amount for the asset")
    currency_id = fields.Many2one(related='asset_variant_id.currency_id')
    date = fields.Date(default=fields.Date.context_today, string='Date')
    select_invoice_line_id = fields.Boolean(compute="_compute_select_invoice_line_id")
    # if we should display the fields for the creation of gross increase asset
    gain_value = fields.Boolean(compute="_compute_gain_value")

    account_asset_id = fields.Many2one(
        'account.account',
        string="Gross Increase Account",
        check_company=True,
    )
    new_account_asset_id = fields.Many2one(
        'account.account',
        string="New Fixed Asset Account",
        check_company=True,
        domain="[('account_type', '=', 'asset_fixed')]",
        help="The fixed asset account to transfer this asset to. The depreciation parameters of this account will be applied to the new asset.",
    )
    account_asset_counterpart_id = fields.Many2one(
        'account.account',
        check_company=True,
        string="Asset Counterpart Account",
    )
    account_depreciation_id = fields.Many2one(related='account_asset_id.asset_depreciation_account_id')
    account_depreciation_expense_id = fields.Many2one(related='account_asset_id.asset_expense_account_id')
    modify_action = fields.Selection(selection="_get_selection_modify_options", string="Action")
    company_id = fields.Many2one('res.company', related='asset_variant_id.company_id')

    invoice_ids = fields.Many2many(
        comodel_name='account.move',
        string="Customer Invoice",
        check_company=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
        help="The disposal invoice is needed in order to generate the closing journal entry.",
    )
    invoice_line_ids = fields.Many2many(
        comodel_name='account.move.line',
        check_company=True,
        domain="[('move_id', '=', invoice_id), ('display_type', '=', 'product')]",
        help="There are multiple lines that could be the related to this asset",
    )
    gain_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        compute="_compute_accounts", inverse="_inverse_gain_account", readonly=False, compute_sudo=True,
        help="Account used to write the journal item in case of gain",
    )
    loss_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        compute="_compute_accounts", inverse="_inverse_loss_account", readonly=False, compute_sudo=True,
        help="Account used to write the journal item in case of loss",
    )

    informational_text = fields.Html(compute='_compute_informational_text')

    # Technical field to know if there was a profit or a loss in the selling of the asset
    gain_or_loss = fields.Selection([('gain', 'Gain'), ('loss', 'Loss'), ('no', 'No')], compute='_compute_gain_or_loss')

    def _compute_modify_action(self):
        if self.env.context.get('resume_after_pause'):
            return 'resume'
        else:
            return 'dispose'

    def _get_selection_modify_options(self):
        if self.env.context.get('resume_after_pause'):
            return [('resume', self.env._('Resume'))]
        return [
            ('dispose', self.env._("Dispose")),
            ('sell', self.env._("Sell")),
            ('modify', self.env._("Re-evaluate")),
            ('pause', self.env._("Pause")),
            ('activate_depreciation', self.env._("Activate Depreciation")),
        ]

    @api.depends('company_id')
    def _compute_accounts(self):
        for record in self:
            record.gain_account_id = record.company_id.gain_account_id
            record.loss_account_id = record.company_id.loss_account_id

    @api.depends('date')
    def _compute_value_residual(self):
        for record in self:
            record.value_residual = record.asset_variant_id._get_residual_value_at_date(record.date)

    def _inverse_gain_account(self):
        for record in self:
            record.company_id.sudo().gain_account_id = record.gain_account_id

    def _inverse_loss_account(self):
        for record in self:
            record.company_id.sudo().loss_account_id = record.loss_account_id

    @api.onchange('modify_action')
    def _onchange_action(self):
        if self.modify_action == 'sell' and self.asset_variant_id.children_ids.filtered(lambda a: a.state in ('draft', 'open') or a.value_residual > 0):
            raise UserError(self.env._("You cannot automate the journal entry for an asset that has a running gross increase. Please use 'Dispose' on the increase(s)."))
        if self.modify_action not in ('modify', 'resume'):
            self.write({'value_residual': self.asset_variant_id._get_residual_value_at_date(self.date), 'salvage_value': self.asset_variant_id.salvage_value})
        if self.modify_action != 'activate_depreciation':
            self.new_account_asset_id = False

    @api.onchange('invoice_ids')
    def _onchange_invoice_ids(self):
        self.invoice_line_ids = self.invoice_ids.invoice_line_ids.filtered(lambda line: line._origin.id in self.invoice_line_ids.ids)  # because the domain filter doesn't apply and the invoice_line_ids remains selected
        for invoice in self.invoice_ids.filtered(lambda inv: len(inv.invoice_line_ids) == 1):
            self.invoice_line_ids += invoice.invoice_line_ids

    @api.depends('asset_variant_id', 'invoice_ids', 'invoice_line_ids', 'modify_action', 'date')
    def _compute_gain_or_loss(self):
        for record in self:
            balances = abs(sum([invoice.balance for invoice in record.invoice_line_ids]))
            comparison = record.company_id.currency_id.compare_amounts(record.asset_variant_id._get_own_book_value(record.date), balances)
            if record.modify_action in ('sell', 'dispose') and comparison < 0:
                record.gain_or_loss = 'gain'
            elif record.modify_action in ('sell', 'dispose') and comparison > 0:
                record.gain_or_loss = 'loss'
            else:
                record.gain_or_loss = 'no'

    @api.depends('asset_variant_id', 'value_residual', 'salvage_value')
    def _compute_gain_value(self):
        for record in self:
            record.gain_value = record.currency_id.compare_amounts(
                record._get_own_book_value(),
                record.asset_variant_id._get_own_book_value(record.date)
            ) > 0

    @api.depends('loss_account_id', 'gain_account_id', 'gain_or_loss', 'modify_action', 'date', 'value_residual', 'salvage_value', 'asset_variant_id', 'new_account_asset_id')
    def _compute_informational_text(self):
        for wizard in self:
            if wizard.modify_action == 'dispose':
                if wizard.gain_or_loss == 'gain':
                    account = wizard.gain_account_id.display_name or ''
                    gain_or_loss = self.env._('gain')
                elif wizard.gain_or_loss == 'loss':
                    account = wizard.loss_account_id.display_name or ''
                    gain_or_loss = self.env._('loss')
                else:
                    account = ''
                    gain_or_loss = self.env._('gain/loss')
                wizard.informational_text = self.env._(
                    "A depreciation entry will be posted on and including the date %(date)s."
                    "<br/> A disposal entry will be posted on the %(account_type)s account <b>%(account)s</b>.",
                    date=format_date(self.env, wizard.date), account_type=gain_or_loss, account=account,
                )
            elif wizard.modify_action == 'sell':
                if wizard.gain_or_loss == 'gain':
                    account = wizard.gain_account_id.display_name or ''
                elif wizard.gain_or_loss == 'loss':
                    account = wizard.loss_account_id.display_name or ''
                else:
                    account = ''
                wizard.informational_text = self.env._(
                    "A depreciation entry will be posted on and including the date %(date)s."
                    "<br/> A second entry will neutralize the original income and post the  "
                    "outcome of this sale on account <b>%(account)s</b>.",
                    date=format_date(self.env, wizard.date), account=account,
                )
            elif wizard.modify_action == 'pause':
                wizard.informational_text = self.env._(
                    "A depreciation entry will be posted on and including the date %s.",
                    format_date(self.env, wizard.date)
                )
            elif wizard.modify_action == 'modify':
                if wizard.gain_value:
                    text = self.env._("An asset will be created for the value increase of the asset. <br/>")
                else:
                    text = ""
                wizard.informational_text = self.env._(
                    "A depreciation entry will be posted on and including the date %(date)s. <br/> %(extra_text)s "
                    "Future entries will be recomputed to depreciate the asset following the changes.",
                    date=format_date(self.env, wizard.date), extra_text=text,
                )

            elif wizard.modify_action == 'activate_depreciation':
                old_account = wizard.asset_variant_id.account_asset_id.display_name or ''
                new_account = wizard.new_account_asset_id.display_name or ''
                wizard.informational_text = self.env._(
                    "A journal entry will transfer the asset value from "
                    "<strong><em>\"%(old_account)s\"</em></strong> to <strong><em>\"%(new_account)s\"</em></strong> on <strong>%(date)s</strong>."
                    "<br/> The current asset will be closed and a new asset will be created with the same book value."
                    "<br/> Depreciation will begin from <strong>%(date)s</strong> using the depreciation parameters configured on the new account.",
                    old_account=old_account, new_account=new_account or self.env._("(Choose Account)"), date=format_date(self.env, wizard.date),
                )

            else:
                if wizard.gain_value:
                    text = self.env._("An asset will be created for the value increase of the asset. <br/>")
                else:
                    text = ""
                wizard.informational_text = self.env._("%s Future entries will be recomputed to depreciate the asset following the changes.", text)

    @api.depends('invoice_ids', 'modify_action')
    def _compute_select_invoice_line_id(self):
        for record in self:
            record.select_invoice_line_id = record.modify_action == 'sell' and len(record.invoice_ids.invoice_line_ids) > 1

    @api.depends('asset_variant_id.model_id')
    def _compute_show_duration(self):
        for wizard in self:
            wizard.show_duration = wizard.asset_variant_id.model_id.method != 'no_depreciation'

    @api.depends('method_number')
    def _compute_linear_rate(self):
        for model in self:
            if model.method_number:
                model.method_rate = 1 / model.method_number

    def _inverse_linear_rate(self):
        for model in self:
            if model.method_rate:
                model.method_number = 1 / model.method_rate

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if 'asset_variant_id' in vals:
                asset = self.env['account.asset.variant'].browse(vals['asset_variant_id'])
                if asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted' and not m.reversal_move_ids and m.date > today):
                    raise UserError(self.env._("Reverse the depreciation entries posted in the future in order to modify the depreciation"))
                if 'method_number' not in vals:
                    vals.update({'method_number': asset.method_number})
                if 'method_period' not in vals:
                    vals.update({'method_period': asset.method_period})
                if 'method_mode' not in vals:
                    vals.update({'method_mode': asset.method_mode})
                if 'salvage_value' not in vals:
                    vals.update({'salvage_value': asset.salvage_value})
                if 'account_asset_id' not in vals:
                    vals.update({'account_asset_id': asset.account_asset_id.id})
        return super().create(vals_list)

    def modify(self):
        """ Modifies the duration of asset for calculating depreciation
        and maintains the history of old values, in the chatter.
        """
        if self.date <= self.asset_variant_id.company_id._get_user_fiscal_lock_date(self.asset_variant_id.journal_id):
            raise UserError(self.env._("You can't re-evaluate the asset before the lock date."))

        track_init_values = {
            'method_mode': self.asset_variant_id.method_mode,
            'method_number': self.asset_variant_id.method_number,
            'method_period': self.asset_variant_id.method_period,
            'value_residual': self.asset_variant_id.value_residual,
            'salvage_value': self.asset_variant_id.salvage_value,
        }

        # Check if asset model exists with new duration before creating new asset model
        existing_model = self.env['account.depreciation.model'].with_context(active_test=False).search([
                ('method', '=', self.asset_variant_id.method),
                ('method_mode', '=', self.method_mode),
                ('method_number', '=', self.method_number),
                ('method_period', '=', self.method_period),
                ('method_progress_factor', '=', self.asset_variant_id.method_progress_factor),
                ('prorata_computation_type', '=', self.asset_variant_id.prorata_computation_type),
                ('salvage_value_percent', '=', self.asset_variant_id.salvage_value_percent),
                Domain.OR([
                    Domain('company_id', '=', False),
                    Domain('journal_id', '=', self.asset_variant_id.journal_id.id),
                ])
            ], limit=1)
        if existing_model:
            depreciation_model_id = existing_model
        else:
            depreciation_model_id = self.asset_variant_id.model_id.copy({
                'method_number': self.method_number,
                'method_period': self.method_period,
                'method_mode': self.method_mode,
                'active': False,
            })

        asset_vals = {
            'salvage_value': self.salvage_value,
            'account_asset_id': self.account_asset_id,
            'model_id': depreciation_model_id.id,
        }
        if self.env.context.get('resume_after_pause'):
            variants_to_unpause = self.asset_variant_id
            if self.asset_variant_id.is_main_variant:
                variants_to_unpause |= self.asset_variant_id.asset_id.variant_ids.filtered(lambda v: v.state == 'paused')

            self.asset_variant_id.asset_id._message_log(body=self.env._(
                "%(unpause_message)s%(variant_message)s%(note)s",
                unpause_message=self.env._("Asset unpaused. ") if self.asset_variant_id.is_main_variant else "",
                variant_message=(
                    self.env._("Variants resumed: %s. ", ', '.join(variants_to_unpause.mapped('name')))
                    if len(variants_to_unpause) > 1 or not self.asset_variant_id.is_main_variant
                    else ""
                ),
                note=self.name or '',
            ))

            for variant in variants_to_unpause:
                date_before_pause = (
                    max(variant.depreciation_move_ids, key=lambda x: x.date).date
                    if variant.depreciation_move_ids
                    else variant.acquisition_date
                )
                # We are removing one day to number days because we don't count the current day
                # i.e. If we pause and resume the same day, there isn't any gap whereas for depreciation
                # purpose it would count as one full day
                number_days = variant._get_delta_days(date_before_pause, self.date) - 1
                if number_days < 0:
                    raise UserError(self.env._("You cannot resume at a date equal to or before the pause date"))

                variant.write({
                    'asset_paused_days': variant.asset_paused_days + number_days,
                    'state': 'open',
                })

        current_asset_book = self.asset_variant_id._get_own_book_value(self.date)
        after_asset_book = self._get_own_book_value()
        increase = after_asset_book - current_asset_book

        new_residual, new_salvage = self._get_new_asset_values(current_asset_book)
        residual_increase = max(0, self.value_residual - new_residual)
        salvage_increase = max(0, self.salvage_value - new_salvage)

        if not self.env.context.get('resume_after_pause'):
            if self.env['account.move'].search_count([('asset_variant_id', '=', self.asset_variant_id.id), ('state', '=', 'draft'), ('date', '<=', self.date)], limit=1):
                raise UserError(self.env._('There are unposted depreciations prior to the selected operation date, please deal with them first.'))
            self.asset_variant_id._create_move_before_date(self.date)

        asset_vals.update({
            'salvage_value': new_salvage,
        })
        computation_children_changed = (
                depreciation_model_id.method_number != self.asset_variant_id.method_number
                or depreciation_model_id.method_period != self.asset_variant_id.method_period
                or asset_vals.get('asset_paused_days') and not float_is_zero(asset_vals['asset_paused_days'] - self.asset_variant_id.asset_paused_days, 8)
        )
        self.asset_variant_id.write(asset_vals)

        # Check for residual/salvage increase while rounding with the company currency precision to prevent float precision issues.
        if self.currency_id.compare_amounts(residual_increase + salvage_increase, 0) > 0:
            move = self.env['account.move'].create({
                'journal_id': self.asset_variant_id.journal_id.id,
                'date': self.date + relativedelta(days=1),
                'move_type': 'entry',
                'asset_move_type': 'positive_revaluation',
                'line_ids': [
                    Command.create({
                        'account_id': self.account_asset_id.id,
                        'debit': residual_increase + salvage_increase,
                        'credit': 0,
                        'name': self.env._('Value increase for: %(asset)s', asset=self.asset_variant_id.name),
                    }),
                    Command.create({
                        'account_id': self.account_asset_counterpart_id.id,
                        'debit': 0,
                        'credit': residual_increase + salvage_increase,
                        'name': self.env._('Value increase for: %(asset)s', asset=self.asset_variant_id.name),
                    }),
                ],
            })
            move._post()
            asset_increase = self.env['account.asset'].create({
                'name': self.asset_variant_id.name + ': ' + self.name if self.name else "",
                'model_id': depreciation_model_id.id,
                'currency_id': self.asset_variant_id.currency_id.id,
                'company_id': self.asset_variant_id.company_id.id,
                'acquisition_date': self.date + relativedelta(days=1),
                'value_residual': residual_increase,
                'salvage_value': salvage_increase,
                'prorata_date': self.date + relativedelta(days=1),
                'original_value': self._get_increase_original_value(residual_increase, salvage_increase),
                'account_asset_id': self.account_asset_id.id,
                'parent_id': self.asset_variant_id.id,
                'original_move_line_ids': [(6, 0, move.line_ids.filtered(lambda r: r.account_id == self.account_asset_id).ids)],
            })
            asset_increase.validate()

            subject = self.env._('A gross increase has been created: %(link)s', link=asset_increase._get_html_link())
            self.asset_variant_id.asset_id.message_post(body=subject)

        if self.currency_id.compare_amounts(increase, 0) < 0:
            move = self.env['account.move'].create(self.env['account.move']._prepare_move_for_asset_depreciation(
                amount=-increase,
                asset_variant=self.asset_variant_id,
                depreciation_beginning_date=self.date,
                date=self.date,
                asset_number_days=0,
                asset_value_change=True,
                asset_move_type='negative_revaluation',
            ))._post()

        restart_date = self.date if self.env.context.get('resume_after_pause') else self.date + relativedelta(days=1)
        if self.asset_variant_id.depreciation_move_ids:
            self.asset_variant_id.compute_depreciation_board(restart_date)
        else:
            # We have no moves, we can compute it as new
            self.asset_variant_id.compute_depreciation_board()

        if computation_children_changed:
            children = self.asset_variant_id.children_ids
            children.write({
                'model_id': asset_vals['model_id'],
                'asset_paused_days': self.asset_variant_id.asset_paused_days,
            })

            for child in children:
                if not self.env.context.get('resume_after_pause'):
                    child._create_move_before_date(self.date)
                if child.depreciation_move_ids:
                    child.compute_depreciation_board(restart_date)
                else:
                    child.compute_depreciation_board()
                child._check_depreciations()
                child.depreciation_move_ids.filtered(lambda move: move.state != 'posted')._post()

        self.asset_variant_id.asset_id._track_add({self.asset_variant_id.asset_id.id: track_init_values}, body=self.env._("Depreciation board modified %s", self.name))
        self.asset_variant_id._check_depreciations()
        self.asset_variant_id.depreciation_move_ids.filtered(lambda move: move.state != 'posted')._post()
        return {'type': 'ir.actions.act_window_close'}

    def pause(self):
        for record in self:
            variants_to_pause = record.asset_variant_id
            if record.asset_variant_id.is_main_variant:
                variants_to_pause |= record.asset_variant_id.asset_id.variant_ids.filtered(lambda v: v.state == 'open')

            record.asset_variant_id.asset_id._message_log(body=self.env._(
                "%(pause_message)s%(variant_message)s%(note)s",
                pause_message=self.env._("Asset paused. ") if self.asset_variant_id.is_main_variant else "",
                variant_message=(
                    self.env._("Variants paused: %s. ", ', '.join(variants_to_pause.mapped('name')))
                    if len(variants_to_pause) > 1 or not self.asset_variant_id.is_main_variant
                    else ""
                ),
                note=record.name or '',
            ))

            for variant in variants_to_pause:
                variant.pause(pause_date=record.date, message=record.name)

    def sell_dispose(self):
        self.ensure_one()
        if self.gain_account_id == self.asset_variant_id.account_depreciation_id or self.loss_account_id == self.asset_variant_id.account_depreciation_id:
            raise UserError(self.env._("You cannot select the same account as the Depreciation Account"))
        invoice_lines = self.env['account.move.line'] if self.modify_action == 'dispose' else self.invoice_line_ids
        return self.asset_variant_id.set_to_close(invoice_line_ids=invoice_lines, date=self.date, message=self.name)

    def activate_depreciation(self):
        """Closes the current no-depreciation asset and creates a new asset on a different
        fixed asset account, transferring the book value via a misc journal entry."""
        self.ensure_one()
        variant = self.asset_variant_id

        if variant.state != 'open' or variant.model_id.method != 'no_depreciation':
            raise UserError(self.env._(
                "You can only activate a running asset that has a \"%s\" method.",
                dict(self.env['account.depreciation.model']._fields['method']._description_selection(self.env)).get('no_depreciation')
            ))
        if self.date <= variant.company_id._get_user_fiscal_lock_date(variant.journal_id):
            raise UserError(self.env._("You can't activate depreciation before the lock date."))
        if self.date < variant.acquisition_date:
            raise UserError(self.env._("The activation date cannot be before the asset's acquisition date."))
        if running_children := variant.children_ids.filtered(lambda a: a.state in ('draft', 'open')):
            raise RedirectWarning(
                message=self.env._("You cannot activate depreciation on an asset that has running gross increases. Please dispose of them first."),
                action=running_children.open_asset(['list', 'form']),
                button_text=self.env._("Show Gross Increases"),
            )
        if self.new_account_asset_id == variant.account_asset_id:
            raise UserError(self.env._("Please select a different fixed asset account than the one used on the current asset."))
        if not (
            self.new_account_asset_id.depreciation_model_id
            and self.new_account_asset_id.asset_depreciation_account_id
            and self.new_account_asset_id.asset_expense_account_id
        ):
            raise RedirectWarning(
                message=self.env._("Fixed asset account selected is not configured to create an asset."),
                action=self.new_account_asset_id._get_records_action(),
                button_text=self.env._("Go to Account"),
            )

        journal = variant.journal_id or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(variant.company_id),
            ('type', '=', 'general'),
        ], limit=1)

        book_value = variant.book_value
        salvage_value = variant.salvage_value

        move = self.env['account.move'].with_company(variant.company_id).create({
            'journal_id': journal.id,
            'date': self.date,
            'move_type': 'entry',
            'asset_depreciation_beginning_date': self.date,
            'ref': self.env._("Activate Depreciation: %(asset)s", asset=variant.name),
            'line_ids': [
                Command.create({
                    'account_id': self.new_account_asset_id.id,
                    'debit': book_value,
                    'credit': 0,
                    'name': self.env._("Activate Depreciation for: %(asset)s", asset=variant.name),
                }),
                Command.create({
                    'account_id': variant.account_asset_id.id,
                    'debit': 0,
                    'credit': book_value,
                    'name': self.env._("Activate Depreciation for: %(asset)s", asset=variant.name),
                }),
            ],
        })
        move.action_post()

        variant.write({
            'depreciation_move_ids': [Command.link(move.id)],
            'state': 'close',
        })

        new_asset = self.env['account.asset'].create({
            'name': variant.asset_id.name,
            'account_asset_id': self.new_account_asset_id.id,
            'original_value': book_value,
            'salvage_value': salvage_value,
            'acquisition_date': self.date,
            'company_id': variant.asset_id.company_id.id,
            'origin_asset_id': variant.asset_id.id,
            'state': 'draft',
        })
        new_asset.validate()

        new_asset.message_post(body=Markup('<br>').join([
            self.env._("Depreciation activated from asset: %s", variant.asset_id._get_html_link()),
            self.env._("Value transferred from %(old_account)s to %(new_account)s.",
                old_account=variant.account_asset_id.display_name,
                new_account=self.new_account_asset_id.display_name,
            ),
        ]))

        variant.asset_id.message_post(body=Markup('<br>').join([
            self.env._("Depreciation activated. Asset value transferred from %(old_account)s to %(new_account)s.",
                old_account=variant.account_asset_id.display_name,
                new_account=self.new_account_asset_id.display_name,
            ),
            Markup(self.env._("See new asset created: <b>%s</b>")) % new_asset._get_html_link(),
            self.env._("Note: %s", self.name) if self.name else ""
        ]))

        return {'type': 'ir.actions.act_window_close'}

    def _get_own_book_value(self):
        return self.value_residual + self.salvage_value

    def _get_increase_original_value(self, residual_increase, salvage_increase):
        return residual_increase + salvage_increase

    def _get_new_asset_values(self, current_asset_book):
        self.ensure_one()
        new_residual = min(current_asset_book - min(self.salvage_value, self.asset_variant_id.salvage_value), self.value_residual)
        new_salvage = min(current_asset_book - new_residual, self.salvage_value)
        return new_residual, new_salvage
