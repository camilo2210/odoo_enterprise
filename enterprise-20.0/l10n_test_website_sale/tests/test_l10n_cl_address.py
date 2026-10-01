# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, HttpCase


@tagged("post_install_l10n", "post_install", "-at_install")
class TestChileAddress(HttpCase):
    def test_chile_address_frontend(self):
        website = self.env.ref('base.default_website')
        website.company_id.account_fiscal_country_id = website.company_id.country_id = self.env.ref("base.cl")

        self.env["product.product"].create(
            {
                "name": "Chile test product",
                "list_price": 12.50,
                "is_published": True,
            }
        )
        self.start_tour("/shop?search=Chile test product", "test_chile_address")
