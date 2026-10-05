from odoo import fields, models


MIN_LONG_TERM_PERIOD = 60
MIN_MID_TERM_PERIOD = 12


class AccountLoanLine(models.Model):
    _inherit = 'account.loan.line'

    mid_term_theoretical_balance = fields.Monetary(
        string="Mid-Term",
        compute='_compute_theoretical_balances',
        store=True,  # stored for pivot view
    )

    def _compute_theoretical_balances(self):
        non_fr_lines = self.browse()
        for line in self:
            if line.company_id.account_fiscal_country_id.code == 'FR':
                filtered_lines = line.loan_id.line_ids.filtered(lambda l: line.date and l.date and l.date > line.date)
                line.long_term_theoretical_balance = sum(filtered_lines[MIN_LONG_TERM_PERIOD:].mapped('principal'))
                line.mid_term_theoretical_balance = sum(filtered_lines[MIN_MID_TERM_PERIOD:MIN_LONG_TERM_PERIOD].mapped('principal'))
                line.short_term_theoretical_balance = sum(filtered_lines[:MIN_MID_TERM_PERIOD].mapped('principal'))
            else:
                non_fr_lines |= line
        super(AccountLoanLine, non_fr_lines)._compute_theoretical_balances()
