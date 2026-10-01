# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import fields, models, api
from odoo.addons.l10n_co.tools.partner_identifiers import CO_NIT_DIAN_CODE
from odoo.addons.l10n_co_edi import xml_utils
from odoo.exceptions import UserError

FINAL_CONSUMER_VAT = '222222222222'  # 'Consumidor Final' is the generic partner used in B2C


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_co_edi_large_taxpayer = fields.Boolean(string='Gran Contribuyente')
    l10n_co_edi_fiscal_regimen = fields.Selection([
        ('48', 'IVA'),
        ('49', 'No Aplica'),
        ('04', 'IC'),
        ('ZA', 'IVA en IC'),
    ], string="Fiscal Regimen", required=True, default='48')
    l10n_co_edi_commercial_name = fields.Char('Commercial Name')
    l10n_co_edi_obligation_type_ids = fields.Many2many('l10n_co_edi.type_code',
                                                       'partner_l10n_co_edi_obligation_types',
                                                       'partner_id', 'type_id',
                                                       string='Obligaciones y Responsabilidades')

    l10n_co_edi_enable_update_data = fields.Boolean(compute='_compute_l10n_co_edi_enable_update_data')

    @api.depends_context('company')
    @api.depends('l10n_co_dian_id_code', 'l10n_co_dian_id_value')
    def _compute_l10n_co_edi_enable_update_data(self):
        for partner in self:
            company = self.env.company
            partner.l10n_co_edi_enable_update_data = (
                company.account_fiscal_country_id.code == 'CO'
                and partner.l10n_co_dian_id_code
                and partner.l10n_co_dian_id_value
                and not partner.parent_id
            )

    # if country_code is not part of the onchange then the _l10n_co_edi_update_data method
    # will not correctly trigger if the user fills in the identification and
    # vat fields before filling in the country field
    @api.onchange('additional_identifiers', 'vat')
    def _l10n_co_edi_onchange_identification_type(self):
        for partner in self:
            company = self.env.company
            if partner.l10n_co_edi_enable_update_data and company.sudo().l10n_co_edi_certificate_ids:
                partner._l10n_co_edi_update_data(company)

    def button_l10n_co_edi_refresh_data(self):
        self._l10n_co_edi_update_data(self.env.company)

    def _l10n_co_edi_update_data(self, company):
        self.ensure_one()
        partner = self.commercial_partner_id
        data = partner._l10n_co_edi_call_get_acquirer({
            'identification_type': partner._l10n_co_edi_get_identification_type_code(),
            'identification_number': partner._get_vat_without_verification_code(),
            'company': company,
        })

        if not data or data.get('email') == partner.email:
            return
        if not partner.email:
            partner.write(data)
            return

        if partner.child_ids.filtered(lambda p: 'invoice' in p.type):
            raise UserError(self.env._(
                "This contact has already been updated with DIAN information, please review the related invoicing address contact and see if it matches the data returned from DIAN:\nEmail: %(partner_email)s\nName: %(partner_name)s",
                partner_email=data.get('email'),
                partner_name=data.get('name'),
            ))

        self.env['res.partner'].create({
            **data,
            'parent_id': partner.id,
            'type': 'invoice',
        })

    @api.model
    def _l10n_co_edi_call_get_acquirer(self, data: dict):
        if not self.env.ref('l10n_co_edi.get_acquirer', raise_if_not_found=False):
            # Could happen when the user did not update their db
            return dict()

        response = xml_utils._build_and_send_request(
            self,
            payload={
                'identification_type': data['identification_type'],
                'identification_number': data['identification_number'],
                'soap_body_template': "l10n_co_edi.get_acquirer",
            },
            service='GetAcquirer',
            company=data['company'],
        )

        if response['status_code'] != 200:
            return dict()

        root = etree.fromstring(response['response'])
        return {
            'email': root.findtext('.//{*}ReceiverEmail'),
            'name': root.findtext('.//{*}ReceiverName'),
        }

    @api.depends('l10n_co_edi_obligation_type_ids')
    def _compute_is_company(self):
        # EXTENDS 'base'
        co_partners = self.filtered(lambda p: p.country_code == 'CO')
        for partner in co_partners:
            partner.is_company = bool(
                partner.has_vat
                and partner.commercial_partner_id == partner
                and 'R-99-PN' not in partner.l10n_co_edi_obligation_type_ids.mapped('name')
            )
        super(ResPartner, self - co_partners)._compute_is_company()

    @api.model
    def _commercial_fields(self):
        return super()._commercial_fields() + [
            'l10n_co_edi_fiscal_regimen',
            'l10n_co_edi_obligation_type_ids',
            'l10n_co_edi_large_taxpayer',
            'l10n_co_edi_commercial_name',
        ]

    def _get_frontend_writable_fields(self):
        frontend_writable_fields = super()._get_frontend_writable_fields()
        frontend_writable_fields.update({
            'l10n_co_edi_fiscal_regimen',
            'l10n_co_edi_obligation_type_ids',
        })

        return frontend_writable_fields

    def _get_vat_without_verification_code(self):
        self.ensure_one()
        # only the NIT (DIAN code 31) carries a verification code as its last digit (possibly after a -)
        number = self.l10n_co_dian_id_value or ''
        if self.l10n_co_dian_id_code != CO_NIT_DIAN_CODE or number == FINAL_CONSUMER_VAT:
            return number
        elif number and "-" in number:
            return number.split('-')[0]
        return number[:-1] if number else ''

    def _get_vat_verification_code(self):
        self.ensure_one()
        number = self.l10n_co_dian_id_value or ''
        if self.l10n_co_dian_id_code != CO_NIT_DIAN_CODE:
            return ''
        elif number and "-" in number:
            return number.split('-')[1]
        return number[-1] if number else ''

    def _l10n_co_edi_get_partner_type(self):
        self.ensure_one()
        return '1' if self.is_company else '2'

    def _l10n_co_edi_get_identification_type_code(self):
        self.ensure_one()
        return self.l10n_co_dian_id_code or ''

    def _l10n_co_edi_get_company_address(self):
        """
        Function forms address of the company avoiding duplicity. contact_address attribute holds the complete address
        of company, which should not be used.
        Information like city, state which is already sent in other tags should be excluded from the company's address.
        """
        self.ensure_one()
        return '%s %s' % (self.street or '', self.street2 or '')

    def _l10n_co_edi_get_fiscal_regimen_code(self):
        if self.l10n_co_edi_fiscal_regimen == '48':
            return '01'
        if self.l10n_co_edi_fiscal_regimen == '49':
            return 'ZZ'
        return self.l10n_co_edi_fiscal_regimen

    def _l10n_co_edi_get_fiscal_regimen_name(self):
        return dict(self._fields["l10n_co_edi_fiscal_regimen"]._description_selection(self.env)).get(self.l10n_co_edi_fiscal_regimen)
