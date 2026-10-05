# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class HrExpense(models.Model):
    _inherit = "hr.expense"

    payment_mode = fields.Selection(
        selection_add=[('payslip_account', 'Employee (Through a Payslip)')],
        ondelete={'payslip_account': 'cascade'},
    )
    refund_in_payslip = fields.Boolean(string="Reimburse In Next Payslip")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip", readonly=True, index='btree_not_null')

    def _compute_is_editable(self):
        """ Add the condition that an expense is not editable if it is linked to a payslip."""
        # EXTENDS hr_expense
        super()._compute_is_editable()
        for expense in self:
            expense.is_editable = expense.is_editable and not expense.payslip_id

    @api.depends('payslip_id.state')
    def _compute_state(self):
        # EXTENDS hr_expense
        to_update = self.filtered(lambda exp: exp.payment_mode == 'payslip_account' and exp.existing_bill_id and exp.account_move_id)
        for expense in to_update:
            move = expense.account_move_id
            if move.state == 'cancel':
                expense.state = 'paid'
            elif move.state == 'draft':
                expense.state = 'approved'
            elif expense.payslip_id and expense.payslip_id.state in ['draft', 'validated']:
                expense.state = 'posted'
            elif expense.payslip_id and expense.payslip_id.state == 'paid':
                expense.state = 'paid'
            else:
                expense.state = expense.approval_state or 'draft'

        super(HrExpense, self - to_update)._compute_state()

    def _get_correct_salary_rule_per_expense(self, structure):
        """ If the expense is to be reimbursed in the payslip, we need to get the right salary rule linked to the expense's product
        and the payslip's structure.

        :param structure: `hr.payroll.structure` linked to the payslip, as an expense may be reimbursed through different structures
        :return: a mapping dictionary {expense: salary_rule} containing only valid expenses and rules
        :rtype: dict
        """

        valid_rule_per_expense = {}
        for expense in self:
            valid_rule_per_expense[expense] = expense.product_id.salary_rule_ids.filtered(
                lambda rule: structure in rule.struct_ids
                and rule.account_debit.account_type == 'liability_payable'
                and rule.account_debit.reconcile
            )[:1]

        return valid_rule_per_expense

    def _create_move(self):
        # EXTENDS hr_expense
        payslip_expenses = self.filtered(lambda expense: expense.payment_mode == 'payslip_account')
        if payslip_expenses:
            payslip_expenses._report_in_next_payslip()
        return super(HrExpense, self - payslip_expenses)._create_move()

    def action_refuse(self):
        # EXTENDS hr_expense
        res = super().action_refuse()
        self.sudo().refund_in_payslip = False  # Because we check the access rights in write
        return res

    def action_reset(self):
        # EXTENDS hr_expense
        if any(slip.state in {'validated', 'paid'} for slip in self.payslip_id):
            raise UserError(_(
                "You cannot remove an expense from a payslip that has already been validated.\n"
                "Expenses can only be removed from draft or canceled payslips."
            ))
        self.sudo().action_remove_from_payslip()
        res = super().action_reset()
        return res

    def _report_in_next_payslip(self):
        """ Allow the report to be included in the next employee payslip computation. """
        if not self:
            raise UserError(_("There are no valid expenses selected."))
        if self.filtered(lambda expense: expense.state not in {'approved', 'posted'} or expense.payment_mode != 'payslip_account'):
            raise UserError(_("Only approved and posted expenses with payslip reimbursement can be reported in the next payslip."))

        unmatched_expenses = self.filtered(
            lambda expense: (
                not expense.product_id.salary_rule_ids
                or (
                    all(struct.country_id for struct in expense.product_id.salary_rule_ids.struct_ids)
                    and expense.employee_id.company_country_id not in expense.product_id.salary_rule_ids.mapped("country_id")
                )
            )
        )
        if unmatched_expenses:
            raise UserError(
                self.env._("Please add a Salary Rule belonging to Expense Product \"%(name)s\" to report its expenses in the next payslip",
                name=unmatched_expenses[0].product_id.name)
            )

        # Do not raise if already reported, just ignore it
        to_report = self.filtered(lambda expense: not expense.refund_in_payslip)
        to_report.refund_in_payslip = True
        debt_transfer_entry_vals = self._prepare_linked_bill_paid_in_salary_payment_vals()
        if debt_transfer_entry_vals:
            # Create the debt transfer entry to transfer debt from vendor to employee (through his payslip)
            moves_sudo = self.env['account.move'].sudo().create(debt_transfer_entry_vals)
            moves_sudo.action_post()
            for move_sudo in moves_sudo:
                debt_transfer_line = move_sudo.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'liability_payable' and l.balance > 0
                )
                existing_bill_line = debt_transfer_line.expense_id.existing_bill_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'liability_payable'
                )
                if debt_transfer_line and existing_bill_line:
                    (debt_transfer_line + existing_bill_line).reconcile()

        for record in to_report:
            record.message_post(
                body=_('Expense ("%(name)s") will be added to the next payslip.', name=record.name),
                partner_ids=record.employee_id.user_id.partner_id.ids,
                email_layout_xmlid='mail.mail_notification_light',
                subtype_id=self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
            )

    def action_remove_from_payslip(self):
        """
            Disallow the expense to be included to the next employee payslip computation and/or unlink it from its payslip if possible.
        """
        valid_expenses = self.filtered(
            lambda expense: not expense.payslip_id or (not expense.payslip_id.move_id and expense.payslip_id.state in {'draft', 'cancel'})
        )
        # Don't raise in case of batch action for smooth flow
        if not valid_expenses:
            raise UserError(_(
                "You cannot remove an expense from a payslip that has already been validated.\n"
                "Expenses can only be removed from draft or canceled payslips."
            ))
        previous_payslips = valid_expenses.payslip_id
        # Only edit & post message when really needed
        expenses_to_edit = valid_expenses.filtered(lambda expense: expense.payslip_id or expense.refund_in_payslip)
        for expense in expenses_to_edit:
            expense.message_post(
                body=_('Expense ("%(name)s") was removed from the next payslip.', name=expense.name),
                partner_ids=expense.employee_id.user_id.partner_id.ids,
                email_layout_xmlid='mail.mail_notification_light',
                subtype_id=expense.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
            )
        expenses_to_edit.payslip_id = False
        if previous_payslips:
            # Remove the expenses amounts from the payslips
            previous_payslips._update_expense_input_line_ids()

    def action_open_payslip(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payslip'),
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'res_id': self.payslip_id.id,
        }

    def action_open_account_move(self):
        # EXTENDS hr_expense
        self.ensure_one()
        if not (self.payment_mode == 'payslip_account' and self.existing_bill_id):
            return super().action_open_account_move()
        return self.account_move_id._get_records_action()

    def _post_without_wizard_payslip_mode(self):
        """ Post a payslip without any direct call for the wizard """
        # When a move has been deleted
        self._check_can_create_move()
        today = fields.Date.context_today(self)
        payslip_expenses = self.filtered(lambda expense: expense.payment_mode == 'payslip_account')

        for company, expenses in payslip_expenses.grouped('company_id').items():
            expenses = expenses.with_company(company)
            company_domain = self.env['account.journal']._check_company_domain(company)
            journal = (
                    company.expense_journal_id
                    or expenses.env['account.journal'].search([*company_domain, ('type', '=', 'purchase')], limit=1))
            expense_receipt_vals_list = [
                {
                    **new_receipt_vals,
                    'journal_id': journal.id,
                    'invoice_date': today,
                }
                for new_receipt_vals in expenses._prepare_receipts_vals()
            ]
            moves = self.env['account.move'].sudo().create(expense_receipt_vals_list)
            for move in moves:
                move._message_set_main_attachment_id(move.attachment_ids, force=True, filter_xml=False)
            moves.action_post()

    def _prepare_linked_bill_paid_in_salary_payment_vals(self):
        expenses = self.filtered(
            lambda expense: expense.payment_mode == 'payslip_account'
                and expense.existing_bill_id
                and not any(expense.existing_bill_id.line_ids.mapped('reconciled'))
        )
        if not expenses:
            return

        payment_vals = []
        for expense in expenses:
            salary_rules = expense.product_id.salary_rule_ids.filtered(lambda sr: sr.account_debit and sr.account_debit.account_type == 'liability_payable')
            account_id = salary_rules.account_debit.id or expense.account_id.id
            move_lines = [
                {
                    'name': expense._get_move_line_name(),
                    'account_id': expense.account_id.id,
                    'expense_id': expense.id,
                    'amount_currency': expense.total_amount_currency,
                    'balance': expense.total_amount,
                    'currency_id': expense.currency_id.id,
                    'partner_id': expense.vendor_id.id,
                },
                {
                    'name': expense._get_move_line_name(),
                    'account_id': account_id,
                    'expense_id': expense.id,
                    'amount_currency': -expense.total_amount_currency,
                    'balance': -expense.total_amount,
                    'currency_id': expense.currency_id.id,
                    'partner_id': expense.employee_id.user_id.partner_id.id,
                },
            ]
            payment_vals.append({
                **expense._prepare_move_vals(),
                'date': expense.date or fields.Date.context_today(expense),
                'ref': expense.name,
                'move_type': 'entry',
                'currency_id': expense.currency_id.id,
                'company_id': expense.company_id.id,
                'line_ids': [Command.create(line) for line in move_lines],
            })

        return payment_vals

    def write(self, vals):
        if (
                vals.get('refund_in_payslip')
                and not self.env.user.has_groups(
                    'account.group_account_invoice,'
                    'hr_payroll.group_hr_payroll_user,'
                )
                and not self.env.su
        ):
            raise UserError(_("You do not have permission to add this expense to a payslip."))
        return super().write(vals)
