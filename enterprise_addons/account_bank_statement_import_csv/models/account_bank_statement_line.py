from odoo import models
from odoo.tools import html2plaintext


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def _format_statement_line_data(self):
        if self.env.context.get('bank_stmt_import'):
            self.transaction_details = {
                'Statement': self.statement_id.name if self.statement_id else None,
                'Reference': self.ref or None,
                'Notes': html2plaintext(self.narration or '') or None,
            }
        return super()._format_statement_line_data()
