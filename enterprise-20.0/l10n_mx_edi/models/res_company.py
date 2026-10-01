# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

# A CFDI dated day X may not be STAMPED/available at SAT until later (SAT allows to do it
# ~72h later). We use a 4 day lag window to obtain the CFDI that might not have been issued
# on previous requests.
SAT_STAMP_LAG_DAYS = 4

FISCAL_REGIMES_SELECTION = [
    ('601', 'General de Ley Personas Morales'),
    ('603', 'Personas Morales con Fines no Lucrativos'),
    ('605', 'Sueldos y Salarios e Ingresos Asimilados a Salarios'),
    ('606', 'Arrendamiento'),
    ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
    ('608', 'Demás ingresos'),
    ('609', 'Consolidación'),
    ('610', 'Residentes en el Extranjero sin Establecimiento Permanente en México'),
    ('611', 'Ingresos por Dividendos (socios y accionistas)'),
    ('612', 'Personas Físicas con Actividades Empresariales y Profesionales'),
    ('614', 'Ingresos por intereses'),
    ('615', 'Régimen de los ingresos por obtención de premios'),
    ('616', 'Sin obligaciones fiscales'),
    ('620', 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos'),
    ('621', 'Incorporación Fiscal'),
    ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
    ('623', 'Opcional para Grupos de Sociedades'),
    ('624', 'Coordinados'),
    ('625', 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas'),
    ('626', 'Régimen Simplificado de Confianza - RESICO'),
    ('628', 'Hidrocarburos'),
    ('629', 'De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales'),
    ('630', 'Enajenación de acciones en bolsa de valores')]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # == PAC web-services ==
    l10n_mx_edi_pac = fields.Selection(
        selection=[('finkok', 'Quadrum'), ('solfact', 'Solucion Factible'),
                   ('sw', 'SW sapien-SmarterWEB')],
        string='PAC',
        help='The PAC that will sign/cancel the invoices',
        default='finkok')
    l10n_mx_edi_pac_test_env = fields.Boolean(
        string='PAC test environment',
        help='Enable the usage of test credentials',
        default=False)
    l10n_mx_edi_pac_username = fields.Char(
        string='PAC username',
        help='The username used to request the seal from the PAC',
        groups='base.group_system')
    l10n_mx_edi_pac_password = fields.Char(
        string='PAC password',
        help='The password used to request the seal from the PAC',
        groups='base.group_system')
    l10n_mx_edi_certificate_ids = fields.One2many(
        comodel_name='certificate.certificate',
        inverse_name='company_id',
        string='Certificates (MX)',
    )

    # == CFDI EDI ==
    l10n_mx_edi_fiscal_regime = fields.Selection(
        selection=FISCAL_REGIMES_SELECTION,
        string="Fiscal Regime",
        help="It is used to fill Mexican XML CFDI required field "
        "Comprobante.Emisor.RegimenFiscal.")
    l10n_mx_edi_global_invoice_sequence_id = fields.Many2one(
        string="Global Invoice Sequence",
        comodel_name='ir.sequence',
        compute='_compute_l10n_mx_edi_global_invoice_sequence_id',
    )
    l10n_mx_edi_global_invoice_sequence_prefix = fields.Char(
        string="Global Invoice Serie",
        compute='_compute_l10n_mx_edi_global_invoice_sequence_prefix',
        inverse='_inverse_l10n_mx_edi_global_invoice_sequence_prefix',
    )
    l10n_mx_edi_factoring_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Factoring Account",
        check_company=True,
    )

    # == SAT mass download ==
    l10n_mx_edi_last_sync = fields.Date(
        string="Last Sync",
        readonly=True,
        copy=False,
        help="Last date CFDIs were requested from SAT for this company, in the company's timezone.",
        groups="base.group_user",
    )

    @api.depends('account_fiscal_country_id')
    def _compute_l10n_mx_edi_global_invoice_sequence_id(self):
        for company in self:
            if company.account_fiscal_country_id.code == 'MX':
                company.l10n_mx_edi_global_invoice_sequence_id = self.env['ir.sequence'].sudo().search(
                    [('code', '=', 'l10n_mx_global_invoice_cfdi'), ('company_id', '=', company.id)],
                    limit=1,
                )
            else:
                company.l10n_mx_edi_global_invoice_sequence_id = None

    def _create_l10n_mx_edi_global_invoice_sequence(self):
        self.ensure_one()
        return self.env['ir.sequence'].sudo().create({
            'name': f"Global Invoice CFDI ({self.name})",
            'code': 'l10n_mx_global_invoice_cfdi',
            'company_id': self.id,
            'prefix': self.l10n_mx_edi_global_invoice_sequence_prefix,
            'implementation': 'standard',
            'use_date_range': True,
            'padding': 5,
        })

    @api.depends('account_fiscal_country_id')
    def _compute_l10n_mx_edi_global_invoice_sequence_prefix(self):
        for company in self:
            if company.account_fiscal_country_id.code == 'MX':
                if sequence := company.l10n_mx_edi_global_invoice_sequence_id:
                    company.l10n_mx_edi_global_invoice_sequence_prefix = sequence.prefix
                else:
                    company.l10n_mx_edi_global_invoice_sequence_prefix = 'GINV/'
            else:
                company.l10n_mx_edi_global_invoice_sequence_prefix = None

    def _inverse_l10n_mx_edi_global_invoice_sequence_prefix(self):
        for company in self:
            if (
                company.account_fiscal_country_id.code == 'MX'
                and company.l10n_mx_edi_global_invoice_sequence_prefix
            ):
                if sequence := company.l10n_mx_edi_global_invoice_sequence_id:
                    # Update an existing sequence.
                    if sequence.prefix != company.l10n_mx_edi_global_invoice_sequence_prefix:
                        sequence.prefix = company.l10n_mx_edi_global_invoice_sequence_prefix
                else:
                    # Create a specific sequence for the branch only.
                    # By default, only the sequence of the root company is used (GINV/).
                    # The sequence for the root company will be created the first time a global invoice is created.
                    cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(company)
                    if (
                        company != cfdi_values['root_company']
                        and company.l10n_mx_edi_global_invoice_sequence_prefix != cfdi_values['root_company'].l10n_mx_edi_global_invoice_sequence_prefix
                    ):
                        company._create_l10n_mx_edi_global_invoice_sequence()
                        company.invalidate_recordset(fnames=['l10n_mx_edi_global_invoice_sequence_id'])

    def _l10n_mx_edi_get_foreign_customer_fiscal_position(self):
        """Return the fiscal position for foreign customers from the mexican chart template.
           Return an empty fiscal position in case it was not found.
        """
        self.ensure_one()
        fiscal_position = self.env['account.chart.template'].with_company(self).ref('account_fiscal_position_foreign', raise_if_not_found=False)
        return fiscal_position or self.env['account.fiscal.position']

    # -------------------------------------------------------------------------
    # SAT MASS DOWNLOAD
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_get_e_firma_certificate(self):
        """Return the company's valid FIEL (e.firma) certificate if exists."""
        self.ensure_one()
        return self.l10n_mx_edi_certificate_ids.filtered(
            lambda c: c.scope == 'e_firma' and c.is_valid
        )[:1]

    def _l10n_mx_edi_get_sat_credentials(self):
        """Return the company's FIEL and a SAT token to sign mass-download calls with."""
        self.ensure_one()
        certificate = self._l10n_mx_edi_get_e_firma_certificate()
        if not certificate:
            raise UserError(_('Not a valid FIEL certificate was found for request company.'))
        token = certificate._l10n_mx_edi_get_sat_token()
        return certificate, token

    @api.model
    def _cron_l10n_mx_edi_create_company_requests(self):
        companies_to_process = self.search(
            Domain('parent_id', '=', False) & Domain('account_fiscal_country_id.code', '=', 'MX')
            & Domain('currency_id.name', '=', 'MXN') & Domain('chart_template', '=', 'mx')
            & Domain('l10n_mx_edi_certificate_ids', 'any', [('scope', '=', 'e_firma')]),
        )

        IrCron = self.env['ir.cron']
        IrCron._commit_progress(remaining=len(companies_to_process))
        created_requests = self.env['l10n_mx_edi.cfdi.request']
        receipt_type_dict = dict(self.env['l10n_mx_edi.cfdi.request']._fields['receipt_type']._description_selection(self.env))
        for company in companies_to_process:
            tz = company.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone()
            mx_today = datetime.now(tz).date()
            last_sync = company.l10n_mx_edi_last_sync
            if last_sync and last_sync >= mx_today:
                IrCron._commit_progress(1)
                continue

            if not company._l10n_mx_edi_get_e_firma_certificate():
                IrCron._notify_admin(_(
                    "Couldn't sync CFDIs from SAT for Company %(company)s. E-Firma certificate is not valid or has expired. "
                    "Upload a valid ceritificate to keep syncing CFDIs from SAT, or remove/archive current certificate "
                    "to stop receiving this notification.",
                    company=company.display_name))
                IrCron._commit_progress(1)
                continue

            emission_date_from = (last_sync or mx_today) - timedelta(days=SAT_STAMP_LAG_DAYS)
            emission_date_to = mx_today - timedelta(days=1)
            if lock_dates := company._get_lock_date_violations(emission_date_from):
                latest_lock = max(d for d, _field in lock_dates)
                emission_date_from = latest_lock + timedelta(days=1)
                if emission_date_from > emission_date_to:
                    company.l10n_mx_edi_last_sync = emission_date_from
                    IrCron._commit_progress(1)
                    continue

            request_vals = [
                {
                    'company_id': company.id,
                    'request_type': 'batch_received',
                    'receipt_type': receipt_type,
                    'emission_date_from': emission_date_from,
                    'emission_date_to': emission_date_to,
                }
                for receipt_type in receipt_type_dict
            ]

            new_requests = self.env['l10n_mx_edi.cfdi.request']
            for vals in request_vals:
                try:
                    new_requests |= new_requests._send_and_create_new_request(vals)
                except Exception as err:  # noqa: BLE001
                    _logger.exception(
                        "Automatic CFDI request creation for company %s from %s to %s failed.",
                        company.display_name, emission_date_from, mx_today,
                    )
                    new_requests |= new_requests.create({
                        **vals,
                        'state': 'rejected',
                        'message': _("Failed to create automatic company request: %s", str(err)),
                    })

            created_requests |= new_requests

            if failed_requests := new_requests.filtered(lambda request: request.state != 'in_process_at_sat'):
                IrCron._notify_admin(_(
                    "Failed to request the CFDIs of company %(company)s for %(date_from)s - %(date_to)s. More info:\n"
                    "%(causes)s",
                    company=company.display_name, date_from=emission_date_from, date_to=emission_date_to,
                    causes="\n".join(self.env._(
                        "- Request for %(receipt_type)s CFDIs failed with: %(message)s",
                        receipt_type=receipt_type_dict[request.receipt_type],
                        message=request.message,
                    ) for request in failed_requests),
                ))
            company.l10n_mx_edi_last_sync = mx_today

            if not IrCron._commit_progress(1):
                break

        return created_requests
