from odoo import fields, models
from odoo.tools import SQL


class AccountSelectAccountLine(models.TransientModel):
    _name = "account.select.account.line"
    _description = "Account Select Account Line"
    # Unused wizard but can't remove in stable

    name = fields.Char()
    code = fields.Char()
    description = fields.Char()
    account_type = fields.Selection(
        selection=[
            ("asset_receivable", "Receivable"),
            ("asset_cash", "Bank and Cash"),
            ("asset_current", "Current Assets"),
            ("asset_non_current", "Non-current Assets"),
            ("asset_prepayments", "Prepayments"),
            ("asset_fixed", "Fixed Assets"),
            ("liability_payable", "Payable"),
            ("liability_credit_card", "Credit Card"),
            ("liability_current", "Current Liabilities"),
            ("liability_non_current", "Non-current Liabilities"),
            ("equity", "Equity"),
            ("equity_unaffected", "Current Year Earnings"),
            ("income", "Income"),
            ("income_other", "Other Income"),
            ("expense", "Expenses"),
            ("expense_other", "Other Expenses"),
            ("expense_depreciation", "Depreciation"),
            ("expense_direct_cost", "Cost of Revenue"),
            ("off_balance", "Off-Balance Sheet"),
        ],
    )
    amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency')
    account_id = fields.Many2one('account.account')

    def _order_to_sql(self, table, order, reverse=False):
        sql_order = super()._order_to_sql(table, order, reverse)

        if order == self._order and (preferred_account_type := self.env.context.get('preferred_account_type')):
            sql_order = SQL(
                "%(field_sql)s = %(preferred_account_type)s %(direction)s, %(base_order)s",
                field_sql=table.account_type,
                preferred_account_type=preferred_account_type,
                direction=SQL('ASC') if reverse else SQL('DESC'),
                base_order=sql_order,
            )
        return sql_order
