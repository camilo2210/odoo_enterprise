# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL
from odoo.tools.sql import table_columns


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    exclude_bank_lines = fields.Boolean(compute='_compute_exclude_bank_lines', store=True)

    analytic_coverage = fields.Float(
        string="Analytic Coverage",
        compute='_compute_analytic_coverage',
        compute_sql='_compute_sql_analytic_coverage',
        compute_sudo=True,
        groups='analytic.group_analytic_accounting',
    )
    cta_value = fields.Monetary(
        string="CTA",
        compute='_compute_cta_value',
        compute_sql='_compute_sql_cta_value',
        compute_sudo=True,
        currency_field='consolidation_currency_id',
    )

    @api.depends('journal_id')
    def _compute_exclude_bank_lines(self):
        for move_line in self:
            move_line.exclude_bank_lines = move_line.account_id != move_line.journal_id.default_account_id

    @api.constrains('tax_ids', 'tax_tag_ids')
    def _check_taxes_on_closing_entries(self):
        for aml in self:
            if aml.move_id.closing_return_id and (aml.tax_ids or aml.tax_tag_ids):
                raise UserError(_("You cannot add taxes on a tax closing move line."))

    @api.depends('product_id', 'product_uom_id', 'move_id.closing_return_id')
    def _compute_tax_ids(self):
        """ Some special cases may see accounts used in tax closing having default taxes.
        They would trigger the constrains above, which we don't want. Instead, we don't trigger
        the tax computation in this case.
        """
        # EXTEND account
        lines_to_compute = self.filtered(lambda line: not line.move_id.closing_return_id)
        (self - lines_to_compute).tax_ids = False
        super(AccountMoveLine, lines_to_compute)._compute_tax_ids()

    def _compute_sql_cta_value(self, table):
        current_rate_table = table._with_model(self.with_context(currency_translation='current'))
        return SQL("%s - %s", table.consolidation_balance, current_rate_table.consolidation_balance)

    @api.depends('consolidation_balance', 'consolidation_rate', 'balance')
    def _compute_cta_value(self):
        for line in self:
            line.cta_value = line.consolidation_balance - line.with_context(currency_translation='current').consolidation_balance

    def _get_attachment_domains(self):
        attachment_domains = super()._get_attachment_domains()
        if self.move_id.closing_return_id:
            attachment_domains.append([('res_model', '=', 'account.return'), ('res_id', 'in', self.move_id.closing_return_id.ids)])
        return attachment_domains

    @api.model
    def _get_attachment_by_record(self, id_model2attachments, move_line):
        attachment_id = super()._get_attachment_by_record(id_model2attachments, move_line)
        if not attachment_id and move_line.move_id.closing_return_id:
            attachment_id = id_model2attachments.get(('account.return', move_line.move_id.closing_return_id.id))
        return attachment_id

    @api.model
    def _prepare_aml_shadowing_for_report(self, change_equivalence_dict, prefix_fields=False):
        """ Prepares the fields lists for creating a temporary table shadowing the account_move_line one.
        This is used to switch the computation mode of the reports, with analytics or financial budgets, for example.

        :param change_equivalence_dict: A dict, in the form {aml_field: sql_equivalence}, where:
                                        - aml_field: is a string containing the name of field of account.move.line
                                        - sql_equivalence: is the value to use to shadow aml_field. It can be an SQL object; if
                                          it's not, it'll be escaped in the query.
        :param prefix_fields: True if you want the returned stored fields to be prefixed with the `account_move_line` table.

        :return: A tuple of 2 SQL objects, so that:
                 - The first one is the fields list to pass into the INSERT TO part of the query filling up the temporary table
                 - The second one contains the field values to insert into the SELECT clause of the same query, in the same order
                   as in the first element of the returned tuple.
        """
        line_fields = self.env['account.move.line'].fields_get(attributes=["translate"])
        stored_fields = {fld for fld in table_columns(self.env.cr, 'account_move_line') if fld in line_fields}

        fields_to_insert = []
        for fname in stored_fields:
            if fname in change_equivalence_dict:
                fields_to_insert.append(SQL(
                    "%(original)s AS %(asname)s",
                    original=change_equivalence_dict[fname],
                    asname=SQL.identifier(fname),
                ))
            else:
                typecast = self.env['account.move.line']._fields[fname].stored_sql_column_type

                fields_to_insert.append(SQL(
                    "CAST(NULL AS %(typecast)s) AS %(fname)s",
                    typecast=typecast,
                    fname=SQL.identifier(fname),
                ))

        return (
            SQL(', ').join(
                SQL.identifier('account_move_line', fname) if prefix_fields else SQL.identifier(fname)
                for fname in stored_fields
            ),
            SQL(', ').join(fields_to_insert)
        )

    def _affect_tax_report(self):
        return super()._affect_tax_report() or (self.move_id.closing_return_id and not self.env.context.get('account_bypass_tax_closing_lock_check'))

    def _compute_sql_analytic_coverage(self, table):
        plan_id = self.env.context.get('selected_analytic_plan')
        if not plan_id:
            return SQL("0.0")

        return SQL("""
               (SELECT COALESCE(SUM(CAST(distribution.value AS FLOAT)) / 100, 0)
                  FROM jsonb_each_text(%(distribution)s) AS distribution(key, value)
                 WHERE EXISTS (
                          SELECT 1
                            FROM regexp_split_to_table(distribution.key, ',') AS accounts
                            JOIN account_analytic_account ON account_analytic_account.id = CAST(accounts AS INTEGER)
                           WHERE account_analytic_account.plan_id = %(plan_id)s
               ))
            """,
            distribution=table.analytic_distribution,
            plan_id=plan_id,
        )

    def _compute_analytic_coverage(self):
        query = self._search([('id', 'in', self.ids)])
        line2coverage = dict(self.env.execute_query(query.select(
            query.table.id,
            query.table.analytic_coverage,
        )))
        for line in self:
            line.analytic_coverage = line2coverage[line._origin.id]
