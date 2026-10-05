# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.sale_lazada.tests import common


@tagged("post_install", "-at_install")
class TestLazadaMultiCompany(common.TestLazadaCommon):
    def setUp(self):
        super().setUp()
        self.branch_company = self.env["res.company"].create({
            "name": "Test branch company",
            "currency_id": self.env.company.currency_id.id,
            "parent_id": self.env.company.id,
        })
        self._test_user.company_ids = [Command.link(self.branch_company.id)]
        self.branch_warehouse = self.env["stock.warehouse"].create({
            "name": "Branch Warehouse",
            "code": "BRANCH",
            "company_id": self.branch_company.id,
        })
        self.parent_tax_group = self.env["account.tax.group"].create({
            "name": "Test Tax Group",
            "company_id": self.env.company.id,
        })
        self.parent_tax = self.env["account.tax"].create({
            "name": "Test Tax",
            "company_id": self.env.company.id,
        })
        self.other_lazada_shop = self.env["lazada.shop"].create({
            "name": "TestAnotherShopeName",
            "company_id": self.branch_company.id,
            "country_id": self.env.ref("base.vn").id,
            "app_key": "2",
            "app_secret": "A different app secret",
            "shop_extern_id": "50002",
            "access_token": "test_access_token",
            "access_token_expiration_date": fields.Datetime.now() + timedelta(hours=4),
            "refresh_token": "test_refresh_token",
            "refresh_token_expiration_date": fields.Datetime.now() + timedelta(days=30),
            "last_orders_sync_date": self.initial_sync_date,
            "last_product_catalog_sync_date": self.initial_sync_date,
            "fbm_warehouse_id": self.branch_warehouse.id,
        })

    @freeze_time("2020-02-01")
    @mute_logger("odoo.addons.sale_lazada.models.lazada_shop")
    def test_tax_application_on_sync_order_for_branch_company(self):
        """
        Test the orders synchronization can assign taxes from parent company.

        product_line should have the same tax as the parent tax.
        """

        def find_matching_product_mock(
            _self, internal_reference, default_xmlid, default_name, default_type, **_kwargs
        ):
            """Return a product created on-the-fly with the product code as internal reference."""
            product_ = self.env["product.product"].create({
                "name": default_name,
                "type": default_type,
                "list_price": 0.0,
                "sale_ok": True,
                "purchase_ok": False,
                "is_storable": True,
                "default_code": internal_reference,
            })
            product_.product_tmpl_id.taxes_id = self.parent_tax
            return product_

        with (
            patch(
                "odoo.addons.sale_lazada.utils.make_lazada_api_request",
                new=lambda operation, _shop, *_args, **_kwargs: common.OPERATIONS_RESPONSES_MAP[
                    operation
                ],
            ),
            patch(
                "odoo.addons.sale_lazada.models.lazada_shop.LazadaShop._compute_subtotal",
                new=lambda _shop, subtotal_, *_args, **_kwargs: subtotal_,
            ),
            patch(
                "odoo.addons.sale_lazada.models.lazada_shop.LazadaShop._find_matching_product",
                new=find_matching_product_mock,
            ),
        ):
            self.other_lazada_shop._sync_orders(auto_commit=False)
            self.assertEqual(self.other_lazada_shop.last_orders_sync_date, fields.Datetime.now())

            order = self.env["sale.order"].search([("lazada_order_ref", "=", common.ORDER_ID_MOCK)])
            order_lines = self.env["sale.order.line"].search([("order_id", "=", order.id)])
            product_line = order_lines.filtered(
                lambda line: line.product_id.default_code == "TEST-SKU-001"
            )

            self.assertEqual(len(order), 1)
            self.assertEqual(order.company_id.id, self.other_lazada_shop.company_id.id)
            self.assertEqual(product_line.tax_ids, self.parent_tax)
