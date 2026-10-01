# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase, patch, tagged

from odoo.addons.google_address_autocomplete.controllers.google_address_autocomplete import (
    AutoCompleteController,
)


MOCK_GOOGLE_ID = 'aHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1kUXc0dzlXZ1hjUQ=='
MOCK_API_KEY = 'Tm9ib2R5IGV4cGVjdHMgdGhlIFNwYW5pc2ggaW5xdWlzaXRpb24gIQ=='


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPeruvianAutocomplete(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['product.product'].create({
            'name': 'A test product',
            'website_published': True,
            'list_price': 1,
        })

    def test_autocomplete_pe(self):
        website = self.env.ref('base.default_website')
        peru_country = self.env.ref("base.pe")
        website.company_id.account_fiscal_country_id = website.company_id.country_id = peru_country

        target_state = self.env['res.country.state'].search([('country_id', '=', peru_country.id)], limit=1)
        target_city = self.env['res.city'].search([('state_id', '=', target_state.id)], limit=1)

        with patch.object(AutoCompleteController, '_perform_complete_place_search',
                          lambda controller, *args, **kwargs: {
                              'country': [peru_country.id, 'Peru'],
                              'state': [target_state.id, target_state.name],
                              'city_id': [target_city.id, target_city.name],
                              'zip': '15001',
                              'street': 'Avenida Larco',
                              'street_number': '123',
                              'formatted_street_number': '123 Avenida Larco',
                          }), \
                patch.object(AutoCompleteController, '_perform_place_search',
                             lambda controller, *args, **kwargs: {
                                 'results': [{
                                     'formatted_address': f'Peru Result {x}',
                                     'google_place_id': MOCK_GOOGLE_ID
                                 } for x in range(5)]}):
            website.google_places_api_key = MOCK_API_KEY
            self.start_tour('/shop', 'autocomplete_pe_tour')
