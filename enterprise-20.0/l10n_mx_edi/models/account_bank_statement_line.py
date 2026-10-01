from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    l10n_mx_edi_can_use_factoring = fields.Boolean(compute="_compute_l10n_mx_edi_can_use_factoring")

    @api.depends('journal_id', 'country_code', 'currency_id', 'foreign_currency_id')
    def _compute_l10n_mx_edi_can_use_factoring(self):
        for line in self:
            line.l10n_mx_edi_can_use_factoring = (
                line.company_id.l10n_mx_edi_factoring_account_id
                and line.review_state not in ('todo', 'anomaly')
                and line.move_id._l10n_mx_edi_is_cfdi_document()
                and not line.foreign_currency_id
            )
