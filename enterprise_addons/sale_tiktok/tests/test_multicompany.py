# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from unittest.mock import patch

from freezegun import freeze_time

from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.sale_tiktok.tests import common


@tagged("post_install", "-at_install")
class TestTikTokMultiCompany(common.TestTikTokShopCommon):
    def setUp(self):
        super().setUp()
        self.branch_company = self.env["res.company"].create({
            "name": "Test branch company",
            "currency_id": self.env.company.currency_id.id,
            "parent_id": self.env.company.id,
        })
        self.parent_tax = self.env["account.tax"].create({
            "name": "Test Tax",
            "company_id": self.env.company.id,
        })
        self.other_tiktok_shop = self.env["tiktok.shop"].create({
            "app_key": "dummy_app_key",
            "app_secret": "dummy_app_secret",
            "service_extern_id": "dummy_service",
            "name": "other_dummy_name",
            "tiktok_shop_ref": "other_dummy_shop_id",
            "tiktok_cipher": "other_dummy_cipher",
            "last_orders_sync_date": self.initial_sync_date,
            "access_token": "dummy_access_token",
            "access_token_expire_datetime": datetime(2020, 6, 1),
            "refresh_token": "dummy_refresh_token",
            "refresh_token_expire_datetime": datetime(2025, 6, 1),
        })

    @freeze_time("2020-02-01")
    @mute_logger("odoo.addons.sale_tiktok.models.tiktok_shop")
    def test_tax_application_on_sync_order_for_branch_company(self):
        """Test the orders synchronization can assign taxes from parent company.

        product_line and shipping_line should have the same tax as the parent tax.
        """

        def find_matching_product_mock(
            _self, product_code_, _default_xmlid, default_name_, default_type_
        ):
            product_ = self.env["product.product"].create({
                "name": default_name_,
                "type": default_type_,
                "list_price": 0.0,
                "sale_ok": False,
                "purchase_ok": False,
                "default_code": product_code_,
            })
            product_.product_tmpl_id.taxes_id = self.parent_tax
            return product_

        def mocked_make_request(_shop, operation, *_args, **_kwargs):
            return common.OPERATIONS_RESPONSES_MAP[operation]

        with (
            patch("odoo.addons.sale_tiktok.utils.make_tiktok_api_request", new=mocked_make_request),
            patch(
                "odoo.addons.sale_tiktok.models.tiktok_shop.TikTokShop._compute_subtotal",
                new=lambda _shop, subtotal_, *_args, **_kwargs: subtotal_,
            ),
            patch(
                "odoo.addons.sale_tiktok.models.tiktok_shop.TikTokShop._find_matching_product",
                new=find_matching_product_mock,
            ),
        ):
            self.other_tiktok_shop._sync_orders(auto_commit=False)
            expected_dt = datetime.fromtimestamp(
                common.OPERATIONS_RESPONSES_MAP["get_order_list"]["orders"][0]["update_time"]
            )
            self.assertEqual(self.other_tiktok_shop.last_orders_sync_date, expected_dt)

            order = self.env["sale.order"].search([("tiktok_order_ref", "=", common.ORDER_ID_MOCK)])
            order_lines = self.env["sale.order.line"].search([("order_id", "=", order.id)])
            product_line = order_lines.filtered(lambda line: line.product_id.default_code == "1234")

            self.assertEqual(len(order), 1)
            self.assertEqual(order.company_id.id, self.other_tiktok_shop.company_id.id)
            self.assertEqual(len(order_lines), 2)  # product line + shipping
            self.assertEqual(product_line.price_unit, 10000.0)
            self.assertEqual(product_line.tax_ids, self.parent_tax)
