# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged

from odoo.addons.website_sale.tests.common import WebsiteSaleCommon
from odoo.addons.website_sale_external_tax.controllers.main import WebsiteSaleDelivery


@tagged('post_install', '-at_install')
class TestWebsiteSaleExternalTaxCalculation(WebsiteSaleCommon, HttpCase):

    _test_user_groups = None  # FIXME list needed groups

    def test_validate_payment_with_error_from_external_provider(self):
        """Payment should be blocked if external tax provider raises an error
        (invalid address, connection issue, etc ...)."""
        self.cart._set_delivery_method(self.free_delivery)
        self.cart.partner_id.write(dict(self.dummy_partner_address_values))

        with patch.object(
            self.env.registry['sale.order'],
            '_get_and_set_external_taxes_on_eligible_records',
            side_effect=UserError('bim bam boom'),
        ):
            response = self.make_jsonrpc_request(
                f'/shop/payment/transaction/{self.cart.id}',
                params={'access_token': self.cart._portal_ensure_token()},
            )

        self.assertURLEqual(response['redirect'], '/shop/payment')
        self.assertIn("bim bam boom", response['state_message'])

    def test_order_summary_values_with_external_tax_error(self):
        """_order_summary_values should return external_tax_error if tax calc fails."""
        so = self.env['sale.order'].create({
            'website_id': self.website.id,
            'partner_id': self.env.user.partner_id.id,
            'order_line': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'price_unit': self.product.list_price,
            })]
        })
        controller = WebsiteSaleDelivery()

        with (
            self.mock_request(sale_order_id=so.id) as req,
            patch.object(
                self.env.registry['sale.order'],
                '_get_and_set_external_taxes_on_eligible_records',
                side_effect=UserError("Simulated external tax failure")
            ),
        ):
            order = req.cart

            res = controller._order_summary_values(order)
            self.assertIn('external_tax_error', res)
            self.assertEqual(res['external_tax_error'], "Simulated external tax failure")

    def test_external_taxes_apply_on_express_checkout(self):
        """Ensure external taxes are computed during express checkout route call."""
        published_product = self.env['product.product'].search(
            [('website_published', '=', True)],
            limit=1,
        )
        self.make_jsonrpc_request("/shop/cart/add", {
            'product_template_id': published_product.product_tmpl_id.id,
            'product_id': published_product.id,
            'quantity': 1,
        })
        partial_shipping_address = {
            'city': "ooo shipping",
            'zip': "6155",
            'country': "AU",
            'state': "WA",
        }

        with patch.object(
            self.env.registry['sale.order'],
            '_get_and_set_external_taxes_on_eligible_records',
        ) as mock:
            self.make_jsonrpc_request(
                WebsiteSaleDelivery._express_checkout_delivery_route, {
                    'partial_delivery_address': partial_shipping_address,
                }
            )
            self.assertEqual(mock.call_count, 1)
