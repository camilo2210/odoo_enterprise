# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.sale_shopee.tests import common


@tagged("post_install", "-at_install")
class TestShopeeMultiCompany(common.TestShopeeCommon):
    def setUp(self):
        super().setUp()
        self.branch_company = self.env["res.company"].create({
            "name": "Test branch company",
            "currency_id": self.env.company.currency_id.id,
            "parent_id": self.env.company.id,
        })
        self._test_user.company_ids = [Command.link(self.branch_company.id)]
        self.parent_tax = self.env["account.tax"].create({
            "name": "Test Tax",
            "company_id": self.env.company.id,
        })
        self.other_shopee_account = self.env["shopee.account"].create({
            "name": "TestAnotherAccountName",
            "partner_identifier": 1,
            "partner_key": "A partner token",
            "api_endpoint": "test",
            "company_ids": [self.branch_company.id],
        })
        self.other_shopee_shop = self.env["shopee.shop"].create({
            "name": "TestAnotherShopeName",
            "shop_identifier": 1,
            "account_id": self.other_shopee_account.id,
            "status": "active",
            "authorization_expiration_date": datetime.now() + timedelta(days=365),
            "last_orders_sync_date": self.initial_sync_date,
        })

    @freeze_time("2020-02-01")
    @mute_logger("odoo.addons.sale_shopee.models.shopee_shop")
    def test_tax_application_on_sync_order_for_branch_company(self):
        """Test the orders synchronization can assign taxes from parent company.

        product_line and shipping_line should have the same tax as the parent tax.
        """

        def find_matching_product_mock(
            _self, product_code_, _default_xmlid, default_name_, default_type_
        ):
            """Return a product created on-the-fly with the product code as internal reference."""
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

        def api_mock(_shop, operation_, *_args):
            if operation_ == "get_escrow_detail":
                return common.build_escrow_mock()
            return common.OPERATIONS_RESPONSES_MAP[operation_]

        with (
            patch("odoo.addons.sale_shopee.utils.make_shopee_api_request", new=api_mock),
            patch(
                "odoo.addons.sale_shopee.models.shopee_shop.ShopeeShop._recompute_subtotal",
                new=lambda _shop, subtotal_, *_args, **_kwargs: subtotal_,
            ),
            patch(
                "odoo.addons.sale_shopee.models.shopee_shop.ShopeeShop._find_matching_product",
                new=find_matching_product_mock,
            ),
        ):
            self.other_shopee_shop._sync_orders(auto_commit=False)
            self.assertEqual(self.other_shopee_shop.last_orders_sync_date, datetime.now())

            order = self.env['sale.order'].search([('shopee_order_ref', '=', 'O123456789')])
            order_lines = self.env['sale.order.line'].search([('order_id', '=', order.id)])
            product_line = order_lines.filtered(lambda l: l.product_id.default_code == 'TEST_SKU')
            shipping_line = order_lines - product_line

            self.assertEqual(len(order), 1)
            self.assertEqual(order.company_id.id, self.other_shopee_shop.company_id.id)
            self.assertEqual(len(order_lines), 2)  # product line + shipping line
            self.assertEqual(product_line.price_unit, 40.0)
            self.assertEqual(product_line.tax_ids, self.parent_tax)
            self.assertEqual(shipping_line.tax_ids, self.parent_tax)
