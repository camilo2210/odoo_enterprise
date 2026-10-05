# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import SQL, html2plaintext
from odoo.addons.account.models.account_move import REVIEW_STATE_SELECTION


class AccountAccount(models.Model):
    _inherit = "account.account"

    exclude_provision_currency_ids = fields.Many2many('res.currency', relation='account_account_exclude_res_currency_provision', help="Whether or not we have to make provisions for the selected foreign currencies.")
    budget_item_ids = fields.One2many(comodel_name='account.report.budget.item', inverse_name='account_id')  # To use it in the domain when adding accounts from the report

    audit_debit = fields.Monetary(string="Debit", compute="_compute_audit_period", currency_field="company_currency_id", compute_sql="_compute_sql_audit_debit", compute_sudo=False)
    audit_credit = fields.Monetary(string="Credit", compute="_compute_audit_period", currency_field="company_currency_id", compute_sql="_compute_sql_audit_credit", compute_sudo=False)
    audit_balance = fields.Monetary(string="Balance", compute="_compute_audit_period", currency_field="company_currency_id", compute_sql="_compute_sql_audit_balance", compute_sudo=False)
    audit_balance_show_warning = fields.Boolean(compute="_compute_audit_balance_show_warning")
    audit_previous_balance = fields.Monetary(string="Balance N-1", compute="_compute_audit_period", currency_field="company_currency_id", compute_sql="_compute_sql_audit_previous_balance", compute_sudo=False)
    audit_previous_balance_show_warning = fields.Boolean(compute="_compute_audit_previous_balance_show_warning")
    audit_var_n_1 = fields.Monetary(string="Var N-1", compute="_compute_audit_variation", currency_field="company_currency_id", compute_sql="_compute_sql_audit_var_n_1", compute_sudo=False)
    audit_var_percentage = fields.Float(string="Var %", compute="_compute_audit_variation", compute_sql="_compute_sql_audit_var_percentage", compute_sudo=False)
    audit_status = fields.Selection(selection=REVIEW_STATE_SELECTION, string="Status", compute="_compute_audit_status", inverse="_inverse_audit_status", compute_sql="_compute_sql_audit_status", compute_sudo=False)

    account_status = fields.One2many(string="Account Status", comodel_name='account.audit.account.status', inverse_name='account_id')
    last_message = fields.Char(string="Last Comment", compute='_compute_last_message')

    @api.depends_context('working_file_id')
    def _compute_audit_period(self):
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))
        found_ids = set()

        if working_file and any(self._ids):
            query = self._as_query(ordered=False)
            for account_id, debit, credit, balance, previous_balance in self.env.execute_query(query.select(*(
                query.table[field_name]
                for field_name in ('id', 'audit_debit', 'audit_credit', 'audit_balance', 'audit_previous_balance')
            ))):
                account = self.browse(account_id)
                account.audit_debit = debit
                account.audit_credit = credit
                account.audit_balance = balance
                account.audit_previous_balance = previous_balance
                found_ids.add(account_id)

        remaining = self - self.browse(found_ids)
        remaining.audit_debit = remaining.audit_credit = remaining.audit_balance = remaining.audit_previous_balance = 0

    @api.model
    def _common_audit_aml_sql(self, table, column_name, previous=False):
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))
        if not working_file:
            return SQL("NULL")
        self.env['account.move.line'].flush_model(['debit', 'credit', 'balance', 'account_id', 'company_id', 'date', 'parent_state'])

        # build the result and check if need to add the join
        alias_audit = table._make_alias(f"audit_wf{working_file.id}{'p' if previous else ''}")
        sql_result = SQL("COALESCE(%s, 0.0)", alias_audit[column_name])
        if alias_audit._alias in table._query._joins:
            return sql_result

        # get dates
        company_ids = working_file.company_ids.ids
        if previous:
            date_from, date_to = working_file.type_id._get_period_boundaries(
                working_file.company_id, (working_file.date_from or fields.Date.context_today(self)) - relativedelta(days=1))
        else:
            date_from = working_file.date_from
            date_to = working_file.date_to

        table._query.add_join(
            'LEFT JOIN',
            alias_audit,
            SQL("""
                (SELECT
                    SUM(aml.debit) as debit,
                    SUM(aml.credit) as credit,
                    SUM(aml.balance) as balance,
                    account_id
                FROM (
                         SELECT aml.debit, aml.credit, aml.balance, aml.account_id
                           FROM account_move_line aml
                           JOIN account_account aml_account ON aml_account.id = aml.account_id
                          WHERE aml.date <= %(date_to)s
                            AND NOT aml_account.account_type ILIKE ANY(ARRAY['income%%', 'expense%%', 'equity_unaffected'])
                            AND aml.company_id = ANY(%(company_ids)s)
                            AND aml.parent_state = 'posted'

                         UNION ALL

                         SELECT aml.debit, aml.credit, aml.balance, aml.account_id
                           FROM account_move_line aml
                           JOIN account_account aml_account ON aml_account.id = aml.account_id
                          WHERE aml.date <= %(date_to)s
                            AND aml.date >= %(date_from)s
                            AND aml_account.account_type ILIKE ANY(ARRAY['income%%', 'expense%%', 'equity_unaffected'])
                            AND aml.company_id = ANY(%(company_ids)s)
                            AND aml.parent_state = 'posted'
                     ) aml
                GROUP BY account_id)
                """,
                date_from=date_from,
                date_to=date_to,
                company_ids=company_ids,
            ),
            SQL("%s = %s", alias_audit.account_id, table.id)
        )

        return sql_result

    def _compute_sql_audit_debit(self, table):
        return self._common_audit_aml_sql(table, 'debit')

    def _compute_sql_audit_credit(self, table):
        return self._common_audit_aml_sql(table, 'credit')

    def _compute_sql_audit_balance(self, table):
        return self._common_audit_aml_sql(table, 'balance')

    def _compute_sql_audit_previous_balance(self, table):
        return self._common_audit_aml_sql(table, 'balance', previous=True)

    @api.depends('audit_balance', 'audit_previous_balance')
    def _compute_audit_variation(self):
        for account in self:
            account.audit_var_n_1 = account.audit_balance - account.audit_previous_balance

            if self.env.company.currency_id.is_zero(account.audit_previous_balance):
                account.audit_var_percentage = False
            else:
                account.audit_var_percentage = (account.audit_balance - account.audit_previous_balance) / account.audit_previous_balance

    def _compute_sql_audit_var_n_1(self, table):
        balance_sql = self._compute_sql_audit_balance(table)
        prev_balance_sql = self._compute_sql_audit_previous_balance(table)
        return SQL("%s - %s", balance_sql, prev_balance_sql)

    def _compute_sql_audit_var_percentage(self, table):
        balance_sql = self._compute_sql_audit_balance(table)
        prev_balance_sql = self._compute_sql_audit_previous_balance(table)
        return SQL("CASE WHEN %(prev)s <> 0 THEN (%(curr)s - %(prev)s) / %(prev)s * 100 END", curr=balance_sql, prev=prev_balance_sql)

    @api.depends_context('working_file_id')
    def _compute_audit_status(self):
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))

        self.audit_status = 'todo'

        if working_file:
            create_vals = []
            account_status_by_account = {status.account_id: status for status in working_file.audit_account_status_ids}
            for account in self:
                if account in account_status_by_account:
                    account.audit_status = account_status_by_account[account].status
                else:
                    create_vals.append({
                        'account_id': account.id,
                        'audit_id': working_file.id,
                    })
            if create_vals:
                self.env['account.audit.account.status'].create(create_vals)

    def _compute_sql_audit_status(self, table):
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))
        status_model = self.env['account.audit.account.status']
        status_query = status_model._search([('audit_id', 'in', working_file.ids)])
        if status_query.is_empty():
            return SQL("NULL::text")
        status_alias = table._make_alias('audit_status')
        table._query.add_join(
            'LEFT JOIN',
            status_alias,
            status_query.subselect(status_query.table.account_id, status_query.table.status),
            SQL("%s = %s", status_alias.account_id, table.id)
        )
        return SQL('%s', status_alias.status)

    def _inverse_audit_status(self):
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))

        if working_file:
            account_status_by_account = {status.account_id: status for status in working_file.audit_account_status_ids}
            for account in self:
                if account in account_status_by_account:
                    account_status_by_account[account].status = account.audit_status

    def _compute_balance_warning(self, balance_field_name, warning_field_name):
        for account in self:
            if account.internal_group == 'asset':
                account[warning_field_name] = account.company_currency_id.compare_amounts(account[balance_field_name], 0) == -1
            elif account.internal_group == 'liability':
                account[warning_field_name] = account.company_currency_id.compare_amounts(account[balance_field_name], 0) == 1
            else:
                account[warning_field_name] = False

    @api.depends('audit_balance')
    def _compute_audit_balance_show_warning(self):
        self._compute_balance_warning('audit_balance', 'audit_balance_show_warning')

    @api.depends('audit_previous_balance')
    def _compute_audit_previous_balance_show_warning(self):
        self._compute_balance_warning('audit_previous_balance', 'audit_previous_balance_show_warning')

    @api.depends_context('working_file_id')
    def _compute_last_message(self):
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))
        if not working_file:
            for account in self:
                account.last_message = False
            return

        self.env['mail.message'].flush_model(['model', 'res_id', 'body'])
        self.env['account.report.annotation'].flush_model(['message_id'])

        self.env.cr.execute("""
            SELECT DISTINCT ON (message.res_id) message.res_id, message.body
            FROM mail_message message
            JOIN account_report_annotation annotation ON annotation.message_id = message.id
            WHERE message.model = 'account.account' AND message.res_id = ANY(%s) AND annotation.date >= %s AND annotation.date <= %s
            ORDER BY message.res_id, message.create_date DESC
        """, (self.ids, working_file.date_from, working_file.date_to))
        last_message_by_account = {
            row[0]: html2plaintext(row[1])
            for row in self.env.cr.fetchall()
        }

        for account in self:
            account.last_message = last_message_by_account.get(account.id, False)

    def action_audit_account(self):
        action = self.env['ir.actions.act_window']._for_xml_id("account.action_account_moves_all")
        context = literal_eval(action.get('context', {}))
        working_file = self.env['account.return'].browse(self.env.context.get('working_file_id'))
        if working_file:
            context.update({
                'search_default_audit_date_between': 1,
                'date_to': fields.Date.to_string(working_file.date_to),
                'date_from': fields.Date.to_string(working_file.date_from),
            })

        return {
            **action,
            'domain': [('account_id', 'in', self.ids)],
            'context': context,
            'search_view_id': self.env.ref('account_reports.view_audit_move_line_filter').id,
            'views': [(self.env.ref('account_reports.view_audit_move_line_list').id, 'list')],
        }
