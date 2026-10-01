import calendar
from contextlib import contextmanager
from itertools import chain
from dateutil.relativedelta import relativedelta
import logging
import markupsafe
import re

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.fields import Command, Domain
from odoo.tools import SQL, float_compare, frozendict
from odoo.tools.misc import formatLang


_logger = logging.getLogger(__name__)


DEFERRED_DATE_MIN = '1900-01-01'
DEFERRED_DATE_MAX = '9999-12-31'


class AccountMove(models.Model):
    _inherit = "account.move"

    # Technical field to keep the value of payment_state when switching from invoicing to accounting
    # (using invoicing_switch_threshold setting field). It allows keeping the former payment state, so that
    # we can restore it if the user misconfigured the switch date and wants to change it.
    payment_state_before_switch = fields.Char(string="Payment State Before Switch", copy=False)

    # Deferred management fields
    deferred_move_ids = fields.Many2many(
        string="Deferred Entries",
        comodel_name='account.move',
        relation='account_move_deferred_rel',
        column1='original_move_id',
        column2='deferred_move_id',
        help="The deferred entries created by this invoice",
        copy=False,
    )
    deferred_original_move_ids = fields.Many2many(
        string="Original Invoices",
        comodel_name='account.move',
        relation='account_move_deferred_rel',
        column1='deferred_move_id',
        column2='original_move_id',
        help="The original invoices that created the deferred entries",
        copy=False,
    )
    deferred_entry_type = fields.Selection(
        string="Deferred Entry Type",
        selection=[
            ('expense', 'Deferred Expense'),
            ('revenue', 'Deferred Revenue'),
            ('misc', 'Deferred Miscellaneous'),
        ],
        compute='_compute_deferred_entry_type',
        copy=False,
    )

    signing_user = fields.Many2one(
        string='Signer',
        comodel_name='res.users',
        compute='_compute_signing_user', store=True,
        copy=False,
    )
    show_signature_area = fields.Boolean(compute='_compute_signature')
    signature = fields.Binary(compute='_compute_signature')  # can't be `related`: the sign module might not be there

    @api.depends('state', 'move_type', 'invoice_user_id')
    def _compute_signing_user(self):
        other_moves = self.filtered(lambda move: not move.is_sale_document())
        other_moves.signing_user = False

        is_odoobot_user = self.env.user == self.env.ref('base.user_root')
        is_backend_user = self.env.user.has_group('base.group_user')

        for invoice in (self - other_moves).filtered(lambda inv: inv.state == 'posted'):
            # signer priority:
            #   - res.user set in res.settings
            #   - real backend user posting the invoice
            #   - if odoobot: the person that initiated the invoice ie: The salesman
            #   - if invoice initiated by a portal user -> No signature
            representative = invoice.company_id.signing_user
            # checking `has_group('base.group_user')` ensure we never keep a portal user to sign
            if is_odoobot_user:
                user_can_sign = invoice.invoice_user_id and invoice.invoice_user_id.has_group('base.group_user')
                invoice.signing_user = representative or invoice.invoice_user_id if user_can_sign else False
            else:
                invoice.signing_user = representative or self.env.user if is_backend_user else False

    @api.depends('state')
    def _compute_signature(self):
        is_portal_user = self.env.user.has_group('base.group_portal')
        # Checking `company_id.sign_invoice` removes the needs to check if the sign module is installed
        # Setting it to True through `res.settings` auto install the sign module
        moves_not_to_sign = self.filtered(
            lambda inv: not inv.company_id.sign_invoice
                        or inv.state in {'draft', 'cancel'}
                        or not inv.is_sale_document()
                        # Allow signature for portal user only if the invoice already went through the send&print workflow
                        or (is_portal_user and not inv.invoice_pdf_report_id)
        )
        moves_not_to_sign.show_signature_area = False
        moves_not_to_sign.signature = None

        invoice_with_signature = self - moves_not_to_sign
        invoice_with_signature.show_signature_area = True
        for invoice in invoice_with_signature:
            invoice.signature = invoice.signing_user.sudo().sign_signature

    def _post(self, soft=True):
        # Deferred management
        posted = super()._post(soft)
        for move in self:
            if move._get_deferred_entries_method() == 'on_validation' and any(move.line_ids.mapped('deferred_start_date')):
                move._generate_deferred_entries()
        return posted

    def button_draft(self):
        if any(len(deferral_move.deferred_original_move_ids) > 1 for deferral_move in self.deferred_move_ids):
            raise UserError(_("You cannot reset to draft an invoice that is grouped in deferral entry. You can create a credit note instead."))
        reversed_moves = self.deferred_move_ids._unlink_or_reverse()
        if reversed_moves:
            for move in reversed_moves:
                move.with_context(skip_readonly_check=True).write({
                    'date':  move._get_accounting_date(move.date, move._affect_tax_report()),
                })
            self.deferred_move_ids |= reversed_moves
        return super().button_draft()

    def unlink(self):
        # Prevent deferred moves under audit trail restriction from being unlinked
        deferral_moves = self.filtered(lambda move: move._is_protected_by_audit_trail() and move.deferred_original_move_ids)
        deferral_moves.deferred_original_move_ids.deferred_move_ids = False
        deferral_moves._reverse_moves()
        return super(AccountMove, self - deferral_moves).unlink()

    # ============================= START - Deferred Management ====================================

    def _get_deferred_entries_method(self):
        self.ensure_one()
        if self.is_entry():
            move_types = set(self.line_ids.filtered('deferred_start_date').account_id.mapped("internal_group"))
            if (
                "expense" in move_types and "income" in move_types
                and self.company_id.generate_deferred_expense_entries_method != self.company_id.generate_deferred_revenue_entries_method
            ):
                raise UserError(self.env._(
                    "Having different deferred entries generation methods for expenses and revenues is not supported on "
                    "journal entries involving both expense and revenue accounts. You can split this entry into two entries instead."
                ))
            elif "expense" in move_types:
                return self.company_id.generate_deferred_expense_entries_method
            else:
                return self.company_id.generate_deferred_revenue_entries_method
        if self.is_purchase_document():
            return self.company_id.generate_deferred_expense_entries_method
        return self.company_id.generate_deferred_revenue_entries_method

    def _get_deferred_entries_periodicity(self):
        self.ensure_one()
        if self.is_outbound():
            return self.company_id.deferred_expense_periodicity
        return self.company_id.deferred_revenue_periodicity

    @api.depends('deferred_original_move_ids')
    def _compute_deferred_entry_type(self):
        for move in self:
            if move.deferred_original_move_ids:
                move_types = set(move.deferred_original_move_ids.mapped('move_type'))
                if len(move_types) > 1 or move.deferred_original_move_ids[0].is_entry():
                    move.deferred_entry_type = 'misc'
                elif move.deferred_original_move_ids[0].is_purchase_document():
                    move.deferred_entry_type = 'expense'
                else:
                    move.deferred_entry_type = 'revenue'
            else:
                move.deferred_entry_type = False

    @api.model
    def _get_deferred_diff_dates(self, start, end):
        """
        Returns the number of months between two dates [start, end[
        The computation is done by using months of 30 days so that the deferred amount for february
        (28-29 days), march (31 days) and april (30 days) are all the same (in case of monthly computation).
        See test_deferred_management_get_diff_dates for examples.
        """
        if start > end:
            start, end = end, start
        nb_months = end.month - start.month + 12 * (end.year - start.year)
        start_day, end_day = start.day, end.day
        if start_day == calendar.monthrange(start.year, start.month)[1]:
            start_day = 30
        if end_day == calendar.monthrange(end.year, end.month)[1]:
            end_day = 30
        nb_days = end_day - start_day
        return (nb_months * 30 + nb_days) / 30

    @api.model
    def _get_deferred_period_amount(self, method, period_start, period_end, line_start, line_end, balance):
        """
        Returns the amount to defer for the given period taking into account the deferred method (day/month/full_months).
        """
        if period_end <= line_start or period_end <= period_start:
            return 0  # invalid period
        if method == 'day':
            amount_per_day = balance / (line_end - line_start).days
            return (period_end - period_start).days * amount_per_day
        elif method in ('month', 'full_months'):
            if method == 'full_months':
                reset_day_1 = relativedelta(day=1)
                line_start, line_end = line_start + reset_day_1, line_end + reset_day_1
                period_start, period_end = period_start + reset_day_1, period_end + reset_day_1
            line_diff = self._get_deferred_diff_dates(line_end, line_start)
            period_diff = self._get_deferred_diff_dates(period_end, period_start)
            return period_diff / line_diff * balance if line_diff else balance

    @api.model
    def _get_deferred_amounts_by_line(self, lines, periods, deferred_type):
        """
        :return: a list of dictionaries containing the deferred amounts for each line and each period
        E.g. (where period1 = (date1, date2, label1), period2 = (date2, date3, label2), ...)
        [
            {'account_id': 1, period_1: 100, period_2: 200},
            {'account_id': 1, period_1: 100, period_2: 200},
            {'account_id': 2, period_1: 300, period_2: 400},
        ]
        """
        values = []
        for line in lines:
            line_start = fields.Date.to_date(line['deferred_start_date'])
            line_end = fields.Date.to_date(line['deferred_end_date'])
            if line_end < line_start:
                # This normally shouldn't happen, but if it does, would cause calculation errors later on.
                # To not make the reports crash, we just set both dates to the same day.
                # The user should fix the dates manually.
                line_end = line_start

            columns = {}
            for period in periods:
                if period[2] == 'not_started' and line_start <= period[0]:
                    # The 'Not Started' column only considers lines starting the deferral after the report end date
                    columns[period] = 0.0
                    continue
                # periods = [Total, Not Started, Before, ..., Current, ..., Later]
                # The dates to calculate the amount for the current period
                period_start = max(period[0], line_start)
                period_end = min(period[1], line_end) + relativedelta(days=1)  # +1 to include  end date of report

                columns[period] = self._get_deferred_period_amount(
                    self.env.company.deferred_expense_amount_computation_method if deferred_type == "expense" else self.env.company.deferred_revenue_amount_computation_method,
                    period_start, period_end,
                    line_start, line_end + relativedelta(days=1),  # +1 to include the end date of the line
                    line['balance']
                )

            values.append({
                **self.env['account.move.line']._get_deferred_amounts_by_line_values(line),
                **columns,
            })
        return values

    @api.model
    def _get_deferred_lines(self, line, deferred_account, deferred_type, period, ref, force_balance=None, grouping_field='account_id'):
        """
        :return: a list of Command objects to create the deferred lines of a single given period
        """
        deferred_amounts = self._get_deferred_amounts_by_line(line, [period], deferred_type)[0]
        balance = deferred_amounts[period] if force_balance is None else force_balance
        return [
            Command.create({
                **self.env['account.move.line']._get_deferred_lines_values(account.id, coeff * balance, ref, line.analytic_distribution, line),
                'partner_id': line.partner_id.id,
                'product_id': line.product_id.id,
            })
            for (account, coeff) in [(deferred_amounts[grouping_field], 1), (deferred_account, -1)]
        ]

    def _generate_deferred_entries(self):
        """
        Generates the deferred entries for the invoice.
        """
        self.ensure_one()
        if self.state != 'posted':
            return

        for deferred_type in ('expense', 'revenue'):
            moves_vals_to_create = []
            lines_vals_to_create = []
            lines_periods = []
            lines = self.line_ids.filtered(lambda l: (
                l.account_id.internal_group == ('expense' if deferred_type == 'expense' else 'income')
                and l.deferred_start_date
                and l.deferred_end_date
            ))
            if not lines:
                continue

            company_deferred_account = self.company_id.deferred_expense_account_id if deferred_type == "expense" else self.company_id.deferred_revenue_account_id
            deferred_journal = self.company_id.deferred_expense_journal_id if deferred_type == "expense" else self.company_id.deferred_revenue_journal_id
            deferred_method = self.company_id.deferred_expense_amount_computation_method if deferred_type == "expense" else self.company_id.deferred_revenue_amount_computation_method
            if not deferred_journal:
                raise UserError(_("Please set the deferred journal in the accounting settings."))

            for line in lines:
                periods = line._get_deferred_periods()
                if not periods:
                    continue

                start_date = line.deferred_start_date
                end_date = line.deferred_end_date
                accounting_date = line.date

                # When using the 'full_months' computation method, every consumed month counts as a full month.
                # We therefore need to subtract one month from the end date for the following check on dates.
                if deferred_method == 'full_months':
                    # We need to add one day to the end date since it's excluded by _get_deferred_diff_dates().
                    if self._get_deferred_diff_dates(start_date.replace(day=1), end_date + relativedelta(days=1)) < 2:
                        end_date += relativedelta(months=-1)

                # When all move line dates (start, end, accounting) are within the same month, we skip the line.
                # It would otherwise lead to the creation of both a reversal and a deferral move that would cancel each other out.
                if start_date.replace(day=1) == end_date.replace(day=1) == accounting_date.replace(day=1):
                    continue

                ref = _("Deferral of %s", line.move_id.name or '')

                # Use the deferred account set on the related account if any, otherwise fall back on the company one.
                deferred_account = line.account_id.deferred_account_id or company_deferred_account
                if not deferred_account:
                    raise UserError(_("Please set a deferred account on the related account or in the accounting settings."))

                moves_vals_to_create.append({
                    'move_type': 'entry',
                    'deferred_original_move_ids': [Command.set(line.move_id.ids)],
                    'journal_id': deferred_journal.id,
                    'company_id': self.company_id.id,
                    'partner_id': line.partner_id.id,
                    'auto_post': 'at_date',
                    'ref': ref,
                    'name': False,
                    'date': line.move_id.date,
                })
                lines_vals_to_create.append([
                    {
                        **self.env['account.move.line']._get_deferred_lines_values(account.id, coeff * line.balance, ref, line.analytic_distribution, line),
                        'partner_id': line.partner_id.id,
                        'reconciled_lines_ids': line.ids if not line.reconciled and line.account_id == account else None,
                    }
                    for (account, coeff) in [(line.account_id, -1), (deferred_account, 1)]
                ])
                lines_periods.append((line, periods))
            # create the deferred moves
            moves_fully_deferred = self.create(moves_vals_to_create)
            # We write the lines after creation, to make sure the `deferred_original_move_ids` is set.
            # This way we can avoid adding taxes for deferred moves.
            for move_fully_deferred, lines_vals in zip(moves_fully_deferred, lines_vals_to_create):
                for line_vals in lines_vals:
                    # This will link the moves to the lines. Instead of move.write('line_ids': lines_ids)
                    line_vals['move_id'] = move_fully_deferred.id
            self.env['account.move.line'].create(list(chain(*lines_vals_to_create)))

            deferral_moves_vals = []
            deferral_moves_line_vals = []
            # Create the deferred entries for the periods [deferred_start_date, deferred_end_date]
            for (line, periods), move_vals in zip(lines_periods, moves_vals_to_create):
                deferred_account = line.account_id.deferred_account_id or company_deferred_account
                remaining_balance = line.balance
                for period_index, period in enumerate(periods):
                    # For the last deferral move the balance is forced to remaining balance to avoid rounding errors
                    force_balance = remaining_balance if period_index == len(periods) - 1 else None
                    deferred_amounts = self._get_deferred_amounts_by_line(line, [period], deferred_type)[0]
                    balance = deferred_amounts[period] if force_balance is None else force_balance
                    remaining_balance -= line.currency_id.round(balance)
                    deferral_moves_vals.append({**move_vals, 'date': period[1]})
                    deferral_moves_line_vals.append([
                        {
                            **self.env['account.move.line']._get_deferred_lines_values(account.id, coeff * balance, move_vals['ref'], line.analytic_distribution, line),
                            'partner_id': line.partner_id.id,
                            'product_id': line.product_id.id,
                        }
                        for (account, coeff) in [(deferred_amounts['account_id'], 1), (deferred_account, -1)]
                    ])

            deferral_moves = self.create(deferral_moves_vals)
            for deferral_move, lines_vals in zip(deferral_moves, deferral_moves_line_vals):
                for line_vals in lines_vals:
                    # This will link the moves to the lines. Instead of move.write('line_ids': lines_ids)
                    line_vals['move_id'] = deferral_move.id
            self.env['account.move.line'].create(list(chain(*deferral_moves_line_vals)))

            # Avoid having deferral moves with a total amount of 0.
            to_unlink = deferral_moves.filtered(lambda move: move.currency_id.is_zero(move.amount_total))
            to_unlink.unlink()

            (moves_fully_deferred + deferral_moves - to_unlink)._post(soft=True)

    def open_deferred_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Deferred Entries"),
            'res_model': 'account.move.line',
            'domain': [('id', 'in', self.deferred_move_ids.line_ids.ids)],
            'views': [(self.env.ref('account_accountant.view_deferred_entries_tree').id, 'list')],
            'context': {
                'search_default_group_by_move': True,
                'expand': True,
            }
        }

    def open_deferred_original_entry(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _("Original Deferred Entries"),
            'res_model': 'account.move.line',
            'domain': [('id', 'in', self.deferred_original_move_ids.line_ids.ids)],
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'search_default_group_by_move': True,
                'expand': True,
            }
        }
        if len(self.deferred_original_move_ids) == 1:
            action.update({
                'res_model': 'account.move',
                'res_id': self.deferred_original_move_ids[0].id,
                'views': [(False, 'form')],
            })
        return action

    # ============================= END - Deferred management ======================================

    def action_open_bank_reconciliation_widget(self):
        return self.statement_line_id._action_open_bank_reconciliation_widget(
            default_context={
                'search_default_journal_id': self.statement_line_id.journal_id.id,
                'search_default_statement_line_id': self.statement_line_id.id,
                'default_st_line_id': self.statement_line_id.id,
            }
        )

    def action_open_bank_reconciliation_widget_statement(self):
        return self.statement_line_id._action_open_bank_reconciliation_widget(
            extra_domain=[('statement_id', 'in', self.statement_id.ids)],
        )

    def action_open_business_doc(self):
        if self.statement_line_id:
            return self.action_open_bank_reconciliation_widget()
        else:
            action = super().action_open_business_doc()
            # prevent propagation of the following keys
            action['context'] = action.get('context', {}) | {
                'preferred_aml_value': None,
                'preferred_aml_currency_id': None,
            }
            return action

    def _get_mail_thread_data_attachments(self):
        res = super()._get_mail_thread_data_attachments()
        res += self.statement_line_id.statement_id.attachment_ids
        return res

    @contextmanager
    def _get_edi_creation(self):
        with super()._get_edi_creation() as move:
            previous_lines = move.invoice_line_ids
            yield move.with_context(disable_onchange_name_predictive=['all'])  # noqa: RUF075
            for line in move.invoice_line_ids - previous_lines:
                line._onchange_name_predictive()

    def _get_outstanding_bank_statement_lines_domain(self):
        """
        Returns a search domain for move lines for unreconciled bank payments
        linked to this move's partner.
        """
        self.ensure_one()
        return [
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', self.commercial_partner_id.id),
                ('partner_id', '!=', False),
                ('account_id.account_type', '=', 'asset_cash'),
                ('journal_id', 'in', self.env['account.journal']._search([
                    *self.env['account.journal']._check_company_domain(self.company_id.id),
                    ('type', '=', 'bank')
                ])),
                ('balance', '>' if self.is_inbound() else '<', 0.0),
                ('statement_line_id', '!=', False),
                ('move_id.line_ids', 'any', [
                    ('account_id', '=', self.company_id.account_journal_suspense_account_id.id),
                    ('reconciled', '=', False),
                ]),
            ]

    def _compute_payments_widget_to_reconcile_info(self):
        # EXTENDS 'account'
        super()._compute_payments_widget_to_reconcile_info()
        for move in self:
            if move.state not in {'draft', 'posted'} \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True) \
                    or not move.partner_id:
                continue

            bank_domain = [
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('partner_id', '!=', False),
                ('account_id.account_type', '=', 'asset_cash'),
                ('journal_id', 'in', self.env['account.journal']._search([
                        *self.env['account.journal']._check_company_domain(move.company_id.id),
                        ('type', '=', 'bank')
                    ])),
                ('balance', '>' if move.is_inbound() else '<', 0.0),
                ('statement_line_id', '!=', False),
                ('move_id.line_ids', 'any', [
                    ('account_id', '=', move.company_id.account_journal_suspense_account_id.id),
                    ('reconciled', '=', False),
                ]),
            ]

            payments_widget_vals = {
                'outstanding': True,
                'content': [],
                'move_id': move.id,
                'title': _('Outstanding credits') if move.is_inbound() else _('Outstanding debits')
            }

            for line in self.env['account.move.line'].search(bank_domain):
                st_line = line.statement_line_id
                currency = st_line.foreign_currency_id or st_line.currency_id
                amount = currency._convert(
                    from_amount=abs(st_line.amount_residual),
                    to_currency=move.currency_id,
                    company=move.company_id,
                    date=line.date,
                )
                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'bank_label': line.name if line.journal_id.type == 'bank' else False,
                    'move_name': line.move_id.name,
                    'amount': amount,
                    'currency_id': move.currency_id.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                    'ref': line.ref,
                })

            if payments_widget_vals['content']:
                widget = move.invoice_outstanding_credits_debits_widget
                if widget:
                    widget['content'].extend(payments_widget_vals['content'])
                    widget['content'].sort(key=lambda x: (x['date'], x['id']), reverse=True)
                else:
                    widget = payments_widget_vals
                move.invoice_outstanding_credits_debits_widget = widget

    def _get_partner_credit_warning_exclude_amount(self):
        # EXTENDS 'account'
        exclude_amount = super()._get_partner_credit_warning_exclude_amount()
        bank_domain = self._get_outstanding_bank_statement_lines_domain()
        for line in self.env['account.move.line'].search(bank_domain):
            currency = line.statement_line_id.foreign_currency_id or line.statement_line_id.currency_id
            exclude_amount += currency._convert(
                from_amount=abs(line.statement_line_id.amount_residual),
                to_currency=self.company_id.currency_id,
                company=self.company_id,
                date=line.date,
            )

        matched_credits = self.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable').matched_credit_ids
        if matched_credits:
            bank_line_amount = sum(matched_credits.mapped('amount'))
            payment_date = max(matched_credits.mapped('max_date'))
            amount_company = matched_credits[0].credit_currency_id._convert(
                from_amount=bank_line_amount,
                to_currency=self.company_id.currency_id,
                company=self.company_id,
                date=payment_date,
            )
            exclude_amount += amount_company

        return exclude_amount

    def js_assign_outstanding_line(self, line_id):
        # EXTENDS
        super().js_assign_outstanding_line(line_id)
        line = self.env['account.move.line'].browse(line_id)
        if line.account_id.account_type == 'asset_cash' and line.statement_line_id:
            return line.statement_line_id.with_context(
                skip_payment_tolerance=True,
                stop_reco_at_first_partial=True,
            ).set_line_bank_statement_line(self.line_ids.filtered(lambda line: line.account_id.account_type in {'asset_receivable', 'liability_payable'}).ids)

    def js_remove_outstanding_partial(self, partial_id):
        # EXTENDS
        if st_line := self.statement_line_id:
            partial = self.env['account.partial.reconcile'].browse(partial_id)
            st_line.delete_reconciled_line((partial.credit_move_id + partial.debit_move_id).filtered(lambda m: m.display_type != 'payment_term').ids)
        else:
            super().js_remove_outstanding_partial(partial_id)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    move_attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachment')

    # Deferred management fields
    deferred_start_date = fields.Date(
        string="Start Date",
        compute='_compute_deferred_start_date', store=True, readonly=False,
        index='btree_not_null',
        copy=False,
        help="Date at which the deferred expense/revenue starts"
    )
    deferred_end_date = fields.Date(
        string="End Date",
        index='btree_not_null',
        copy=False,
        help="Date at which the deferred expense/revenue ends"
    )
    has_deferred_moves = fields.Boolean(compute='_compute_has_deferred_moves')
    has_abnormal_deferred_dates = fields.Boolean(compute='_compute_has_abnormal_deferred_dates')
    is_deferred_account = fields.Boolean(related='account_id.is_deferred')

    full_amount_switch_html = fields.Html(compute='_compute_full_amount_switch_html')

    def _order_to_sql(self, table, order, reverse=False):
        sql_order = super()._order_to_sql(table, order, reverse)
        preferred_aml_residual_value = self.env.context.get('preferred_aml_value')
        preferred_aml_currency_id = self.env.context.get('preferred_aml_currency_id')
        if preferred_aml_residual_value and preferred_aml_currency_id and order == self._order:
            currency = self.env['res.currency'].browse(preferred_aml_currency_id)
            # using round since currency.round(55.55) = 55.550000000000004
            preferred_aml_residual_value = round(preferred_aml_residual_value, currency.decimal_places)
            return SQL(
                "ROUND(%(residual_currency)s, %(decimal_places)s) = %(value)s "
                "AND %(currency)s = %(currency_id)s DESC, %(order)s",
                residual_currency=table.amount_residual_currency,
                decimal_places=currency.decimal_places,
                value=preferred_aml_residual_value,
                currency=table.currency_id,
                currency_id=currency.id,
                order=sql_order,
            )
        return sql_order

    def copy_data(self, default=None):
        data_list = super().copy_data(default=default)
        for line, values in zip(self, data_list):
            if 'move_reverse_cancel' in self.env.context:
                values['deferred_start_date'] = line.deferred_start_date
                values['deferred_end_date'] = line.deferred_end_date
        return data_list

    def write(self, vals):
        """ Prevent changing the account of a move line when there are already deferral entries.
        """
        if 'account_id' in vals:
            for line in self:
                if (
                    line.has_deferred_moves
                    and line.deferred_start_date
                    and line.deferred_end_date
                    and vals['account_id'] != line.account_id.id
                ):
                    raise UserError(_(
                        "You cannot change the account for a deferred line in %(move_name)s if it has already been deferred.",
                        move_name=line.move_id.display_name
                    ))
        return super().write(vals)

    @api.depends('balance')
    def _compute_full_amount_switch_html(self):
        for line in self:
            # Ignore lines with no reconciled lines or not linked to a bank statement.
            if not (reconciled_lines := line.reconciled_lines_excluding_exchange_diff_ids) or len(reconciled_lines) > 1 or not line.statement_line_id:
                line.full_amount_switch_html = False
                continue

            is_invoice = reconciled_lines.move_id.is_invoice(include_receipts=True)
            btn_start = markupsafe.Markup("<a name='apply_full_amount' type='object' class='btn btn-link p-0 align-baseline'>")

            if reconciled_lines.currency_id.is_zero(reconciled_lines.amount_currency + line.amount_currency):
                lines = [
                    _("%(display_name_html)s will be entirely paid by the transaction.")
                    if is_invoice else
                    _("%(display_name_html)s will be fully reconciled by the transaction.")
                ]
                liquidity_line_amount_currency = line.move_id.line_ids.filtered(lambda line: line.account_id == line.move_id.journal_id.default_account_id).amount_currency
                # Means that we possibly want to come back to partial
                if float_compare(liquidity_line_amount_currency, reconciled_lines.amount_currency, 2) < 0:
                    btn_start = markupsafe.Markup("<a name='apply_partial_amount' type='object' class='btn btn-link p-0 align-baseline'>")
                    lines.append(
                        _("You might want to record a %(btn_start)spartial payment%(btn_end)s.")
                        if is_invoice else
                        _("You might want to make a %(btn_start)spartial reconciliation%(btn_end)s instead.")
                    )
            else:
                if is_invoice:
                    lines = [
                        _("%(display_name_html)s will be reduced by %(amount)s."),
                        _("You might want to set the invoice as %(btn_start)sfully paid%(btn_end)s."),
                    ]
                else:
                    lines = [
                        _("%(display_name_html)s will be reduced by %(amount)s."),
                        _("You might want to %(btn_start)sfully reconcile%(btn_end)s the document."),
                    ]

            # We need to use span instead of button here because button is not displayed otherwise
            display_name_html = markupsafe.Markup("""
                    <a name='action_redirect_to_move' type='object' class="btn btn-link p-0 align-baseline fst-italic">%(display_name)s</a>
                """) % {
                'display_name': reconciled_lines.move_id._get_move_display_name(show_ref=False),
            }

            extra_text = markupsafe.Markup("<br/>").join(lines) % {
                'amount': formatLang(self.env, line.amount_currency, currency_obj=line.currency_id),
                'display_name_html': display_name_html,
                'btn_start': btn_start,
                'btn_end': markupsafe.Markup("</a>"),
            }
            line.full_amount_switch_html = markupsafe.Markup("<div class='text-muted'>%s</div>") % extra_text

    # ============================= START - Deferred management ====================================
    def _compute_has_deferred_moves(self):
        for line in self:
            line.has_deferred_moves = line.move_id.deferred_move_ids

    @api.depends('deferred_start_date', 'deferred_end_date')
    def _compute_has_abnormal_deferred_dates(self):
        # In the deferred computations, we always assume that both the start and end date are inclusive
        # E.g: 1st January -> 31st December is *exactly* 1 year = 12 months
        # However, the user may instead put 1st January -> 1st January of next year which is then
        # 12 months + 1/30 month = 12.03 months which may result in odd amounts when deferrals are created
        # For this reason, we alert the user if we detect such a case
        # Other cases were the number of months is not round should not be handled.
        for line in self:
            line.has_abnormal_deferred_dates = (
                line.deferred_start_date
                and line.deferred_end_date
                and line.deferred_start_date != line.deferred_end_date
                and float_compare(
                    self.env['account.move']._get_deferred_diff_dates(line.deferred_start_date, line.deferred_end_date + relativedelta(days=1)) % 1,  # end date is included
                    1 / 30,
                    precision_digits=2
                ) == 0
            )

    def _has_deferred_compatible_account(self):
        self.ensure_one()
        return (
            self.move_id.is_purchase_document(include_receipts=True)
            and
            self.account_id.internal_group == 'expense'
        ) or (
            self.move_id.is_sale_document(include_receipts=True)
            and
            self.account_id.internal_group == 'income'
        ) or (
            self.move_id.is_entry()
            and
            self.account_id.internal_group in ('expense', 'income')
        )

    @api.onchange('deferred_start_date', 'account_id')
    def _onchange_deferred_start_date(self):
        if not self._has_deferred_compatible_account():
            self.deferred_start_date = False
        if self.deferred_start_date and not self.deferred_end_date:
            self.deferred_end_date = self.deferred_start_date

    @api.onchange('deferred_end_date', 'account_id')
    def _onchange_deferred_end_date(self):
        if not self._has_deferred_compatible_account():
            self.deferred_end_date = False
        if self.deferred_end_date and not self.deferred_start_date:
            self.deferred_start_date = self.deferred_end_date

    @api.depends('deferred_end_date', 'move_id.invoice_date', 'move_id.state')
    def _compute_deferred_start_date(self):
        for line in self:
            if not line.deferred_start_date and line.move_id.invoice_date and line.deferred_end_date:
                line.deferred_start_date = line.move_id.invoice_date

    @api.constrains('deferred_start_date', 'deferred_end_date', 'account_id')
    def _check_deferred_dates(self):
        for line in self:
            if line.deferred_start_date and not line.deferred_end_date:
                raise UserError(_("You cannot create a deferred entry with a start date but no end date."))
            elif line.deferred_start_date and line.deferred_end_date and line.deferred_start_date > line.deferred_end_date:
                raise UserError(_("You cannot create a deferred entry with a start date later than the end date."))

    @api.model
    def _get_deferred_ends_of_month(self, start_date, end_date):
        """
        :return: a list of dates corresponding to the end of each month between start_date and end_date.
            See test_get_ends_of_month for examples.
        """
        dates = []
        while start_date <= end_date:
            start_date = start_date + relativedelta(day=31)  # Go to end of month
            dates.append(start_date)
            start_date = start_date + relativedelta(days=1)  # Go to first day of next month
        return dates

    @api.model
    def _get_deferred_ends_of_year(self, start_date, end_date):
        """
        :return: a list of dates corresponding to the end of each year between start_date and end_date.
            See test_get_ends_of_year for examples.
        """
        dates = []
        date_end_of_year = start_date
        while date_end_of_year <= end_date:
            date_end_of_year = self.env.company.compute_fiscalyear_dates(date_end_of_year)['date_to']  # Go to end of fiscal year
            dates.append(date_end_of_year)
            date_end_of_year += relativedelta(days=1)  # Add one day to be in the next fiscal year
        return dates

    def _get_deferred_periods(self):
        """
        :return: a list of tuples (start_date, end_date) during which the deferred expense/revenue is spread.
            If there is only one period containing the move date, it means that we don't need to defer the
            expense/revenue since the invoice deferral and its deferred entry will be created on the same day and will
            thus cancel each other.
        """
        self.ensure_one()
        if self.move_id._get_deferred_entries_periodicity() == 'month':
            periods = [
                (max(self.deferred_start_date, date.replace(day=1)), min(date, self.deferred_end_date), 'current')
                for date in self._get_deferred_ends_of_month(self.deferred_start_date, self.deferred_end_date)
            ]
        elif self.move_id._get_deferred_entries_periodicity() == 'year':
            periods = [
                (max(self.deferred_start_date, self.company_id.compute_fiscalyear_dates(date)['date_from']), min(date, self.deferred_end_date), 'current')
                for date in self._get_deferred_ends_of_year(self.deferred_start_date, self.deferred_end_date)
            ]
        if not periods or len(periods) == 1 and periods[0][0].replace(day=1) == self.date.replace(day=1):
            return []
        else:
            return periods

    @api.model
    def _get_deferred_amounts_by_line_values(self, line):
        return {
            'account_id': line['account_id'],
            # line either be a dict with ids (coming from SQL query), or a real account.move.line object
            'product_id': line['product_id'] if isinstance(line, dict) else line['product_id'].id,
            'product_category_id': line['product_category_id'] if isinstance(line, dict) else line['product_category_id'].id,
            'balance': line['balance'],
            'move_id': line['move_id'],
        }

    @api.model
    def _get_deferred_lines_values(self, account_id, balance, ref, analytic_distribution, line=None):
        return {
            'account_id': account_id,
            # line either be a dict with ids (coming from SQL query), or a real account.move.line object
            'product_id': line['product_id'] if isinstance(line, dict) else line['product_id'].id,
            'product_category_id': line['product_category_id'] if isinstance(line, dict) else line['product_category_id'].id,
            'balance': balance,
            'name': ref,
            'analytic_distribution': analytic_distribution,
        }

    # ============================= END - Deferred management ====================================

    def _get_computed_taxes(self):
        if self.move_id.deferred_original_move_ids:
            # If this line is part of a deferral move, do not (re)calculate its taxes automatically.
            # Doing so might unvoluntarily impact the tax report in deferral moves (if a default tax is set on the account).
            return self.tax_ids
        return super()._get_computed_taxes()

    def _compute_attachment(self):
        id_model2attachments = {
            (res_model, res_id): attachments
            for res_model, res_id, attachments in self.env['ir.attachment']._read_group(
                domain=Domain.OR(self._get_attachment_domains()),
                groupby=['res_model', 'res_id'],
                aggregates=['id:recordset'],
            )
        }

        for record in self:
            record.move_attachment_ids = self._get_attachment_by_record(id_model2attachments, record)

    def action_reconcile(self):
        """ This function is called by the 'Reconcile' button of account.move.line's
        list view. It performs reconciliation between the selected lines.
        - If the reconciliation can be done directly we do it silently
        - Else, if a write-off is required we open the wizard to let the client enter required information
        """
        self = self.filtered(lambda x: x.balance or x.amount_currency)  # noqa: PLW0642
        if not self:
            return

        wizard = self.env['account.reconcile.wizard'].with_context(
            active_model='account.move.line',
            active_ids=self.ids,
        ).new({})
        return wizard._action_open_wizard() if (wizard.is_write_off_required or wizard.force_partials) else wizard.reconcile()

    def action_split_lines(self):
        return {
            'name': _("Split"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.split.journal.item.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_ids': [Command.set(self.ids)],
            },
        }

    def _get_predict_postgres_dictionary(self):
        lang = self.env.context.get('lang') and self.env.context.get('lang')[:2]
        return {'fr': 'french'}.get(lang, 'english')

    def _get_predictive_domain(self, move):
        return [
            ('state', '=', 'posted'),
            ('move_type', '=', move.move_type),
            ('partner_id', '=', move.partner_id.id),
            ('company_id', '=', move.journal_id.company_id.id or self.env.company.id),
        ]

    @api.model
    def _build_predictive_query(self, move, line_domain=()):
        move_ids = self.env['account.move'].search(
            self._get_predictive_domain(move),
            order='invoice_date desc, id desc',
            limit=self.env["ir.config_parameter"].sudo().get_int("account.bill.predict.history.limit") or 100,
        ).ids
        return self.env['account.move.line']._search([
            ('move_id', 'in', move_ids),
            ('display_type', '=', 'product'),
        ] + list(line_domain), bypass_access=True)

    @api.model
    def _get_predicted_values(self, name, move, line_domain=()):
        r"""Predict the most likely value based on the previous history.

        This method uses postgres tsvector in order to try to deduce a field of
        an invoice line based on the text entered into the name (description)
        field and the partner linked.
        We only limit the search on the previous 100 entries, which according
        to our tests bore the best results. However this limit parameter is
        configurable by creating a config parameter with the key:
        account.bill.predict.history.limit

        :param name: the label to match for in the history
        :param move: the record of the move owning the line, used to filter on similar moves
        :param line_domain: a domain to restrict the candidate lines to match
        """
        if not name:
            return {}

        cache = self.env.cr.cache.setdefault('account_move_prediction', {})
        cache_key = frozendict(name=name, line_domain=line_domain, move_domain=self._get_predictive_domain(move))
        if cache_key in cache:
            return cache[cache_key]
        psql_lang = self._get_predict_postgres_dictionary()
        parsed_description = re.sub(r"[*&()|!':<>=%/~@,.;$\[\]]+", " ", name)
        parsed_description = ' | '.join(parsed_description.split())
        getters = self.with_company(move.journal_id.company_id or self.env.company)._predictive_field_getter()
        sql_getters = SQL(', ').join(sql for fname, formatter, sql in getters)

        try:
            aml_query = self._build_predictive_query(move, line_domain)
            if result := self.env.execute_query_dict(SQL("""
                      WITH account_move_line AS (%(account_move_line)s),
                           source AS (%(source)s)
                    SELECT %(getters)s,
                           ts_rank(source.document, query_plain) AS rank
                      FROM source, to_tsquery(%(lang)s, %(description)s) query_plain
                  ORDER BY rank DESC, invoice_date DESC, id DESC
                     LIMIT 1
                """,
                account_move_line=aml_query.select(SQL('*')),  # force the query planner to only consider the max limit
                source=aml_query.select(
                    SQL("account_move_line.*"),
                    SQL(
                        "setweight(to_tsvector(%s, CONCAT_WS(' ', %s, %s)), 'B') AS document",
                        psql_lang,
                        aml_query.table.product_id.name,
                        aml_query.table.name,
                    ),
                ),
                getters=sql_getters,
                lang=psql_lang,
                description=parsed_description,
            )):
                cache[cache_key] = {
                    fname: formatter(result[0][fname])
                    for fname, formatter, sql in getters
                }
                return cache[cache_key]
        except Exception:
            # In case there is an error while parsing the to_tsquery (wrong character for example)
            # We don't want to have a blocking traceback, instead return False
            _logger.exception('Error while predicting invoice line fields')
        return {}

    def _predictive_field_getter(self):
        """Return the list of fields to predict and how to retrieve them from a result row.

        Each entry is a (fname, formatter, sql) tuple where:
        - fname: the name of the field on account.move.line to set
        - formatter: a callable to convert the raw SQL value into the expected
            Python value (e.g. a browse method to get a recordset)
        - sql: a SQL expression to select the value from an account_move_line
            row, using the columns of the account_move_line CTE defined
            in _get_predicted_values
        """
        getters = [
            ('product_id', self.env['product.product'].browse, SQL("""(
                SELECT product_product.id
                  FROM product_product
                 WHERE product_product.id = source.product_id
                   AND product_product.active
            ) AS product_id""")),
            ('account_id', self.env['account.account'].browse, SQL("""(
                SELECT account_account.id
                  FROM account_account
                 WHERE account_account.id = source.account_id
                   AND account_account.active
            ) AS account_id""")),
            ('tax_ids', self.env['account.tax'].browse, SQL("""(
                SELECT ARRAY_AGG(account_tax_id)
                  FROM account_move_line_account_tax_rel rel
                  JOIN account_tax account_tax ON account_tax.id = rel.account_tax_id
                 WHERE rel.account_move_line_id = source.id
                   AND account_tax.active IS NOT FALSE
            ) AS tax_ids""")),
            ('analytic_distribution', lambda v: v, SQL("analytic_distribution")),
        ]
        if self.env.user.has_groups('account.group_partial_purchase_deductibility'):
            getters.append(('deductible_percentage', lambda v: v, SQL("deductible_percentage")))
        return getters

    @api.onchange('name')
    def _onchange_name_predictive(self):
        disabled_fields = set(self.env.context.get('disable_onchange_name_predictive', []))
        if (
            'all' not in disabled_fields
            and (self.move_id.quick_edit_mode or self.move_id.is_purchase_document(include_receipts=True))
            and self.display_type == 'product'
            and self.name
            and self.partner_id
            and (not self.move_id.name or self.move_id.name == '/')
        ):
            predicted_values = self._get_predicted_values(self.name, self.move_id)
            protected_fields = ['price_unit', 'account_id', 'tax_ids', 'name']
            to_update = {fname: value for fname, value in predicted_values.items() if fname not in disabled_fields}
            to_protect = [self._fields[fname] for fname in protected_fields if self[fname] and fname not in to_update]
            with self.env.protecting(to_protect, self):
                self.update(to_update)

    def _read_group_select(self, table, aggregate_spec):
        # Enable to use HAVING clause that sum rounded values depending on the
        # currency precision settings. Limitation: we only handle a having
        # clause of one element with that specific method :sum_rounded.
        fname, __, func = models.parse_read_group_spec(aggregate_spec)
        if func != 'sum_rounded':
            return super()._read_group_select(table, aggregate_spec)

        return SQL(
            'SUM(ROUND(%s, %s))',
            table[fname],
            table._sudo().currency_id.decimal_places,
        )

    def _read_group_groupby(self, table, groupby_spec):
        # enable grouping by :abs_rounded on fields, which is useful when trying
        # to match positive and negative amounts
        if ':' in groupby_spec:
            fname, method = groupby_spec.split(':')
            if method == 'abs_rounded':
                # rounds with the used currency settings
                return SQL(
                    'ROUND(ABS(%s), %s)',
                    table[fname],
                    table._sudo().currency_id.decimal_places,
                )

        return super()._read_group_groupby(table, groupby_spec)

    def onchange(self, values, field_names, fields_spec):
        return super(AccountMoveLine, self.with_context(
            disable_onchange_name_predictive=list(values) if self.id else [],
            disable_onchange_add_to_compute='name' in field_names,
        )).onchange(values, field_names, fields_spec)

    def _conditional_add_to_compute(self, fname, condition):
        if self.env.context.get('disable_onchange_add_to_compute'):
            # In the case where the account/product is modified by the predictive, we do not want
            # to trigger the onchange/inverse methods in chain. There are indeed triggered after
            # the snapshot comparison, outside of the `protecting`` context manager used in
            # `_onchange_name_predictive`
            return
        super()._conditional_add_to_compute(fname, condition)
