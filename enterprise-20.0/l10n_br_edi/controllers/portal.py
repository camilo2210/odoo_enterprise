# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request

from odoo.addons.account.controllers.portal import PortalAccount


class L10nBREdiPortalAccount(PortalAccount):

    def _complete_address_values(self, address_values, *args, **kwargs):
        """ Override. Complete the address for EDI in the B2C case (CPF identification). """
        super()._complete_address_values(address_values, *args, **kwargs)
        if 'BR_CN' in (address_values.get('additional_identifiers') or {}):
            fiscal_position = request.env['account.fiscal.position'].sudo().search([
                ('company_id', '=', request.env.company.id), ('l10n_br_is_avatax', '=', True)
            ], limit=1)
            address_values.update({
                'property_account_position_id': fiscal_position.id,
                'l10n_br_tax_regime': 'individual',
                'l10n_br_taxpayer': 'non',
                'l10n_br_activity_sector': 'finalConsumer',
                'l10n_br_subject_cofins': 'T',
                'l10n_br_subject_pis': 'T',
                'l10n_br_is_subject_csll': True,
            })
