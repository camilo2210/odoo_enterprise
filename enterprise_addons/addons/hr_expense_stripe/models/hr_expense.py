import datetime
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.fields import Domain

from odoo.addons.hr_expense_stripe.utils import format_amount_from_stripe


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    stripe_authorization_id = fields.Char("Stripe Authorization ID", index='btree_not_null', copy=False, readonly=True)
    stripe_transaction_id = fields.Char("Stripe Transaction ID", index='btree_not_null', copy=False, readonly=True)
    card_id = fields.Many2one(
        comodel_name='hr.expense.stripe.card',
        string="Card",
        readonly=True,
        copy=False,
        groups='base.group_user',
        index=True,
    )
    mcc_tag_id = fields.Many2one(comodel_name='product.mcc.stripe.tag', copy=False, readonly=True)
    is_card_expense = fields.Boolean(compute='_compute_is_card_expense', readonly=True, compute_sudo=True)
    dispute_id = fields.Many2one(comodel_name='hr.expense.stripe.dispute', readonly=True, copy=False, index='btree')
    dispute_currency_id = fields.Many2one(
        string="Dispute Currency",
        comodel_name='res.currency',
        related='dispute_id.currency_id',
    )
    disputed_amount = fields.Monetary(
        string='Disputed Amount',
        currency_field='dispute_currency_id',
        copy=False,
        readonly=True,
    )

    @api.constrains('disputed_amount')
    def _check_disputed_amount(self):
        for expense in self:
            if expense.dispute_currency_id:
                expense_amount = expense.currency_id._convert(
                    from_amount=expense.total_amount_currency,
                    to_currency=expense.dispute_currency_id,
                    company=expense.company_id,
                )
                if expense.dispute_currency_id.compare_amounts(expense.disputed_amount, expense_amount) > 0:
                    raise ValidationError(self.env._("The disputed amount cannot be greater than the expense amount."))
                elif expense.dispute_currency_id.compare_amounts(expense.disputed_amount, 0) < 0:
                    raise ValidationError(self.env._("The disputed amount cannot be negative."))

    @api.ondelete(at_uninstall=False)
    def _prevent_unlinking_card_expense(self):
        """ If deleted, it may be created again by a stripe event anyway, this ensures the data is accepted """
        card_expenses = self.filtered('is_card_expense')
        if card_expenses and not self.env.su:
            raise ValidationError(_("You cannot delete an expense that was created from a Stripe card transaction."))

    @api.depends('card_id')
    def _compute_is_card_expense(self):
        """ Because the `card_id` field is locked behind access rights, we need to have a safe way to know
        if an expense is created from a card payment or not
        """
        for expense in self:
            expense.is_card_expense = bool(expense.card_id)

    def copy_data(self, default=None):
        if any(self.mapped('is_card_expense')) and not self.env.context.get('from_split_wizard'):
            raise UserError(self.env._("You cannot duplicate an expense that was created from a Stripe card transaction."))

        return super().copy_data(default=default)

    def _get_default_responsible_for_approval(self):
        # EXTEND hr_expense to bypass approval for expenses created from a stripe authorization
        self.ensure_one()
        if self.sudo().card_id:
            return self.env['res.users']
        else:
            return super()._get_default_responsible_for_approval()

    def _can_be_autovalidated(self):
        # EXTEND hr_expense to bypass approval for expenses created from a stripe authorization
        return super()._can_be_autovalidated() or bool(self.sudo().card_id)

    def _do_approve(self):
        # EXTEND hr_expense to bypass approval for expenses created from a stripe authorization
        expenses_from_stripe = self.filtered(lambda exp: exp.sudo().card_id and exp.state in {'submitted', 'draft'})
        for expense in expenses_from_stripe:
            expense.sudo().write({
                'approval_state': 'approved',
                'manager_id': False,
                'approval_date': fields.Datetime().now(),
            })
        expenses_from_stripe.update_activities_and_mails()
        expenses_from_stripe._create_move()
        super(HrExpense, self - expenses_from_stripe)._do_approve()

    def _fetch_create_partner_from_stripe(self, merchant_data):
        """ DEPRECATED  """
        return False

    @api.model
    def _create_from_stripe_authorization(self, auth_object, refusal_reason=None):
        """ Create an expense from a stripe `authorization.request` event, refused if refusal_reason is specified.
        """
        merchant_data = auth_object['merchant_data']
        amount_object = auth_object['pending_request'] or auth_object  # The key is always present, but the value may be empty
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', auth_object['card']['id'])], limit=1)
        if not card:
            raise UserError(_("An Expense card that doesn't exist on the database was used"))

        expense = self.env['hr.expense'].search([('stripe_authorization_id', '=', auth_object['id'])], limit=1)
        if expense and not refusal_reason:
            # We don't update expenses that are refused because they may be reversed (their amount would be set to 0)
            expense._update_from_stripe_authorization(auth_object)
        elif not expense:
            # Create the expense if it doesn't exist yet, which should be the common case
            # when receiving the event `issuing_authorization.created`
            card = card.with_company(card.company_id)
            domain = Domain('can_be_expensed', '=', True)
            domain &= Domain('stripe_mcc_ids', 'any', [('code', '=', merchant_data['category_code'])])
            product = self.env['product.product'].search(domain, limit=1)
            amount_company_currency = amount_currency = format_amount_from_stripe(amount_object['amount'], card.currency_id)
            merchant_currency = (
                self.env['res.currency'].with_context(active_test=False).search([
                        ('name', '=ilike', amount_object['merchant_currency']),
                    ],
                    limit=1,
                )
                or card.currency_id
            )
            if merchant_currency and not merchant_currency.active:
                merchant_currency.active = True
            if merchant_currency != card.currency_id:
                amount_currency = format_amount_from_stripe(amount_object['merchant_amount'], merchant_currency)

            mcc_tag = self.env['product.mcc.stripe.tag'].search([('code', '=', merchant_data['category_code'])], limit=1)
            create_dict = {
                'payment_mode': 'company_account',
                'name': merchant_data['name'],
                'employee_id': card.employee_id.id,
                'card_id': card.id,
                'mcc_tag_id': mcc_tag.id,
                'manager_id': False,
                'stripe_authorization_id': auth_object['id'],
                'stripe_transaction_id': False,
                'product_id': product and product.id,
                'total_amount': amount_company_currency,
                'total_amount_currency': amount_currency,
                'currency_id': merchant_currency.id,
                'journal_id': card.journal_id.id,
                'payment_method_line_id': card.payment_method_line_id.id,
            }
            expense = self.env['hr.expense'].with_company(card.company_id).with_context(lang=card.user_id.lang or self.env.lang).create([create_dict])

        if refusal_reason and expense.state != 'refused':
            # Refused and reversed authorizations should be refused in Odoo as well
            expense._do_refuse(refusal_reason or self.env._("Expense was refused by Stripe, or an error occurred"))
        else:
            # Ask the user to upload the receipt
            expense._stripe_create_user_activity()
        return expense

    def _update_from_stripe_authorization(self, auth_object):
        """
            Update the expense when the event `issuing_authorization.updated` is received,
            (rare, it means the vendor updated the authorization)
            or when `issuing_authorization.created` is received, following an approved `issuing_authorization.request`
             """
        if not self:
            return

        update_vals = {}
        card = self.card_id
        amount_company_currency = amount_currency = format_amount_from_stripe(auth_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=ilike', auth_object['merchant_currency']),
                ],
                limit=1,
            )
            or card.currency_id
        )
        if not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != self.company_currency_id:
            amount_currency = format_amount_from_stripe(auth_object['merchant_amount'], merchant_currency)

        if merchant_currency != self.currency_id:
            update_vals['currency_id'] = merchant_currency.id

        most_recent_expense = self.sorted('date')[-1]
        if len(self) == 1:
            if self.company_currency_id.compare_amounts(amount_company_currency, self.total_amount) != 0:
                update_vals['total_amount'] = amount_company_currency

            if merchant_currency.compare_amounts(amount_currency, self.total_amount_currency) != 0:
                update_vals['total_amount_currency'] = amount_currency
        else:
            all_expenses_total_amount = sum(self.mapped('total_amount'))
            older_expenses = self - most_recent_expense
            if self.company_currency_id.compare_amounts(amount_company_currency, all_expenses_total_amount) != 0:
                update_vals['total_amount'] = amount_company_currency - sum(older_expenses.mapped('total_amount'))

            all_expenses_total_amount_currency = sum(self.mapped('total_amount_currency'))
            if merchant_currency.compare_amounts(amount_currency, all_expenses_total_amount_currency) != 0:
                update_vals['total_amount_currency'] = amount_currency - sum(older_expenses.mapped('total_amount_currency'))

        if update_vals:
            most_recent_expense.write(update_vals)

    @api.model
    def _create_from_stripe_transaction(self, tr_object, split_id=False):
        """ Create an expense from the event `issuing_transaction.created` (when it is a direct capture),
        which may happen in rare cases (when you buy something on a plane, there can be no authorization due to a lack of connection)
        """
        merchant_data = tr_object['merchant_data']
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', tr_object['card'])], limit=1)
        if not card:
            raise UserError(_("An Expense card that doesn't exist on the database was used"))
        card = card.with_company(card.company_id)

        domain = Domain('can_be_expensed', '=', True)
        domain &= Domain('stripe_mcc_ids', 'any', [('code', '=', merchant_data['category_code'])])
        product = (
            self.env['product.product'].search(domain)
            or self.env.ref('hr_expense.product_product_no_cost', raise_if_not_found=False)
        )

        amount_currency = amount_company_currency = -format_amount_from_stripe(tr_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=ilike', tr_object['merchant_currency']),
                ],
                limit=1,
            )
            or card.currency_id
        )
        if merchant_currency and not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != card.currency_id:
            amount_currency = -format_amount_from_stripe(tr_object['merchant_amount'], merchant_currency)
        mcc_tag = self.env['product.mcc.stripe.tag'].search([('code', '=', tr_object['merchant_data']['category_code'])], limit=1)
        authorization = tr_object['authorization'] or {}
        if isinstance(authorization, str):
            authorization = {'id': authorization}

        create_dict = {
            'payment_mode': 'company_account',
            'name': merchant_data['name'],
            'employee_id': card.employee_id.id,
            'card_id': card.id,
            'mcc_tag_id': mcc_tag.id,
            'manager_id': False,
            'currency_id': merchant_currency.id,
            'stripe_authorization_id': authorization.get('id', False),
            'stripe_transaction_id': tr_object['id'],
            'payment_method_line_id': card.payment_method_line_id and card.payment_method_line_id.id,
            'product_id': product.id,
            'total_amount': amount_company_currency,
            'total_amount_currency': amount_currency,
            'split_expense_origin_id': split_id,
        }
        new_expense = self.env['hr.expense'].with_company(card.company_id).with_context(lang=card.user_id.lang or self.env.lang).create([create_dict])
        new_expense._stripe_create_user_activity()

    def _update_from_stripe_transaction(self, tr_object):
        """ When the event `issuing_transaction.updated` is received, which shouldn't be common
        or `issuing_transaction.created` (payment is captured)
        """
        self.ensure_one()
        update_vals = {}
        card = self.card_id
        amount_company_currency = amount_currency = -format_amount_from_stripe(tr_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=ilike', tr_object['merchant_currency']),
                ],
                limit=1,
        )
            or card.currency_id
        )
        if not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != self.company_currency_id:
            amount_currency = -format_amount_from_stripe(tr_object['merchant_amount'], merchant_currency)

        if merchant_currency != self.currency_id:
            update_vals['currency_id'] = merchant_currency.id

        if self.company_currency_id.compare_amounts(amount_company_currency, self.total_amount) != 0:
            update_vals['total_amount'] = amount_company_currency

        if merchant_currency.compare_amounts(amount_currency, self.total_amount_currency) != 0:
            update_vals['total_amount_currency'] = amount_currency

        if not self.stripe_transaction_id:
            update_vals['stripe_transaction_id'] = tr_object['id']

        authorization_id = tr_object['authorization']
        if authorization_id and authorization_id != self.stripe_authorization_id:
            update_vals['stripe_authorization_id'] = authorization_id

        if update_vals:
            self.write(update_vals)

    @api.model
    def _stripe_cancel_expense_or_reverse_move(self, tr_object):
        """ This handles the case where an expense is updated but already had a move """
        if not self:
            raise ValidationError(_("Stripe Credit transfers are not implemented"))
        self.ensure_one()
        transaction_amount = -format_amount_from_stripe(tr_object['amount'], self.company_currency_id)
        transaction_amount_in_currency = -format_amount_from_stripe(tr_object['merchant_amount'], self.currency_id)
        remaining_amount = self.total_amount - transaction_amount
        remaining_amount_in_currency = self.total_amount_currency - transaction_amount_in_currency
        move = self.account_move_id
        if move:
            move._reverse_moves(cancel=True)
        self.with_context(lang=self.card_id.user_id.lang or self.env.lang)._do_refuse(self.env._("Expense was refunded by vendor"))
        if not self.company_currency_id.is_zero(remaining_amount):
            self.with_context(lang=self.card_id.user_id.lang or self.env.lang).copy({
                'manager_id': False,
                'stripe_transaction_id': tr_object['id'],
                'total_amount': remaining_amount,
                'total_amount_currency': remaining_amount_in_currency,
                'split_expense_origin_id': self.id,
            })

    def _stripe_create_user_activity(self):
        """ Creates an activity to remind the employee they have to upload the payment receipt """
        for expense in self.filtered(lambda exp: exp.card_id and exp.state != 'refused'):
            expense.activity_schedule(
                act_type_xmlid='mail.mail_activity_data_upload_document',
                date_deadline=fields.Date.context_today(expense),
                summary=_("Please upload the receipt."),
                user_id=expense.employee_id.user_id.id,
            )

    def _reconcile_stripe_payments(self, existing_statement_lines=False):
        """ When an expense paid by the company is posted, its payment could be reconciled with the bank statement line if it already exists
        """
        expenses_per_stripe_transaction_id = self.grouped('stripe_transaction_id')
        if not existing_statement_lines:
            existing_statement_lines = dict(self.env['account.bank.statement.line']._read_group(
                domain=[('stripe_id', 'in', tuple(expenses_per_stripe_transaction_id.keys()))],
                groupby=['stripe_id'],
                aggregates=['id:recordset'],
            ))
        for stripe_transaction_id, statement_line in existing_statement_lines.items():
            expenses_for_transaction = expenses_per_stripe_transaction_id[stripe_transaction_id]
            if any(statement_line.mapped('is_reconciled')) or any(expense.state != 'paid' for expense in expenses_for_transaction):
                # Skipping automation of tricky corner cases
                continue
            moves_to_reconcile = expenses_for_transaction.account_move_id
            lines_to_reconcile = moves_to_reconcile.line_ids.filtered(lambda line: line.account_id.reconcile)
            account = lines_to_reconcile.account_id
            if len(account) != 1:
                # Skipping automation of tricky corner cases
                continue

            _unused, suspense_lines, _unused = statement_line._seek_for_lines()
            suspense_lines.write({'account_id': account.id})
            self.env['account.move.line']._reconcile_plan([suspense_lines + lines_to_reconcile])

    @api.model
    def _dispute_force_captures(self, amount):
        currency = self.env.company.stripe_currency_id
        if currency.compare_amounts(amount, 0) <= 0:
            return

        expenses_to_dispute = self.env['hr.expense']
        expenses = self.env['hr.expense'].search([
                ('state', 'in', ('draft', 'approved', 'paid')),
                ('stripe_authorization_id', '=', False),  # Force captures don't have any authorizations
                ('stripe_transaction_id', '!=', False),
                ('company_id', '=', self.env.company.id),
                ('date', '>=', fields.Datetime.now() - datetime.timedelta(days=90)),  # Only expenses from the last 90 days can be disputed, as per Stripe's rules
                '|', ('dispute_id', '=', False), ('dispute_id.state', '=', 'unsubmitted'),
            ],
            order='date DESC',
            limit=200,  # No need to fetch them all
        )

        # Stripe allows only one dispute per transaction_id and splitting an expense in Odoo can generate multiple expenses
        # with the same transaction_id. We make sure they are all selected.
        transaction_ids = expenses.mapped('stripe_transaction_id')
        expenses |= self.env['hr.expense'].search([
            ('stripe_transaction_id', 'in', transaction_ids),
            ('company_id', '=', self.env.company.id)
        ])

        escape = False
        for transaction, expenses in expenses.grouped('stripe_transaction_id').items():
            for expense in expenses.sorted('stripe_transaction_id'):
                amount -= expense.currency_id._convert(
                    from_amount=expense.total_amount_currency,
                    to_currency=currency,
                    company=expense.company_id,
                )
                expenses_to_dispute += expense
                if currency.compare_amounts(amount, 0) <= 0:
                    escape = True
            if escape:
                break

        # Auto-posting and submitting since they are company paid expenses and need to create the payment with it's
        # accounting entry to be able to create the reverse move of the dispute.
        to_reset = expenses_to_dispute.filtered(lambda exp: exp.state == 'refused')
        if to_reset:
            to_reset._do_reset_approval()
            for expense in to_reset:
                expense.message_post(body=self.env._("Expense automatically reset to draft due to negative journal balance"))

        to_submit = expenses_to_dispute.filtered(lambda exp: exp.state == 'draft')
        if to_submit:
            to_submit.sudo().action_submit()
            for expense in to_submit:
                expense.message_post(body=self.env._("Expense automatically submitted due to negative journal balance"))

        to_approve = expenses_to_dispute.filtered(lambda exp: exp.state == 'submitted')
        if to_approve:
            to_approve._do_approve()
            for expense in to_approve:
                expense.message_post(body=self.env._("Expense automatically approved due to negative journal balance"))

        to_post = expenses_to_dispute.filtered(lambda exp: exp.state == 'approved')
        if to_post:
            to_post.account_move_id.origin_payment_id.action_post()
            for expense in to_post:
                expense.message_post(body=self.env._("Expense automatically posted due to negative balance"))

        expenses_per_transaction_id = defaultdict(lambda: self.env['hr.expense'])
        for expense in expenses_to_dispute.filtered(lambda exp: not exp.dispute_id):
            expenses_per_transaction_id[expense.stripe_transaction_id] |= expense

        new_disputes_vals = []
        for transaction_id, expenses in expenses_per_transaction_id.items():
            new_disputes_vals.append({
                'stripe_transaction_id': transaction_id,
                # Since the expenses have the same transaction_id, they have the same company / card
                'company_id': expenses.company_id.id,
                'card_id': expenses.card_id.id,
                # Stripe files and settles disputes in the card currency, never the merchant one
                'currency_id': expenses.card_id.currency_id.id,
                'expense_ids': [Command.set(expenses.ids)],
                'reason': 'no_valid_authorization',
                'explanation': self.env._("Dispute automatically created due to negative journal balance."),
            })

        if new_disputes_vals:
            new_disputes = self.env['hr.expense.stripe.dispute'].create(new_disputes_vals)
        else:
            return

        for expense in new_disputes.expense_ids:
            expense.disputed_amount = expense.currency_id._convert(
                expense.total_amount_currency,
                expense.dispute_currency_id,
                expense.company_id,
            )

        for dispute in new_disputes:
            dispute.with_context(automated_dispute=True).action_create_or_update_dispute()

        for dispute in new_disputes:
            dispute.action_submit()
            for expense in dispute.expense_ids:
                expense.message_post(body=self.env._("Dispute automatically created and submitted due to negative balance."))

    def write(self, vals):
        if 'is_card_expense' in vals:
            raise UserError(_("You cannot edit the security fields of an expense manually"))
        return super().write(vals)

    def action_create_dispute(self):
        self.ensure_one()
        if not self.stripe_transaction_id and not self.stripe_authorization_id:
            raise UserError(self.env._("You can only create a dispute for an expense linked to a Stripe transaction or authorization."))
        if not self.stripe_transaction_id:
            raise UserError(self.env._("Transaction must be captured to submit a dispute."))
        if not self.env.user.has_group('hr_expense.group_hr_expense_manager') and not self.dispute_id:
            raise UserError(self.env._(
                "You do not have the necessary access rights to file a dispute. "
                "Please contact your expense administrator to file the dispute."
            ))

        expenses = self.env['hr.expense'].search([('stripe_transaction_id', '=', self.stripe_transaction_id)])
        if len(expenses.currency_id) > 1:
            raise RedirectWarning(
                message=self.env._(
                    "Several expenses sharing the same stripe transaction id use different currencies. "
                    "Please verify the currencies of the expenses."
                ),
                action={
                    'type': 'ir.actions.act_window',
                    'name': self.env._("Linked expenses"),
                    'res_model': 'hr.expense',
                    'view_mode': 'list,form',
                    'domain': [('id', 'in', expenses.ids)],
                },
                button_text=self.env._("Go to expenses"),
            )
        dispute_currency = expenses.card_id.currency_id
        if len(expenses) == 1 and dispute_currency.is_zero(self.disputed_amount):
            self.disputed_amount = self.currency_id._convert(
                from_amount=self.total_amount_currency,
                to_currency=dispute_currency,
                company=self.company_id,
            )

        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Submit Dispute"),
            'res_model': 'hr.expense.stripe.dispute',
            'res_id': self.dispute_id.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_currency_id': dispute_currency.id,
                'default_stripe_transaction_id': self.stripe_transaction_id,
                'default_card_id': self.card_id.id,
                'default_expense_ids': expenses.ids,
                'default_company_id': self.company_id.id,
            },
        }

    def action_open_stripe_card(self):
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.expense.stripe.card',
            'target': 'current',
        }
        if len(self) > 1:
            action.update({
                'name': _("Stripe Cards"),
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.card_id.ids)],
            })
        else:
            action.update({
            'name': _("Stripe Card"),
            'view_mode': 'form',
            'res_id': self.card_id.id,
        })
        return action

    def action_submit(self):
        # EXTEND hr_expense
        if any(expense for expense in self if expense.state == 'draft' and expense.stripe_authorization_id and not expense.stripe_transaction_id):
            raise UserError(self.env._("You cannot submit an expense that is reserved. Please wait for the transaction to be captured."))
        return super().action_submit()

    def action_split_wizard(self):
        # EXTEND hr_expense
        self.ensure_one()
        if self.state == 'draft' and self.stripe_authorization_id and not self.stripe_transaction_id:
            raise UserError(self.env._("You cannot split an expense that is reserved. Please wait for the transaction to be captured."))
        return super().action_split_wizard()
