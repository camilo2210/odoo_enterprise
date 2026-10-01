# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    date = fields.Date('Accounting Date',
        help="Keep empty to use the period of the validation(Payslip) date.", compute="_compute_date", store=True, readonly=False)
    journal_id = fields.Many2one('account.journal', 'Salary Journal', related="struct_id.journal_id", check_company=True)
    move_id = fields.Many2one('account.move', 'Accounting Entry', readonly=True, copy=False, index='btree_not_null')
    move_state = fields.Selection(related='move_id.state', string='Move State', export_string_translation=False)
    batch_payroll_move_lines = fields.Boolean(related='company_id.batch_payroll_move_lines')

    @api.depends('paid_date', 'done_date')
    def _compute_date(self):
        for slip in self:
            slip.date = slip.create_date if slip.is_refund_payslip else slip.done_date if slip.is_correction_payslip else fields.Date.end_of(slip.date_to, 'month')

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + ['struct_id.journal_id']

    def action_payslip_cancel(self):
        # Payroll creates its draft entries itself (see _create_account_move), so it can drop them without
        # accounting rights. An entry that has been posted belongs to accounting: never escalate rights for it.
        moves_sudo = self.move_id.sudo()
        posted_moves = moves_sudo.filtered('posted_before').with_env(self.env)
        if posted_moves and not self.env.su and not self.env.user.has_group('account.group_account_invoice'):
            raise UserError(_(
                "The following payslips are linked to a posted journal entry, "
                "only a user with accounting rights can cancel them:\n%s",
                '\n'.join(self.filtered(lambda slip: slip.move_id in posted_moves).mapped('name')),
            ))
        (moves_sudo - posted_moves)._unlink_or_reverse()
        posted_moves._unlink_or_reverse()
        return super().action_payslip_cancel()

    def action_payslip_done(self):
        """
            Generate the accounting entries related to the selected payslips
            A move is created for each journal and for each month.
        """
        if any(slip.state == 'paid' for slip in self):
            raise ValidationError(_("You can't create a journal entry for a paid payslip."))
        res = super().action_payslip_done()
        self.filtered('journal_id')._action_create_account_move()
        return res

    def _get_account_move_vals(self):
        precision = self.env['decimal.precision'].precision_get('Payroll')

        all_payslips = self
        # Adding pay slips from a batch.
        for run in self.payslip_run_id:
            if run._are_payslips_ready():
                all_payslips |= run.slip_ids

        # A payslip needs to have either a validated state and not an accounting move or a draft state and the Anonymize flag set on the company.
        payslips_to_post = all_payslips.filtered(lambda slip: ((slip.state == 'validated' and not slip.move_id)
                                                            or (slip.state == 'draft' and self.company_id.batch_payroll_move_lines))
                                                            and slip.struct_id.journal_id)

        # Force the prefetch to avoid infinite loop
        payslips_to_post = payslips_to_post.with_prefetch()
        # Map all payslips by structure journal and pay slips month.
        # Case 1: Batch all the payslips together -> {'journal_id': {'month': slips}}
        # Case 2: Generate account move separately -> [{'journal_id': {'month': slip}}]
        if self.company_id.batch_payroll_move_lines:
            all_slip_mapped_data = defaultdict(lambda: defaultdict(lambda: self.env['hr.payslip']))
            for slip in payslips_to_post:
                all_slip_mapped_data[slip.struct_id.journal_id.id][slip.date or fields.Date.end_of(slip.date_to, 'month')] |= slip
            all_slip_mapped_data = [all_slip_mapped_data]
        else:
            all_slip_mapped_data = [{
                slip.struct_id.journal_id.id: {
                    slip.date or fields.Date.end_of(slip.date_to, 'month'): slip
                }
            } for slip in payslips_to_post]

        account_move_vals = []
        slips_date_tuples = []
        for slip_mapped_data in all_slip_mapped_data:
            for journal_id in slip_mapped_data:  # For each journal_id.
                for slip_date in slip_mapped_data[journal_id]:  # For each month.
                    line_ids = []
                    line_index = defaultdict(list)
                    debit_sum = 0.0
                    credit_sum = 0.0
                    date = slip_date
                    move_dict = {
                        'narration': '',
                        'ref': fields.Date.end_of(slip_mapped_data[journal_id][slip_date][0].date_to, 'month').strftime('%B %Y'),
                        'journal_id': journal_id,
                        'date': date,
                    }

                    for slip in slip_mapped_data[journal_id][slip_date]:
                        slip_lines = slip._prepare_slip_lines(date, line_ids, line_index)
                        line_ids.extend(slip_lines)

                    for line_id in line_ids: # Get the debit and credit sum.
                        debit_sum += line_id['debit']
                        credit_sum += line_id['credit']

                    # The code below is called if there is an error in the balance between credit and debit sum.
                    if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                        slip._prepare_adjust_line(line_ids, 'credit', debit_sum, credit_sum, date)
                    elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                        slip._prepare_adjust_line(line_ids, 'debit', debit_sum, credit_sum, date)

                    # Add accounting lines in the move
                    move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                    account_move_vals.append(move_dict)
                    slips_date_tuples.append((slip_mapped_data[journal_id][slip_date], date))

        return account_move_vals, slips_date_tuples

    def _action_create_account_move(self):
        account_move_vals, slips_date_tuples = self._get_account_move_vals()
        moves = self._create_account_move(account_move_vals)
        for move, (slips, date) in zip(moves, slips_date_tuples):
            slips.write({'move_id': move.id, 'date': date})
            if slips.company_id.batch_payroll_move_lines:
                slips.payslip_run_id.write({'move_id': move.id})
        return True

    def _prepare_line_values(self, line, account, date, debit, credit):
        batch_lines = self.company_id.batch_payroll_move_lines
        if not batch_lines and line.salary_rule_id.employee_move_line:
            partner = self.employee_id.work_contact_id
        else:
            partner = line.partner_id
        line_vals = []
        if not batch_lines and line.salary_rule_id.employee_move_line and self.employee_id.has_multiple_bank_accounts:
            debit_allocations = self._compute_salary_allocations(debit)
            credit_allocations = self._compute_salary_allocations(credit)
            for ba in self.employee_id.bank_account_ids | self.salary_attachment_ids.beneficiary_bank_account_id:
                subdebit = debit_allocations.get(str(ba.id), 0)
                subcredit = credit_allocations.get(str(ba.id), 0)
                line_vals.append({
                    'name': line.name if line.salary_rule_id.split_move_lines else line.salary_rule_id.name,
                    'partner_id': partner.id,
                    'account_id': account.id,
                    'employee_bank_account_id': ba.id,
                    'journal_id': line.slip_id.struct_id.journal_id.id,
                    'date': date,
                    'debit': subdebit,
                    'credit': subcredit,
                    'analytic_distribution': line.salary_rule_id.analytic_distribution or line.slip_id.version_id.analytic_distribution,
                    'tax_tag_ids': line.debit_tag_ids.ids if account.id == line.salary_rule_id.account_debit.id else line.credit_tag_ids.ids,
                    'tax_ids': [(4, tax_id) for tax_id in account.tax_ids.ids],
                })
            return line_vals

        return [{
            'name': line.name if line.salary_rule_id.split_move_lines else line.salary_rule_id.name,
            'partner_id': partner.id,
            'account_id': account.id,
            'journal_id': line.slip_id.struct_id.journal_id.id,
            'date': date,
            'debit': debit,
            'credit': credit,
            'analytic_distribution': line.salary_rule_id.analytic_distribution or line.slip_id.version_id.analytic_distribution,
            'tax_tag_ids': line.debit_tag_ids.ids if account.id == line.salary_rule_id.account_debit.id else line.credit_tag_ids.ids,
            'tax_ids': [(4, tax_id) for tax_id in account.tax_ids.ids],
        }]

    def _prepare_slip_lines(self, date, line_ids, line_index=None):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        batch_lines = self.company_id.batch_payroll_move_lines
        is_storno_credit_note = self.company_id.account_storno and self.credit_note

        def get_line_grouping_key(name, account_id, distribution):
            if isinstance(distribution, dict):
                distribution = tuple(sorted(distribution.items()))

            return name, account_id, distribution

        def get_accounting_amount(line):
            amount = line.total
            if line.code != 'NET':
                return amount

            # Excluded rules are posted independently, so remove them from NET.
            excluded_amount = sum(
                abs(other_line.total)
                for other_line in self.line_ids
                if other_line.salary_rule_id.not_computed_in_net
            )
            if amount > 0:
                amount -= excluded_amount
            elif amount < 0:
                amount += excluded_amount
            return amount

        def get_debit_credit(balance):
            if is_storno_credit_note:
                return min(balance, 0.0), min(-balance, 0.0)
            return max(balance, 0.0), max(-balance, 0.0)

        def get_indexed_line(indexed_lines, line, account_id, debit, credit):
            return next((
                line_vals
                for line_vals in indexed_lines
                if (
                       (line_vals['debit'] > 0 >= credit)
                       or (line_vals['credit'] > 0 >= debit)
                   )
                   and self._check_debit_credit_tags(line_vals, line, account_id)
            ), False)

        if line_index is None:
            line_index = defaultdict(list)
            for line_vals in line_ids:
                if line_vals['debit'] > 0 or line_vals['credit'] > 0:
                    key = get_line_grouping_key(
                        line_vals['name'],
                        line_vals['account_id'],
                        line_vals['analytic_distribution'],
                    )
                    line_index[key].append(line_vals)

        new_lines = []
        for line in self.line_ids:
            amount = get_accounting_amount(line)
            if float_is_zero(amount, precision_digits=precision):
                continue

            merge_amounts = batch_lines or not line.salary_rule_id.employee_move_line
            line_name = line.name if line.salary_rule_id.split_move_lines else line.salary_rule_id.name
            distribution = line.salary_rule_id.analytic_distribution or line.slip_id.version_id.analytic_distribution

            for account, balance in (
                (line.salary_rule_id.account_debit, amount),
                (line.salary_rule_id.account_credit, -amount),
            ):
                if not account:
                    continue

                debit, credit = get_debit_credit(balance)
                grouping_key = get_line_grouping_key(line_name, account.id, distribution)
                indexed_line = merge_amounts and get_indexed_line(
                    line_index[grouping_key], line, account.id, debit, credit,
                )

                if indexed_line:
                    indexed_line['debit'] += debit
                    indexed_line['credit'] += credit
                    if indexed_line['debit'] <= 0 and indexed_line['credit'] <= 0:
                        line_index[grouping_key].remove(indexed_line)
                    continue

                prepared_lines = self._prepare_line_values(line, account, date, debit, credit)
                new_lines.extend(prepared_lines)
                line_index[grouping_key].extend(
                    line_vals
                    for line_vals in prepared_lines
                    if line_vals['debit'] > 0 or line_vals['credit'] > 0
                )

        return new_lines

    def _prepare_adjust_line(self, line_ids, adjust_type, debit_sum, credit_sum, date):
        acc_id = self.sudo().journal_id.default_account_id.id
        if not acc_id:
            raise UserError(_('The Expense Journal "%s" has not properly configured the default Account!', self.journal_id.name))
        existing_adjustment_line = (
            line_id for line_id in line_ids if line_id['name'] == self.env._('Adjustment Entry')
        )
        adjust_credit = next(existing_adjustment_line, False)

        if not adjust_credit:
            adjust_credit = {
                'name': _('Adjustment Entry'),
                'partner_id': False,
                'account_id': acc_id,
                'journal_id': self.journal_id.id,
                'date': date,
                'debit': 0.0 if adjust_type == 'credit' else credit_sum - debit_sum,
                'credit': debit_sum - credit_sum if adjust_type == 'credit' else 0.0,
            }
            line_ids.append(adjust_credit)
        else:
            adjust_credit['credit'] = debit_sum - credit_sum

    def _check_debit_credit_tags(self, line_vals, line, account_id):
        return (
            account_id != line.salary_rule_id.account_debit.id
            or sorted(line_vals['tax_tag_ids']) == sorted(line.debit_tag_ids.ids)
        ) and (
            account_id != line.salary_rule_id.account_credit.id
            or sorted(line_vals['tax_tag_ids']) == sorted(line.credit_tag_ids.ids)
        )

    # TODO master: remove this method no longer used
    def _check_partially_matching_accounts(self, line_id, line):
        keys = line_id['analytic_distribution']
        unravelled_keys = []
        for key in keys:
            ids = key.split(',')
            unravelled_keys += ids

        result = any(str(acc_id.id) in unravelled_keys for acc_id in line.salary_rule_id.distribution_analytic_account_ids) \
            or any(str(acc_id.id) in unravelled_keys for acc_id in line.slip_id.version_id.distribution_analytic_account_ids)

        return result

    def _create_account_move(self, values):
        return self.env['account.move'].sudo().create(values)

    def action_open_move(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }
