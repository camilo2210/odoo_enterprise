# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase, patch, tagged

from odoo.addons.google_address_autocomplete.controllers.google_address_autocomplete import (
    AutoCompleteController,
)


MOCK_GOOGLE_ID = 'aHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1kUXc0dzlXZ1hjUQ=='
MOCK_API_KEY = 'Tm9ib2R5IGV4cGVjdHMgdGhlIFNwYW5pc2ggaW5xdWlzaXRpb24gIQ=='


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBrazilianAutocomplete(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['product.product'].create({
            'name': 'A test product',
            'website_published': True,
            'list_price': 1,
        })

    def test_autocomplete_br(self):
        website = self.env.ref('base.default_website')
        website.company_id.account_fiscal_country_id = website.company_id.country_id = self.env.ref("base.br")

        with patch.object(AutoCompleteController, '_perform_complete_place_search',
                          lambda controller, *args, **kwargs: {
                              'country': [self.env['res.country'].search([('code', '=', 'BR')]).id, 'Brazil'],
                              'zip': '12345',
                              'street': 'Hello world',
                              'street_number': '42',
                              'street2': 'Bye Bye',
                          }), \
                patch.object(AutoCompleteController, '_perform_place_search',
                             lambda controller, *args, **kwargs: {
                                 'results': [{
                                     'formatted_address': f'Result {x}',
                                     'google_place_id': MOCK_GOOGLE_ID
                                 } for x in range(5)]}):
            website.google_places_api_key = MOCK_API_KEY
            self.start_tour('/shop', 'autocomplete_br_tour')
