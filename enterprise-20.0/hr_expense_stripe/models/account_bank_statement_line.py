from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils

from odoo.addons.hr_expense_stripe.utils import format_amount_from_stripe, make_request_stripe_proxy


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    stripe_id = fields.Char("Stripe transaction ID", readonly=True, copy=False)

    _unique_stripe_id_unless_dispute = models.UniqueIndex(
        definition="(stripe_id, (left(stripe_id, 4) = 'idp_' AND amount > 0))",
        message="Only one bank statement can be created from a single stripe transaction "
                 "(two are allowed for a dispute: reinstatement and rescindment)",
    )

    @api.model
    def _create_from_stripe_topup(self, tu_object):
        company = self.env.company
        journal = company.stripe_journal_id
        journal_currency = journal.currency_id or journal.company_id.stripe_currency_id
        topup_currency = (
            self.env['res.currency'].with_context(active_test=False).search([('name', 'ilike', tu_object['currency'])], limit=1)
            or journal_currency
        )
        if topup_currency and not topup_currency.active:
            topup_currency.active = True
        amount = format_amount_from_stripe(tu_object['amount'], journal_currency)
        date = date_utils.datetime.fromtimestamp(tu_object['created'])

        transfer_account = company.transfer_account_id
        create_vals = {
            'stripe_id': tu_object['id'],
            'date': date,
            'journal_id': journal.id,
            'payment_ref': _("Stripe Top-up"),
            'amount': amount,
        }
        if transfer_account.active:
            create_vals['counterpart_account_id'] = transfer_account.id  # Hack 'field'

        if topup_currency != journal_currency:
            create_vals.update({
                'foreign_currency_id': topup_currency.id,
                'amount_currency': amount,
                'amount': topup_currency._convert(amount, journal_currency, journal.company_id, date),
            })
        self.with_context(no_retrieve_partner=True).create([create_vals])

    @api.model
    def _create_from_stripe_transaction(self, tr_object):
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', tr_object['card'])], limit=1)
        if not card:
            raise UserError(_("A card that doesn't exist on the database was used"))
        amount, amount_currency, journal, journal_currency, merchant_currency = self._get_transaction_data(card, tr_object)
        payment_ref = _(
            "Card ending in %(last_4)s payment to %(merchant_name)s",
            last_4=card.last_4,
            merchant_name=tr_object['merchant_data']['name']
        )
        create_vals = {
            'stripe_id': tr_object['id'],
            'date': date_utils.datetime.fromtimestamp(tr_object['created']),
            'journal_id': journal.id,
            'payment_ref': payment_ref,
            'amount': amount,
        }
        if merchant_currency != journal_currency:
            create_vals.update({
                'foreign_currency_id': merchant_currency.id,
                'amount_currency': amount_currency,
            })

        stmt_line = self.create([create_vals])

        expenses = self.env['hr.expense'].search([('stripe_transaction_id', '=', tr_object['id'])])
        if expenses:
            for expense in expenses:
                stmt_line.move_id.message_post(
                    body=_('Transaction created from %(expense)s', expense=expense._get_html_link(title=expense.name)),
                    message_type='comment',
                )
            if all(expense.account_move_id.origin_payment_id.state == 'paid' for expense in expenses):
                # Split expenses cases, we only want to reconcile if everything posted
                expenses._reconcile_stripe_payments(existing_statement_lines=stmt_line)

    def _update_from_stripe_transaction(self, tr_object):
        self.ensure_one()
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', tr_object['card'])], limit=1)
        amount, amount_currency, _journal, journal_currency, merchant_currency = self._get_transaction_data(card, tr_object)

        update_vals = {}
        if self.currency_id.compare_amounts(self.amount, amount) != 0:
            update_vals['amount'] = amount

        if merchant_currency != journal_currency:
            if self.foreign_currency_id != merchant_currency:
                update_vals['foreign_currency_id'] = merchant_currency.id
            if merchant_currency.compare_amounts(self.amount_currency, amount_currency) != 0:
                update_vals['amount_currency'] = amount_currency

        if update_vals:
            self.write(update_vals)

    ##################
    # Helper methods #
    ##################
    @api.model
    def _get_transaction_data(self, card, tr_object):
        journal = card.journal_id
        journal_currency = journal.currency_id or journal.stripe_currency_id
        amount = amount_currency = format_amount_from_stripe(tr_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([('name', 'ilike', tr_object['merchant_currency'])], limit=1)
            or journal_currency
        )
        if merchant_currency and not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != journal_currency:
            amount_currency = format_amount_from_stripe(tr_object['merchant_amount'], merchant_currency)
        return amount, amount_currency, journal, journal_currency, merchant_currency

    @api.model
    def _create_from_stripe_dispute(self, dispute_object, movement_type):
        dispute = self.env['hr.expense.stripe.dispute'].search([('stripe_id', '=', dispute_object['id'])], limit=1)
        if not dispute:
            raise UserError(self.env._("A dispute that doesn't exist on the database was used"))

        for state, expenses in dispute.expense_ids.grouped('state').items():
            if state == 'draft':
                expenses.action_submit()
            if state in {'draft', 'submitted'}:
                expenses._do_approve()
            if state in {'draft', 'submitted', 'approved'}:
                expenses.account_move_id.origin_payment_id.action_post()

        stripe_currency = dispute.company_id.stripe_currency_id
        journal = dispute.company_id.stripe_journal_id

        # Since the dispute_object here is returned without any expended variable
        # we need to request balance_transactions.
        response = make_request_stripe_proxy(
            dispute.company_id.sudo(),
            'disputes/{dispute_id}',
            route_params={'dispute_id': dispute_object['id']},
            payload={
                'account': dispute.company_id.sudo().stripe_id,
                'expand[0]': 'balance_transactions',
            },
            method='GET',
        )
        balance_txns = response.get('balance_transactions', [])
        if movement_type == 'reinstated':
            net = sum(bt['net'] for bt in balance_txns if bt['net'] > 0)
            amount = format_amount_from_stripe(net, stripe_currency)
            name = self.env._("Reversal of stripe transaction %(tr_id)s", tr_id=dispute_object['id'])
        else:
            net = sum(bt['net'] for bt in balance_txns if bt['net'] < 0)
            amount = format_amount_from_stripe(net, stripe_currency)
            name = self.env._("Rescission of stripe transaction %(tr_id)s", tr_id=dispute_object['id'])

        date = date_utils.datetime.fromtimestamp(dispute_object['created'])

        if not self.env['account.bank.statement.line'].search([('stripe_id', '=', dispute_object['id']), ('amount', '=', amount)], limit=1):
            moves = self._prepare_moves_for_dispute(dispute, amount, date=date)
            if not moves:
                raise UserError(
                    self.env._(
                        "Error when processing the dispute %(dispute_id)s, no moves were created",
                        dispute_id=dispute_object['id'],
                    )
                )
            stmt_line = self.create({
                'name': name,
                'stripe_id': dispute_object["id"],
                'date': date,
                'journal_id': journal.id,
                'payment_ref': self.env._("Dispute funds %(movement_type)s", movement_type=movement_type),
                'amount': amount,
            })

            lines_to_reconcile = moves.line_ids.filtered(lambda line: line.account_id.reconcile)
            account = lines_to_reconcile.account_id
            if len(account) == 1:
                # Reconcile only simple cases where the account is unique, otherwise we skip the automation
                _liquidity_lines, suspense_lines, _other_lines = stmt_line._seek_for_lines()
                suspense_lines.write({'account_id': account.id})
                self.env['account.move.line']._reconcile_plan([suspense_lines + lines_to_reconcile])

            for expense in dispute.expense_ids:
                expense.message_post(body=stmt_line._get_html_link(self.env._(
                    'Dispute funds %(movement_type)s',
                    movement_type=movement_type,
                )))

    @api.model
    def _prepare_moves_for_dispute(self, dispute, movement_amount, date=None):
        journal = dispute.company_id.stripe_journal_id

        new_moves = self.env['account.move']

        expenses_to_process = dispute.expense_ids.filtered(
            # Currency may not be the right one, but infinite or negative rate doesn't exist so it's still valid
            lambda exp: (
                exp.dispute_currency_id.compare_amounts(exp.disputed_amount, 0) != 0
                # Error in the setup, can't handle that case the move must be made by hand
                and exp.account_move_id
            )
        )
        if not expenses_to_process:
            return new_moves

        allocated = 0
        expense_shares = []
        total_disputed = sum(e.disputed_amount for e in expenses_to_process)
        *first_expenses_to_process, last_expense_to_process = expenses_to_process
        for expense in first_expenses_to_process:
            share = expense.dispute_currency_id.round(movement_amount * expense.disputed_amount / total_disputed)
            allocated += share
            expense_shares.append(share)
        expense_shares.append(last_expense_to_process.dispute_currency_id.round(movement_amount - allocated))

        for expense, amount in zip(expenses_to_process, expense_shares, strict=True):
            if expense.dispute_currency_id.compare_amounts(amount, 0) == 0:
                continue

            expense_move = expense.account_move_id

            AccountTax = self.env['account.tax']
            base_aml = expense_move.line_ids.filtered(lambda line: line.account_type == 'expense' and not line.tax_repartition_line_id)
            base_lines = [{**expense_move._prepare_product_base_line_for_taxes_computation(base_aml), 'special_mode': 'total_excluded'}]
            tax_amls = expense_move.line_ids.filtered('tax_repartition_line_id')
            tax_lines = [expense_move._prepare_tax_line_for_taxes_computation(tax_aml) for tax_aml in tax_amls]
            AccountTax._add_tax_details_in_base_lines(base_lines, dispute.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, dispute.company_id, tax_lines=tax_lines)

            dp_base_lines = AccountTax._prepare_down_payment_lines(
                base_lines=base_lines,
                company=dispute.company_id,
                amount_type='fixed',
                amount=amount,
            )

            AccountTax._add_accounting_data_in_base_lines_tax_details(dp_base_lines, dispute.company_id, include_caba_tags=True)
            tax_results = AccountTax._prepare_tax_lines(
                base_lines=dp_base_lines,
                company=dispute.company_id,
                tax_lines=tax_lines,
            )

            # Base line.
            move_lines = []
            base_move_line = {}
            for base_line, to_update in tax_results['base_lines_to_update']:
                base_move_line = {
                    'name': expense._get_move_line_name(),
                    'account_id': base_line['account_id'].id,
                    'product_id': base_line['product_id'].id,
                    'analytic_distribution': base_line['analytic_distribution'],
                    'tax_ids': [Command.set(base_line['tax_ids'].ids)],
                    'tax_tag_ids': to_update['tax_tag_ids'],
                    'balance': -to_update['balance'],  # reversal
                    'partner_id': expense.vendor_id.id,
                }
                move_lines.append(base_move_line)

            # Tax lines.
            total_tax_line_balance = 0.0
            for tax_line in tax_results['tax_lines_to_add']:
                # since the original move was posted on the currency of the merchant, we need to switch
                # to the currency amount to get the have the amount in the currency of the stripe journal
                tax_line['balance'] = -tax_line['amount_currency']
                del tax_line['amount_currency']
                del tax_line['currency_id']
                total_tax_line_balance += tax_line['balance']
                move_lines.append(tax_line)
            # since there should be only one base line, we can adjust its balance to avoid rounding issues
            base_move_line['balance'] = -amount - total_tax_line_balance

            # Outstanding payment line.
            move_lines.append({
                'name': expense._get_move_line_name(),
                'account_id': expense._get_expense_account_destination(),
                'balance': amount,
                'partner_id': expense.vendor_id.id,
            })
            move_vals = {
                **expense._prepare_move_vals(),
                'date': date or fields.Date.context_today(self),
                'ref': self.env._("Reversal of %(name)s", name=expense_move.name),
                'journal_id': journal.id,
                'partner_id': expense.vendor_id.id,
                'line_ids': [Command.create(line) for line in move_lines],
                'currency_id': expense.dispute_currency_id.id,
                'expense_ids': [],  # otherwise we have multiple moves linked to the same expense and the Journal Entry smart button breaks
            }

            new_move = self.env['account.move'].create(move_vals)
            new_move.action_post()
            new_moves |= new_move

        return new_moves
