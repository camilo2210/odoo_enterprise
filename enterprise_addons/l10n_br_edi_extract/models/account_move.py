# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools.misc import clean_context


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_partner(self, ocr_results):
        """Create or find partner from NFSe OCR results."""
        nfse_data = ocr_results.get('nfse')
        if not nfse_data:
            return super()._get_partner(ocr_results)

        supplier_ocr = self._get_ocr_selected_value(ocr_results, 'supplier', "")
        vat_number_ocr = self._get_ocr_selected_value(ocr_results, 'VAT_Number', "")
        email_ocr = self._get_ocr_selected_value(ocr_results, 'email', "")
        phone_ocr = self._get_ocr_selected_value(ocr_results, 'phone', "")
        country_code_ocr = self._get_ocr_selected_value(ocr_results, 'country', "")

        # Try to find an existing partner
        partner_id = self._find_partner_id_with_name(supplier_ocr)
        if partner_id != 0:
            return self.env['res.partner'].browse(partner_id), False

        # Address info
        address_ocr = nfse_data.get('address', "")
        neighbor_ocr = nfse_data.get('neighbor', "")
        city_ocr = nfse_data.get('city', "")
        state_ocr = nfse_data.get('state', "")
        zip_ocr = nfse_data.get('zip', "")
        municipal_registration_ocr = nfse_data.get('municipal_registration', "")
        state_registration_ocr = nfse_data.get('state_registration', "")

        cpf_vals = self.env['res.partner']._validate_identifier('BR_CN', vat_number_ocr) if vat_number_ocr else {}
        is_cpf = cpf_vals.get('valid')
        partner_vals = {
            'name': supplier_ocr,
            'is_company': True,
            'vat': vat_number_ocr if not is_cpf else False,
            'additional_identifiers': {'BR_CN': cpf_vals['value']} if is_cpf else False,
            'email': email_ocr,
            'phone': phone_ocr,
            'street': address_ocr,
            'street2': neighbor_ocr,
            'city_id': self.env['res.city'].with_context(lang='en_US').search([
                ('name', '=ilike', city_ocr)
            ], limit=1).id,
            'city': city_ocr,
            'state_id': self.env['res.country.state'].with_context(lang='en_US').search([
                '|',
                ('code', '=', state_ocr),
                ('name', '=ilike', state_ocr),
                ('country_id.code', '=', country_code_ocr)
            ], limit=1).id,
            'zip': zip_ocr,
            'country_id': self.env['res.country'].search([
                ('code', '=', country_code_ocr)
            ], limit=1).id,
            'company_id': self.company_id.id,
            'l10n_br_im_code': municipal_registration_ocr,
            'l10n_br_ie_code': state_registration_ocr,
            'is_created_by_ocr': True,
        }
        partner = self.env['res.partner'].with_context(clean_context(self.env.context)).create(partner_vals)
        return partner.id, True

    def _fill_document_with_results(self, ocr_results):
        super()._fill_document_with_results(ocr_results)
        self = self.with_context(skip_is_manually_modified=True)  # noqa: PLW0642
        if self.state != 'draft' or ocr_results is None:
            return

        nfse_data = ocr_results.get('nfse')
        if nfse_data:
            self.write({
                'l10n_br_access_key': nfse_data.get('access_key', ""),
                'l10n_br_nfse_number': nfse_data.get('number', ""),
                'l10n_latam_document_number': nfse_data.get('number', ""),
                'l10n_br_nfse_verification': nfse_data.get('verification_code', ""),
                'l10n_latam_document_type_id': self.env.ref('l10n_br.dt_SE').id,
            })
