# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # EXTENDS account
        # In the case where an expense is reimbursed through an employee's payslip, we need to reconcile the move generated
        # for the expense and the one generated for the payslip, so the expense can be set to 'paid'
        # and only one payment shall be made, the payslip one. If the moves have been altered, the automatic reconciliation may not be done,
        # it will be done manually by an accountant. We will keep the temporary matching data to simplify that case.
        lines_to_reconcile = self.env['account.move.line']
        if not self.env.context.get('skip_reconcile_expense_with_payslip') and self.sudo().payslip_ids.expense_ids:
            self = self.with_context(skip_reconcile_expense_with_payslip=True)  # noqa: PLW0642 Avoid entering here recursively
            lines_to_reconcile = self._hr_payroll_expense_prepare_move_lines_to_reconcile()

        res = super()._post(soft=soft)  # Posting will automatically reconcile same-account-same-matching lines

        lines_to_reconcile = lines_to_reconcile.filtered(lambda line: not line.reconciled)
        if lines_to_reconcile:
            # Tries to reconcile move lines automatically (to mark the expense as paid)
            wizard = self.env['account.reconcile.wizard'].with_context(
                active_model='account.move.line',
                active_ids=lines_to_reconcile.ids,
            ).new({})
            if not (wizard.is_write_off_required or wizard.force_partials):  # Only reconcile if there are no issue that requires user-input
                wizard.reconcile()
        return res

    def unlink(self):
        # EXTENDS account
        self.check_access('unlink')
        expense_moves_sudo = self.sudo().payslip_ids.expense_ids.account_move_id
        if expense_moves_sudo:
            # Unlink or reverse the move between the expense move and the payslip move
            reconciled_payslip_lines_sudo = self.sudo().line_ids.filtered('reconciled')
            reconciled_expense_lines_sudo = expense_moves_sudo.line_ids.filtered('reconciled')

            in_between_moves = reconciled_payslip_lines_sudo.reconciled_lines_ids.move_id & reconciled_expense_lines_sudo.reconciled_lines_ids.move_id
            if in_between_moves:
                in_between_moves._unlink_or_reverse()

        return super().unlink()

    @api.ondelete(at_uninstall=False)
    def _remove_payslip_and_refund_in_payslip(self):
        """
        As the @api.ondelete in hr_expense will set the expense state to submitted, we need to clear
        payslip_id and refund_in_payslip so that it's not included in the payslip
        """
        expense_to_reset_ids = []
        for move in self:
            if any(move.expense_ids.mapped('payslip_id')):
                expense_to_reset_ids += move.expense_ids.ids
        for expense in self.env['hr.expense'].browse(expense_to_reset_ids):
            expense.write({
                'payslip_id': False,
                'refund_in_payslip': False,
            })

    def _hr_payroll_expense_prepare_move_lines_to_reconcile(self):
        """
            (Create if None &) Post the expense's move and prepare it to be reconciled with the payslip move,
            as the expense is reimbursed to the employee through the payslip.
            This ensures the payment state of the expense, its report, and move are set to 'paid'.
        """
        if not self.env.is_superuser() and not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(_("You don't have the access rights to post an invoice."))

        payslips_sudo = self.sudo().payslip_ids
        all_payslip_expenses_sudo = payslips_sudo.expense_ids
        if not all_payslip_expenses_sudo:
            return self.env['account.move.line']  # No payslip or expenses, no reason to continue

        expenses_without_moves = all_payslip_expenses_sudo.filtered(lambda expense: not expense.account_move_id)
        if expenses_without_moves:
            expenses_without_moves._post_without_wizard_payslip_mode()  # Only valid case to bypass the wizard

        # Prepare the reconciliation by grouping expenses per payslip move
        payslip_move_to_expense_map = {}

        # Handles the case where an account move linked to an expense is already paid, ignoring the fact that it was flagged to be paid here
        # (They will get paid twice, but it's the user's responsibility)
        valid_expense_states = {'approved', 'posted'}
        valid_expenses_sudo = all_payslip_expenses_sudo.filtered(lambda expense: expense.state in valid_expense_states)
        for payslip_sudo, expenses_sudo in valid_expenses_sudo.grouped('payslip_id').items():
            rules = expenses_sudo.product_id.salary_rule_ids.filtered(lambda rule: payslip_sudo.struct_id in rule.struct_ids)
            for rule in rules:
                if not rule.with_company(payslip_sudo.company_id).account_debit:
                    raise UserError(self.env._(
                        "No debit account found in the '%(rule_name)s' payslip salary rule. Please add a payable debit account "
                        "to be able to create an accounting entry for the expenses linked to this payslip.",
                        rule_name=rule.name,
                    ))

                if rule.with_company(payslip_sudo.company_id).account_debit.account_type != 'liability_payable':
                    raise UserError(self.env._(
                        "The '%(account_name)s' account for the salary rule '%(rule_name)s' must be of type 'Payable'.",
                        account_name=rule.with_company(payslip_sudo.company_id).account_debit.name,
                        rule_name=rule.name,
                    ))
            payslip_move_to_expense_map.setdefault(payslip_sudo.move_id, {'moves_sudo': self.env['account.move'].sudo(), 'accounts': self.env['account.account']})
            payslip_move_to_expense_map[payslip_sudo.move_id]['moves_sudo'] |= expenses_sudo.sorted().account_move_id
            payslip_move_to_expense_map[payslip_sudo.move_id]['accounts'] |= rules.with_company(payslip_sudo.company_id).account_debit

        # Prepare and collect the reconciliation lines
        lines_to_reconcile_sudo = self.env['account.move.line']
        for idx, payslip_move_sudo in enumerate(payslip_move_to_expense_map):
            # Get the payslip move lines generated for the expenses
            payslip_account_ids = payslip_move_to_expense_map[payslip_move_sudo]['accounts'].ids
            lines_to_match_sudo = payslip_move_sudo.line_ids.filtered(
                lambda aml: aml.account_id.id in payslip_account_ids and aml.display_type != 'payment_term'
            )

            # Get the corresponding payable lines for the expenses
            # In the case of a payslip_account with existing bill, the expense_move is a debt transfer
            # entry with 2 payable lines, so we need to filter on partner id to get the right line
            expense_moves_sudo = payslip_move_to_expense_map[payslip_move_sudo]['moves_sudo']
            lines_to_match_sudo |= expense_moves_sudo.line_ids.filtered(
                lambda aml: aml.account_id.account_type == 'liability_payable'
                and (aml.partner_id == aml.expense_id.employee_id.user_id.partner_id if aml.expense_id.payment_mode == 'payslip_account' else True)
            )

            # Use the matching number system to simplify reconciliation, the number itself is just made to be unique
            lines_to_match_sudo.matching_number = f'{idx:0>10}-{payslip_move_sudo.id}-{min(expense_moves_sudo.ids)}'
            lines_to_reconcile_sudo |= lines_to_match_sudo

        # Post all expense moves that aren't posted already
        expense_moves_to_post_sudo = all_payslip_expenses_sudo.account_move_id.filtered(lambda move: move.state == 'draft')
        if expense_moves_to_post_sudo:
            expense_moves_to_post_sudo._post(soft=False)

        # If we have more than 2 accounts, we will not be able to reconcile
        if len(lines_to_reconcile_sudo.account_id) > 2:
            return self.env['account.move.line']

        # Return all the account move lines to be reconciled in the previous sudo state, sorted to facilitate the pairing
        return lines_to_reconcile_sudo.sorted(lambda line: abs(line.balance)).sudo(self.env.is_superuser())
