from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    available_inter_company_ids = fields.Many2many(
        comodel_name='res.company',
        string="Inter Companies",
        compute="_compute_available_available_inter_company_ids",
    )

    @api.depends_context('company', 'allowed_company_ids')
    def _compute_available_available_inter_company_ids(self):
        self.available_inter_company_ids = self._get_available_inter_companies()

    @api.model
    def _get_available_inter_companies(self):
        return self.env.companies.filtered_domain([
            ('account_interco_clearing_journal_id', '!=', False),
            ('account_interco_payable_id', '!=', False),
            ('account_interco_receivable_id', '!=', False),
        ])

    def delete_reconciled_line(self, move_line_ids):
        self.ensure_one()

        move_lines = self.env['account.move.line'].browse(move_line_ids)

        # Remove the settlement move link to the move_lines
        available_inter_company_ids = self.available_inter_company_ids
        for move_line in move_lines:
            if move_line.company_id not in available_inter_company_ids:
                # No need to check if the line has a settlement move if it's not in the available inter companies
                continue

            reconciled_move = move_line.reconciled_lines_ids.move_id
            # We know the move is a settlement entry, and it needs to be deleted
            settlement_move_line = reconciled_move.line_ids.filtered(lambda line: line.account_id in {self.company_id.account_interco_payable_id, self.company_id.account_interco_receivable_id})
            if settlement_move_line:
                (reconciled_move + reconciled_move.inter_company_clearing_move_id)._unlink_or_reverse()

        super().delete_reconciled_line(move_line_ids)

    def set_line_bank_statement_line(self, move_lines_ids, allow_partial=True):
        self.ensure_one()
        # We do not want to set a line that is already reconciled, otherwise a user error would be raised.
        # Need to be a browse and a filtered domain to keep the order as we receive it.
        move_lines = self.env['account.move.line'].browse(move_lines_ids).filtered_domain([('reconciled', '=', False)])
        if not move_lines:
            return

        # We launch the class set_line for the basic lines of the same company or branch or parent than the statement line
        all_children_and_parents_companies = self._get_all_children_and_parents_companies()
        if same_company_move_lines := move_lines.filtered(lambda line: line.company_id.id in all_children_and_parents_companies):
            super().set_line_bank_statement_line(same_company_move_lines.ids, allow_partial)

        if other_move_lines := move_lines - same_company_move_lines:
            # Create clearing entries in target companies
            entry_ids = []
            available_inter_company_ids = self.available_inter_company_ids
            for move_line in other_move_lines:
                if move_line.company_id not in available_inter_company_ids:
                    raise UserError(self.env._("The company of the move line %(move_name)s does not have the inter-company settings properly configured.", move_name=move_line.move_name))

                clearing_line = self._create_inter_company_clearing_entry(move_line)
                (move_line + clearing_line).reconcile()

                entry_line = self._create_inter_company_settlement_entry(move_line, clearing_line.move_id)
                entry_ids.append(entry_line.id)

                # Post both moves at once
                (clearing_line.move_id + entry_line.move_id).action_post()

                # Log some messages to be able to navigate between clearing move and settlement move
                clearing_line.move_id.message_post(
                    body=self.env._("Settlement move %(settlement_move)s created in %(company)s", settlement_move=entry_line.move_id._get_html_link(), company=entry_line.company_id.display_name)
                )
                entry_line.move_id.message_post(
                    body=self.env._("Clearing move %(clearing_move)s created in %(company)s", clearing_move=clearing_line.move_id._get_html_link(), company=clearing_line.company_id.display_name)
                )

            # We need to reconcile the statement line with the new entry
            self.set_line_bank_statement_line(entry_ids, allow_partial=allow_partial)

    def _create_inter_company_clearing_entry(self, move_line):
        """
            Create and post a clearing entry in the move line's company.
            The entry mirrors the given move line on the appropriate inter-company
            and counterpart accounts, then reconciles its counterpart line with the
            original move line.

            :param account.move.line move_line: The move line for which the clearing entry should be created.
            :return: The counterpart line of the newly created clearing entry.
        """
        is_sale_document = move_line.currency_id.compare_amounts(move_line.balance, 0) > 0
        target_company = move_line.company_id
        inter_company_account = (
            move_line.company_id.account_interco_receivable_id
            if is_sale_document
            else move_line.company_id.account_interco_payable_id
        )

        clearing_move = self.env['account.move'].with_company(target_company).create({
            'move_type': 'entry',
            'journal_id': target_company.account_interco_clearing_journal_id.id,
            'ref': self.env._(
                "Interco Clearing %(partner)s - %(ref)s - %(company)s",
                partner=move_line.partner_id.display_name,
                ref=move_line.ref or move_line.move_name,
                company=self.company_id.display_name,
            ),
            'line_ids': [
                Command.create({
                    'name': self.env._(
                        "Interco Clearing %(ref)s to %(company)s",
                        ref=move_line.ref or move_line.move_name,
                        company=self.company_id.display_name,
                    ),
                    'account_id': move_line.account_id.id,
                    'partner_id': move_line.partner_id.id,
                    'currency_id': move_line.currency_id.id,
                    'amount_currency': -move_line.amount_currency,
                    'balance': -move_line.balance,
                }),
                Command.create({
                    'name': self.env._(
                        "Interco Clearing %(partner)s - %(ref)s",
                        partner=move_line.partner_id.display_name,
                        ref=move_line.ref or move_line.move_name,
                    ),
                    'account_id': inter_company_account.id,
                    'partner_id': self.company_id.partner_id.id,
                    'currency_id': move_line.currency_id.id,
                    'amount_currency': move_line.amount_currency,
                    'balance': move_line.balance,
                }),
            ],
        })

        clearing_line = clearing_move.line_ids.filtered(lambda l: l.account_id == move_line.account_id)
        return clearing_line

    def _create_inter_company_settlement_entry(self, move_line, clearing_move):
        """
            Create and post a settlement entry in the statement line's company.
            The entry settles the balances of the given move lines through the
            inter-company and counterpart accounts.

            :param account.move.line move_line: The move line for which the settlement entry should be created.
            :return: The counterpart line of the newly created settlement entry.
            """
        is_sale_document = self.currency_id.compare_amounts(self.amount, 0) > 0
        # Create settlement entry in current statement's company
        inter_company_account = (
            self.company_id.account_interco_payable_id
            if is_sale_document
            else self.company_id.account_interco_receivable_id
        )

        counterpart_account = (
            self.company_id.receivable_account_id
            if is_sale_document
            else self.company_id.payable_account_id
        )

        entry = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'entry',
            'journal_id': self.company_id.account_interco_clearing_journal_id.id,
            'ref': self.env._(
                "Interco Settlement %(partner)s - %(ref)s - %(company)s",
                partner=move_line.partner_id.display_name,
                ref=move_line.ref or move_line.move_name,
                company=move_line.company_id.display_name,
            ),
            'inter_company_clearing_move_id': clearing_move.id,  # To keep a link between the clearing move and the settlement move to be able to delete when unreconciling in the bank rec widget
            'line_ids': [
                Command.create({
                    'name': self.env._(
                        "Interco Settlement %(partner)s - %(ref)s",
                        partner=move_line.partner_id.display_name,
                        ref=move_line.ref or move_line.move_name,
                    ),
                    'account_id': inter_company_account.id,
                    'partner_id': move_line.company_id.partner_id.id,
                    'balance': -move_line.balance,
                    'currency_id': self.company_id.currency_id.id,
                }),
                Command.create({
                    'name': self.env._(
                        "Interco Settlement %(ref)s to %(company)s",
                        ref=move_line.ref or move_line.move_name,
                        company=move_line.company_id.display_name,
                    ),
                    'account_id': counterpart_account.id,
                    'partner_id': move_line.partner_id.id,
                    'balance': move_line.balance,
                    'currency_id': self.company_id.currency_id.id,
                }),
            ],
        })

        entry_line = entry.line_ids.filtered(lambda line: line.account_id == counterpart_account)
        return entry_line

    def _get_all_children_and_parents_companies(self):
        return set(self.env['res.company'].search([
            '|',
            ('id', 'child_of', self.company_id.id),
            ('id', 'parent_of', self.company_id.id),
        ]).ids)
