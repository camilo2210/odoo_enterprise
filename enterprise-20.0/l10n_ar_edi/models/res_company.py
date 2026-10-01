# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import random
from datetime import datetime

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, BinaryBytes, file_open

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_afip_verification_type = fields.Selection([('not_available', 'Not Available'), ('available', 'Available'), ('required', 'Required')], required=True,
        default='not_available', string='ARCA Invoice Verification', help='It adds an option on invoices to'
        ' verify the invoices in ARCA if the invoices has CAE, CAI or CAEA numbers.\n\n'
        '* Not Available: Will NOT show "Verify on ARCA" button in the invoices\n'
        '* Available: Will show "Verify on ARCA" button in the invoices so the user can manually check the vendor'
        ' bills\n'
        '* Required: The vendor bills will be automatically verified on ARCA before been posted in Odoo. This is to'
        ' ensure that you have verified all the vendor bills that you are reporting in your Purchase VAT Book. NOTE:'
        ' Not all the document types can be validated in ARCA, only the ones defined in this link are the ones that '
        ' we are automatically validating https://serviciosweb.afip.gob.ar/genericos/comprobantes/Default.aspx')

    l10n_ar_connection_ids = fields.One2many('l10n_ar.afipws.connection', 'company_id', 'Connections')

    # Certificate fields
    l10n_ar_afip_ws_environment = fields.Selection([('testing', 'Testing'), ('production', 'Production')], string="ARCA Environment", default='production',
        help="Environment used to connect to ARCA webservices. Production is to create real fiscal invoices in ARCA,"
        " Testing is for testing invoice creation in ARCA (commonly named in ARCA as Homologation environment).")
    l10n_ar_afip_ws_key_id = fields.Many2one(string='Private Key', comodel_name='certificate.key', domain=[('public', '=', False)],
        compute="_compute_afip_key", store=True, readonly=False,
        help="This private key is required because is sent to the ARCA when"
        " trying to create a connection to validate that you are you\n\n * If you have one you can upload it here (In"
        " order to be valid the private key should be in PEM format)\n * if you have not then Odoo will automatically"
        " create a new one when you click in 'Generate Request' or 'Generate Renewal Request' button")
    l10n_ar_afip_ws_crt_id = fields.Many2one(string='ARCA Certificate', comodel_name="certificate.certificate",
        compute="_compute_afip_crt", store=True, readonly=False,
        help="This certificate lets us connect to ARCA to validate electronic invoice."
        " Please select here the ARCA certificate in PEM format. You can get your certificate from your ARCA Portal")
    l10n_ar_fce_transmission_type = fields.Selection(
        [('SCA', 'SCA - TRANSFERENCIA AL SISTEMA DE CIRCULACION ABIERTA'), ('ADC', 'ADC - AGENTE DE DEPOSITO COLECTIVO')],
        'FCE: Transmission Option Default',
        help='Default value for "FCE: Transmission Option" on electronic invoices')
    l10n_ar_payment_foreign_currency = fields.Selection(
        selection=[("Yes", "Yes"), ("No", "No"), ("account", "Account's Currency Dependant")],
        compute="_compute_l10n_ar_payment_foreign_currency",
        string="Default Policy for Payment in Foreign Currency",
    )
    l10n_ar_invoice_pdf_legend = fields.Selection(
        selection=[
            ('payment_on_informed_cbu', 'Payment on Informed CBU'),
            ('operation_subject_to_withholding', 'Operation Subject to Withholding')
        ],
        compute="_compute_l10n_ar_invoice_pdf_legend",
        store=True,
        readonly=False,
        help="Selected legend value will be added below the Document Type letter on the Invoice PDF.")

    # Currency Rate ARCA
    currency_provider = fields.Selection(
        selection_add=[('arca', "[AR] ARCA")],
    )

    def _get_country_wise_currency_providers(self):
        res = super()._get_country_wise_currency_providers()
        res['AR'] = 'arca'
        return res

    def _compute_l10n_ar_payment_foreign_currency(self):
        for company in self:
            company.l10n_ar_payment_foreign_currency = self.env["ir.config_parameter"].sudo().get_str(
                f"l10n_ar_edi.{company.id}_foreign_currency_payment") or "No"

    @api.depends('country_code')
    def _compute_l10n_ar_invoice_pdf_legend(self):
        for company in self:
            if company.country_code != 'AR':
                company.l10n_ar_invoice_pdf_legend = False

    @api.depends('l10n_ar_afip_ws_key_id')
    def _compute_afip_crt(self):
        key_ids = self.l10n_ar_afip_ws_key_id.ids
        certs = self.env['certificate.certificate'].search([('private_key_id', 'in', key_ids)])
        key_to_cert = {cert.private_key_id: cert for cert in certs}
        key_to_cert[False] = False
        for company in self:
            if company.country_code != 'AR':
                continue
            if not company.l10n_ar_afip_ws_crt_id:
                company.l10n_ar_afip_ws_crt_id = key_to_cert.get(company.l10n_ar_afip_ws_key_id)
            else:
                company.l10n_ar_afip_ws_crt_id.private_key_id = company.l10n_ar_afip_ws_key_id

    @api.depends('l10n_ar_afip_ws_crt_id.private_key_id')
    def _compute_afip_key(self):
        for company in self:
            if company.country_code != 'AR':
                continue
            company.l10n_ar_afip_ws_key_id = company.l10n_ar_afip_ws_crt_id.private_key_id

    def _get_environment_type(self):
        """ This method is used to return the environment type of the company (testing or production) and will raise an
        exception when it has not been defined yet """
        self.ensure_one()
        if not self.l10n_ar_afip_ws_environment:
            raise UserError(_('ARCA environment not configured for company “%s”, please check accounting settings', self.name))
        return self.l10n_ar_afip_ws_environment

    def _l10n_ar_get_connection(self, afip_ws):
        """ Returns the last existing connection with ARCA web service, or creates a new one  (which means login to ARCA
        and save token information in a new connection record in Odoo)

        IMPORTANT WARNING: Be careful using this method, when a new connection is created, it will do a cr.commit() """
        self.ensure_one()
        if not afip_ws:
            raise UserError(_('No ARCA WS selected'))

        env_type = self._get_environment_type()
        connection = self.l10n_ar_connection_ids.search([('type', '=', env_type), ('l10n_ar_afip_ws', '=', afip_ws), ('company_id', '=', self.id)], limit=1)

        if connection and connection.expiration_time > fields.Datetime.now():
            return connection

        token_data = connection._l10n_ar_get_token_data(self, afip_ws)
        if connection:
            connection.sudo().write(token_data)
        else:
            values = {'company_id': self.id, 'l10n_ar_afip_ws': afip_ws, 'type': env_type}
            values.update(token_data)
            _logger.info('Connection created for company %s %s (%s)' % (self.name, afip_ws, env_type))
            connection = connection.sudo().create(values)

        # This commit is needed because we need to maintain the connection information no matter if the invoices have
        # been validated or not. This because when we request a token we can not generate a new one until the last
        # one expires.
        if not self.env.context.get('l10n_ar_invoice_skip_commit'):
            self.env.cr.commit()
        _logger.info("Successful Authenticated with ARCA.")

        return connection

    def set_demo_random_cert(self):
        """ Method used to assign a random certificate to the company. This method is called when loading demo data to
        assign a random certificate to the demo companies. It is also available as button in the res.config.settings
        wizard to let the user change the certificate randomly if the one been set is blocked (because someone else
        is using the same certificate in another database) """
        for company in self:
            if company.country_code != 'AR':
                continue
            old_cert_name = company.l10n_ar_afip_ws_crt_id.name
            rid = random.randint(1, 10)
            new_cert_name = 'AR demo certificate %d' % rid
            new_cert = self.env['certificate.certificate'].search([('name', '=', new_cert_name), ('company_id', '=', company.id)], limit=1)
            if not new_cert:
                with file_open('l10n_ar_edi/demo/cert%d.crt' % rid, 'rb') as f:
                    cert_file_content = BinaryBytes(f.read())
                new_cert = self.env['certificate.certificate'].create({
                    'name': new_cert_name,
                    'content': cert_file_content,
                    'private_key_id': company.l10n_ar_afip_ws_key_id.id,
                    'company_id': company.id,
                })
            company.l10n_ar_afip_ws_crt_id = new_cert
            _logger.log(25, 'Setting demo certificate from %s to %s in %s company', old_cert_name, new_cert_name, company.name)

    def _parse_arca_data(self, available_currencies):
        """Fetch the currency rates from ARCA based on the ARCA Currency Code."""
        if not (self.l10n_ar_afip_ws_key_id and self.l10n_ar_afip_ws_crt_id):
            raise UserError(
                _("Please set the ARCA Certificate and Private Key in order to fetch currency rates from ARCA")
            )
        if missing_arca_code := available_currencies.filtered(lambda c: not c.l10n_ar_afip_code):
            raise UserError(_(
                "The following currencies do not have ARCA Code: %s. "
                "Please add the required codes or archive these currencies, then click Update again.",
                ', '.join(missing_arca_code.mapped('name'))
            ))

        result = {}
        ar_currency = self.env.ref('base.ARS')
        arca_date = fields.Datetime.today()
        currency_rates = (available_currencies - ar_currency)._l10n_ar_get_last_business_day_rate(date_formatting=False)
        for name, (date, rate) in currency_rates.items():
            if not rate:
                continue
            currency_date = datetime.strptime(date, '%Y%m%d') + relativedelta(days=1)
            if currency_date < arca_date:
                arca_date = currency_date
            result[name] = (1 / rate, currency_date.strftime(DEFAULT_SERVER_DATE_FORMAT))

        # Default ARS rate
        result['ARS'] = (1.0, arca_date.strftime(DEFAULT_SERVER_DATE_FORMAT))
        return result
