# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.zeep.wsse.username import UsernameToken


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_edi_certificate_id = fields.Many2one(
        string="Certificate (PE)", store=True, readonly=False,
        comodel_name='certificate.certificate',
        compute="_compute_l10n_pe_edi_certificate")
    l10n_pe_edi_provider_username = fields.Char(
        string="SOL User",
        help="The username used to login to SUNAT SOL",
        groups='base.group_system')
    l10n_pe_edi_provider_password = fields.Char(
        string="SOL Password",
        help="The password used to login to SUNAT SOL",
        groups='base.group_system')
    l10n_pe_edi_provider = fields.Selection(
        selection=[('digiflow', 'Estela (formerly Digiflow)'), ('sunat', 'SUNAT'), ('iap', 'IAP')],
        string="Electronic Service Provider (ESP)", default="iap",
        help="Selector for the service we are going to use to report the invoices:"
             "Estela (formerly DIGIFLOW): With the certificate that estela (formerly digiflow) provided you, user and "
             "password you will report the invoices to them."
             "SUNAT: You will report the invoices directly to them using your own certified, user and password."
             "IAP: This is an odoo service that will send the unsigned documents to a PSE and process their response.")
    l10n_pe_edi_address_type_code = fields.Char(
        string="Address Type Code",
        default="0000",
        help="Code of the establishment that SUNAT has registered.")
    l10n_pe_edi_test_env = fields.Boolean(
        string="Test Environment",
        help='Peru: Electronic documents in this setting are processed through a test environment that does not have a real '
             'SUNAT signature. This mode is recommended only for non-production databases that are used for testing purposes.')

    @api.depends('country_id')
    def _compute_l10n_pe_edi_certificate(self):
        for company in self:
            if company.country_code == 'PE':
                company.l10n_pe_edi_certificate_id = self.env['certificate.certificate'].search(
                    [('company_id', '=', company.id), ('is_valid', '=', True)], limit=1)
            else:
                company.l10n_pe_edi_certificate_id = False

    def _l10n_pe_edi_get_credentials(self, sunat_wsdl=None):
        """Return ESP credentials (WSDL endpoint, WS-Security token, fault NS)
        based on the company's electronic service provider.

        Estela credentials are document-type independent. SUNAT requires a WSDL
        that varies by document (invoice, retention, CDR query) so the caller
        must pass the relevant ``sunat_wsdl`` for its scenario.
        """
        self.ensure_one()
        company_sudo = self.sudo()
        if self.l10n_pe_edi_provider == 'digiflow':
            if self.l10n_pe_edi_test_env:
                return {
                    'fault_ns': 's',
                    'wsdl': 'https://ose-test.com/ol-ti-itcpe/',
                    'token': UsernameToken('20557912879MODDATOS', 'moddatos'),
                }
            return {
                'fault_ns': 's',
                'wsdl': 'https://ose.pe/ol-ti-itcpe/billService',
                'token': UsernameToken(
                    company_sudo.l10n_pe_edi_provider_username,
                    company_sudo.l10n_pe_edi_provider_password,
                ),
            }
        if self.l10n_pe_edi_test_env:
            token = UsernameToken('MODDATOS', 'MODDATOS')
        else:
            token = UsernameToken(
                company_sudo.l10n_pe_edi_provider_username,
                company_sudo.l10n_pe_edi_provider_password,
            )
        return {'fault_ns': 'soap-env', 'wsdl': sunat_wsdl, 'token': token}
