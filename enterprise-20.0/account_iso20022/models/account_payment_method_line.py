from odoo import api, fields, models

XML_VERSION_SELECTION = [
    ('pain.001.001.03.austrian.004', 'Austrian'),
    ('pain.001.001.03.de', 'German'),
    ('pain.001.001.09', 'pain.001.001.09'),
    ('pain.001.001.03', 'pain.001.001.03'),
]


class AccountPaymentMethodLine(models.Model):
    _inherit = 'account.payment.method.line'

    bank_account_id = fields.Many2one(related='journal_id.bank_account_id', readonly=True)
    is_sepa_ct_payment_method = fields.Boolean(compute='_compute_is_sepa_ct_payment_method')
    sepa_pain_version = fields.Selection(
        XML_VERSION_SELECTION,
        string="XML Version",
        help="SEPA version to use to generate Credit Transfer XML files from this journal",
        compute='_compute_sepa_pain_version',
        store=True,
        readonly=False,
    )

    @api.depends('bank_account_id.account_number', 'company_id.account_fiscal_country_id', 'company_id.country_id')
    def _compute_sepa_pain_version(self):
        """ Set default value for the field sepa_pain_version"""
        pains_by_country = {
            'DE': 'pain.001.001.03.de',
            'AT': 'pain.001.001.03.austrian.004',
        }
        for rec in self:
            if not rec.is_sepa_ct_payment_method:
                rec.sepa_pain_version = False
                continue
            if rec.bank_account_id and rec.bank_account_id.account_type == 'iban':
                country_code = rec.bank_account_id.account_number[:2].upper()
            # Then try from the company's fiscal country, and finally from the company's country
            else:
                country_code = rec.company_id.account_fiscal_country_id.code or rec.company_id.country_code
            if country_code in pains_by_country:
                rec.sepa_pain_version = pains_by_country.get(country_code)
            else:
                # Having a sepa_pain_version set at pain.001.001.03 means that the user changed it manually,
                # since the default is 09. In this case, we keep the user's change.
                rec.sepa_pain_version = 'pain.001.001.09' \
                    if rec.sepa_pain_version != 'pain.001.001.03' \
                    else rec.sepa_pain_version

    @api.depends('code')
    def _compute_is_sepa_ct_payment_method(self):
        for line in self:
            code = line.code or ''
            line.is_sepa_ct_payment_method = ('sepa_ct' in code) or ('iso20022_ch' in code and self.env['ir.config_parameter'].sudo().get_bool('iso20022_ch_force_sepa'))
