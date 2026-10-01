from odoo.http import request
from odoo.tools import _

from odoo.addons.account.controllers.portal import PortalAccount


class L10nCOPortalAccount(PortalAccount):

    def _is_colombian_company(self):
        return request.env.company.account_fiscal_country_id.code == 'CO'

    def _l10n_co_is_nit(self, values):
        country_id = values.get('country_id')
        if isinstance(country_id, str):
            country_id = int(country_id) if country_id.isdigit() else False
        country = request.env['res.country'].browse(country_id)
        return country.code == 'CO' and bool(values.get('vat'))

    def _parse_form_data(self, form_data):
        # This is needed so that the field is correctly read as list from the request
        if form_data.get('l10n_co_edi_obligation_type_ids'):
            form_data['l10n_co_edi_obligation_type_ids'] = request.httprequest.form.getlist('l10n_co_edi_obligation_type_ids', int)
        # Set default fiscal regimen and obligation types for partners that are not identified by a NIT
        if self._is_colombian_company() and not self._l10n_co_is_nit(form_data):
            default_obligations_ids = request.env['l10n_co_edi.type_code'].sudo().search([('name', 'in', ['R-99-PN'])])
            form_data.update({
                'l10n_co_edi_fiscal_regimen': '49',  # No Aplica
                'l10n_co_edi_obligation_type_ids': default_obligations_ids,
            })
        return super()._parse_form_data(form_data)

    def _prepare_address_form_values(self, *args, **kwargs):
        rendering_values = super()._prepare_address_form_values(*args, **kwargs)

        if self._is_colombian_company():
            rendering_values.update({
                'obligation_types': request.env['l10n_co_edi.type_code'].sudo().search([]),
                'selected_obligation_types_ids': request.httprequest.form.getlist('l10n_co_edi_obligation_type_ids', int) or [],
                'fiscal_regimen_selection': request.env["res.partner"]._fields["l10n_co_edi_fiscal_regimen"].selection,
            })
        return rendering_values

    def _validate_address_values(self, address_values, partner_sudo, address_type, *args, **kwargs):
        invalid_fields, missing_fields, error_messages = super()._validate_address_values(
            address_values, partner_sudo, address_type, *args, **kwargs
        )

        if self._is_colombian_company() and address_type == 'billing':
            if missing_fields and any(
                fname in missing_fields
                for fname in ['l10n_co_edi_obligation_type_ids', 'l10n_co_edi_fiscal_regimen']
            ):
                return invalid_fields, missing_fields, error_messages
            if self._l10n_co_is_nit(address_values):
                if not address_values.get('l10n_co_edi_obligation_type_ids'):
                    missing_fields.add('l10n_co_edi_obligation_type_ids')
                if not address_values.get('l10n_co_edi_fiscal_regimen'):
                    missing_fields.add('l10n_co_edi_fiscal_regimen')
                if len(missing_fields):
                    error_messages.append(_("Indicated Fields are missing."))

        return invalid_fields, missing_fields, error_messages
