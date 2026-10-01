from markupsafe import Markup
from lxml import html

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10n_Be_ReportsISOCPrepaymentPayForm(models.Model):
    _name = 'l10n_be_reports.isoc.prepayment.pay.form'
    _description = "Payment instructions for ISOC prepayment"

    return_id = fields.Many2one(comodel_name='account.return', required=True)
    company_id = fields.Many2one(comodel_name='res.company', string="Company")
    currency_id = fields.Many2one(comodel_name='res.currency', related='return_id.amount_to_pay_currency_id')
    partner_id = fields.Many2one(comodel_name='res.partner', related='partner_bank_id.partner_id')
    partner_bank_id = fields.Many2one(comodel_name='res.partner.bank')
    account_number = fields.Char(string="IBAN", related='partner_bank_id.account_number')
    communication = fields.Char(compute='_compute_communication')
    profit_estimate = fields.Monetary(
        string="Profit Estimate",
        currency_field='currency_id',
        required=True,
        default=0,
    )
    corporate_tax_rate = fields.Selection(
        related='company_id.l10n_be_isoc_corporate_tax_rate',
        required=True,
        readonly=False
    )
    amount_to_pay = fields.Monetary(compute='_compute_amount_to_pay', store=True)

    qr_code = fields.Html(compute='_compute_qr_code')
    show_warning_missing_vat_number = fields.Boolean(compute='_compute_show_warning_missing_vat_number')

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard.profit_estimate = wizard.amount_to_pay * (400 / int(wizard.corporate_tax_rate))

        return wizards

    @api.depends('profit_estimate', 'corporate_tax_rate')
    def _compute_amount_to_pay(self):
        for wizard in self:
            wizard.amount_to_pay = wizard.profit_estimate * int(wizard.corporate_tax_rate) * 0.01 * 0.25

    @api.depends('company_id')
    def _compute_show_warning_missing_vat_number(self):
        for wizard in self:
            wizard.show_warning_missing_vat_number = not bool(wizard.company_id.vat)

    @api.depends('company_id')
    def _compute_communication(self):
        ''' Taken from https://finances.belgium.be/fr/communication-structuree
        '''
        def get_comunication(company):
            try:
                vat, country_code = company.partner_id._run_vat_checks(
                    company.account_fiscal_country_id,
                    company.vat,
                )
            except ValidationError:
                return ""
            if country_code != 'BE' or company.account_fiscal_country_id.code != 'BE':
                return ""
            vat = vat.upper().removeprefix('BE')
            number = int(vat)
            suffix = f"{number % 97 or 97:02}"
            return f"+++{vat[:3]}/{vat[3:7]}/{vat[7:]}{suffix}+++"

        for wizard in self:
            wizard.communication = get_comunication(wizard.company_id)

    @api.depends('partner_bank_id', 'communication', 'amount_to_pay', 'currency_id', 'partner_id')
    def _compute_qr_code(self):
        for wizard in self:
            qr_html = False
            if wizard.partner_bank_id and wizard.currency_id.compare_amounts(wizard.amount_to_pay, 0) > 0 and wizard.communication:
                b64_qr = wizard.partner_bank_id.build_qr_code_base64(
                    amount=wizard.amount_to_pay,
                    free_communication=wizard.communication,
                    structured_communication=wizard.communication,
                    currency=wizard.currency_id,
                    debtor_partner=wizard.partner_id,
                )
                if b64_qr:
                    txt = self.env._('Scan me with your banking app.')
                    qr_html = Markup("""
                        <div class="text-center">
                            <img src="{b64_qr}"/>
                            <p><strong>{txt}</strong></p>
                        </div>
                    """).format(b64_qr=b64_qr, txt=txt)
            wizard.qr_code = qr_html

    def _get_b64_qr_data(self):
        """
        Needed for mail template
        """
        self.ensure_one()
        b64_qr = False
        if self.qr_code:
            tree = html.fromstring(self.qr_code)
            if src_list := tree.xpath('//img/@src'):
                b64_qr = src_list[0]
        return b64_qr

    def action_mark_as_paid(self):
        self.return_id.total_amount_to_pay = self.amount_to_pay
        return self.return_id._action_finalize_payment()

    def action_open_company_configuration_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Set your company data'),
            'res_model': 'res.company',
            'res_id': self.company_id.id,
            'views': [(self.env.ref('account.res_company_form_view_onboarding').id, "form")],
            'target': 'new',
        }
