from odoo import api, fields, models


class AccountPaymentMethodLine(models.Model):
    _inherit = 'account.payment.method.line'

    is_iso_se_payment_method = fields.Boolean(compute='_compute_is_iso_se_payment_method')

    @api.depends('code')
    def _compute_is_iso_se_payment_method(self):
        for line in self:
            line.is_iso_se_payment_method = line.code == 'iso20022_se'

    @api.depends('bank_account_id.account_number', 'company_id.account_fiscal_country_id', 'company_id.country_id')
    def _compute_sepa_pain_version(self):
        se_bban_lines = self.filtered(lambda line: line.bank_account_id.account_type in {'bban_se', 'plusgiro', 'bankgiro'})
        # For SE BBAN, we use the pain.001.001.03 version
        se_bban_lines.sepa_pain_version = 'pain.001.001.03'
        super(AccountPaymentMethodLine, self - se_bban_lines)._compute_sepa_pain_version()
