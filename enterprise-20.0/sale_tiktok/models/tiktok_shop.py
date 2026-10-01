# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from datetime import datetime
from urllib.parse import urlencode

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY
from odoo.tools import split_every

from odoo.addons.sale_tiktok import const, utils

_logger = logging.getLogger(__name__)


class TikTokShop(models.Model):
    _name = "tiktok.shop"
    _description = "TikTok Shop"
    _check_company_auto = True

    # === BASIC FIELDS === #
    active = fields.Boolean(default=True, required=True)
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    name = fields.Char(string="Name", required=True, readonly=True)
    order_ids = fields.One2many(
        string="Orders", comodel_name="sale.order", inverse_name="tiktok_shop_id"
    )
    order_count = fields.Integer(string="Order Count", compute="_compute_order_count")
    country_id = fields.Many2one(string="Shop Region", comodel_name="res.country", readonly=True)
    tiktok_item_count = fields.Integer(string="Item Count", compute="_compute_tiktok_item_count")
    tiktok_item_ids = fields.One2many(
        string="Items", comodel_name="tiktok.item", inverse_name="shop_id"
    )
    tiktok_shop_ref = fields.Char(string="Shop ID", readonly=True)

    # === API & AUTHENTICATION FIELDS === #
    app_key = fields.Char(
        string="App key",
        help="Your TikTok Shop application key. You can find this in your TikTok Partner"
        " Center after creating an application. Enter this before authorizing the connection.",
        required=True,
    )
    app_secret = fields.Char(
        string="App secret",
        help="Your TikTok Shop application secret."
        " You can find this in your TikTok Partner Center after creating an application."
        " Enter this before authorizing the connection.",
        required=True,
    )
    access_token = fields.Char(
        help="The access token for the TikTok Shop API. This token expires in 7 days and needs to "
        "be refreshed with the refresh token. You don't have to manage this field manually.",
        readonly=True,
    )
    access_token_expire_datetime = fields.Datetime(
        string="Access Token Expiration",
        help="The date when the access token expires. Odoo will automatically refresh "
        "the token before it expires.",
        readonly=True,
    )
    refresh_token = fields.Char(
        help="The refresh token for the TikTok Shop API."
        " This token expires in 30 days and needs to be refreshed with the access token."
        " You don't have to manage this field manually.",
        readonly=True,
    )
    refresh_token_expire_datetime = fields.Datetime(
        string="Refresh Token Expiration",
        help="The date when the refresh token expires. Odoo will automatically refresh "
        "the token before it expires.",
        readonly=True,
    )
    service_extern_id = fields.Char(
        string="Service ID",
        help="The service ID for the TikTok Shop API."
        " This ID is used to identify the shop in the TikTok Shop API."
        " You can find this in your TikTok Partner Center after creating an application.",
        required=True,
    )
    tiktok_cipher = fields.Char(
        help="An unique identifier as an input parameter in shop related APIs.", readonly=True
    )

    # === CONFIGURATION FIELDS === #
    fbs_warehouse_id = fields.Many2one(
        string="FBS Warehouse",
        help="Warehouse synchronized with TikTok Shop under the Fulfilled by Seller (FBS) program."
        " Select the warehouse where you store products that you ship directly to customers. If"
        " not set, your company's default warehouse will be used.",
        comodel_name="stock.warehouse",
        domain="[('company_id', '=', company_id)]",
        required=True,
        default=lambda self: self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        ),
        check_company=True,
    )
    last_orders_sync_date = fields.Datetime(
        string="Last Order Synchronization",
        help="The last time orders were synchronized with TikTok Shop. Orders whose status has not "
        "changed since this date are not created nor updated in Odoo.",
        required=True,
        default=fields.Datetime.now,
    )
    last_product_catalog_sync_date = fields.Datetime(
        string="Last Catalog Synchronization",
        help="The last time the TikTok Shop catalog was synchronized with Odoo.",
        required=True,
        default=fields.Datetime.now,
    )
    synchronize_inventory = fields.Boolean(
        string="Enable Inventory Synchronization",
        help="Enable this to keep this shop's product quantities synchronized with TikTok Shop.",
        default=False,
    )
    team_id = fields.Many2one(
        string="Default Sales Team",
        help="The default Sales Team assigned to TikTok Shop orders for reporting",
        comodel_name="crm.team",
        check_company=True,
    )
    user_id = fields.Many2one(
        string="Default Salesperson",
        help="The default salesperson assigned to TikTok Shop orders",
        comodel_name="res.users",
        default=lambda self: self.env.user,
        check_company=True,
    )

    _unique_active_shop = models.UniqueIndex(
        "(tiktok_shop_ref) WHERE active = TRUE",
        "You cannot connect the same shop twice. Consider archiving the existing shop first.",
    )

    # === COMPUTE METHODS === #

    @api.depends("order_ids")
    def _compute_order_count(self):
        counts = dict(
            self.env["sale.order"]._read_group(
                [("tiktok_shop_id", "in", self.ids)],
                ["tiktok_shop_id"],
                ["__count"],
            )
        )
        for shop in self:
            shop.order_count = counts.get(shop, 0)

    @api.depends("tiktok_item_ids")
    def _compute_tiktok_item_count(self):
        counts = dict(
            self.env["tiktok.item"]._read_group(
                [("shop_id", "in", self.ids)],
                ["shop_id"],
                ["__count"],
            )
        )
        for shop in self:
            shop.tiktok_item_count = counts.get(shop, 0)

    # === ACTION METHODS === #

    def action_view_tiktok_items(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("TikTok Shop Items"),
            "res_model": "tiktok.item",
            "view_mode": "list",
            "domain": [("shop_id", "=", self.id)],
            "context": {"default_shop_id": self.id},
        }

    def action_view_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("tiktok_shop_id", "=", self.id)],
        }

    def action_sync_inventory(self):
        self._sync_inventory()

    def action_sync_orders(self):
        self._sync_orders()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    def action_sync_product_catalog(self):
        self._sync_product_catalog()

    def action_open_auth_link(self):
        self.ensure_one()
        state_payload = utils.generate_token(self)
        params = {"service_id": self.service_extern_id, "state": json.dumps(state_payload)}
        url = f"{const.AUTH_SERVICES_URL}?{urlencode(params)}"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    # === INVENTORY & PRODUCT CATALOG SYNCHRONIZATION === #

    def _sync_inventory(self, auto_commit=True):
        """Synchronize the inventory level of products sold on TikTok Shop.

        If called on an empty recordset, the products of all active shops with inventory
        synchronization are synchronized instead.

        :param bool auto_commit: Whether the database cursor should be committed as soon as an item
                                 is successfully synchronized.
        :return: None
        """
        shops = self or self.search([("synchronize_inventory", "=", True)])
        for shop in shops.filtered(lambda s: s.active and s.access_token and s.synchronize_inventory):
            shop.tiktok_item_ids._sync_inventory(auto_commit=auto_commit)

    def _sync_product_catalog(self):
        """
        Synchronize the TikTok Shop product catalog to Odoo.

        If called on an empty recordset, the products of all active shops are synchronized instead.

        :return: None
        """
        sync_start_dt = fields.Datetime.now()
        shops = self or self.search([])

        for shop in shops:
            initialize_shop = not shop.tiktok_item_ids
            next_page_token = None
            try:
                while True:
                    params = {
                        "page_size": const.PRODUCT_LIST_SIZE_LIMIT,
                        "shop_cipher": shop.tiktok_cipher,
                    }
                    body = {"status": "ACTIVATE"}

                    if next_page_token:
                        params["page_token"] = next_page_token
                    elif not initialize_shop:
                        body.update({
                            "update_time_ge": int(shop.last_product_catalog_sync_date.timestamp()),
                            "update_time_lt": int(sync_start_dt.timestamp()),
                        })
                    data = shop._fetch_tiktok_products(params=params, body=body)
                    next_page_token = data.get("next_page_token")

                    for item in data.get("items", []):
                        shop._find_or_create_item(
                            item["seller_sku"], item["item_extern_id"], item["sku_extern_id"]
                        )
                    if not next_page_token:
                        break

                shop.last_product_catalog_sync_date = sync_start_dt

            except utils.TikTokRateLimitError as error:
                _logger.info(
                    "Rate limit reached during TikTok Shop catalog sync (shop %(shop)s). "
                    "Operation: %(error_operation)s",
                    {"shop": shop.id, "error_operation": error.operation},
                )
                raise UserError(
                    self.env._("TikTok API rate limit reached. Please try again later.")
                ) from error

    def _fetch_tiktok_products(self, params=None, body=None):
        """
        Fetch the products from TikTok Shop.

        :param dict params: Query parameter for the API.
        :param dict body: Body for the API.
        :return: The products.
        :rtype: dict
        """
        if body is None:
            body = {}
        if params is None:
            params = {}
        response = utils.make_tiktok_api_request(self, "get_products", params=params, body=body)
        return {
            "items": [
                {
                    "item_extern_id": product["id"],
                    "sku_extern_id": sku["id"],
                    "seller_sku": sku["seller_sku"],
                }
                for product in response.get("products", [])
                for sku in product.get("skus", [])
            ],
            "next_page_token": response.get("next_page_token", ""),
        }

    # === ORDER SYNCHRONIZATION METHODS === #

    def _sync_orders(self, auto_commit=True):
        """Synchronize the shops' sales orders that were recently updated on TikTok Shop.

        If called on an empty recordset, the orders of all active shops are synchronized instead.

        Note: This method is called by the `ir_cron_sync_tiktok_orders` cron.

        :param bool auto_commit: Whether the database cursor should be committed as soon as an order
                                 is successfully synchronized.
        :return: None
        """
        shops = self or self.search([])
        for shop in shops.filtered(lambda s: s.active and s.access_token):
            start_sync_dt = fields.Datetime.now()
            next_page_token = None
            try:
                while True:
                    data = shop._fetch_order_list(
                        time_from=shop.last_orders_sync_date,
                        time_to=start_sync_dt,
                        page_token=next_page_token,
                    )
                    orders = data.get("orders", [])
                    next_page_token = data.get("next_page_token")

                    if auto_commit and orders:
                        self.env["ir.cron"]._commit_progress(0, remaining=len(orders))
                    for order_data in orders:
                        shop._process_and_commit_order(order_data, auto_commit=auto_commit)
                    if not next_page_token:
                        break

            except utils.TikTokRateLimitError as error:
                _logger.info(
                    "Rate limit reached while synchronizing sales orders for TikTok Shop with"
                    " id %(shop)s. Operation: %(error_operation)s",
                    {"shop": shop.id, "error_operation": error.operation},
                )
                continue

    def _process_and_commit_order(self, order_data, auto_commit=True):
        """Process sales order data from TikTok Shop and persist it safely.

        :param bool auto_commit: Whether the database cursor should be committed as soon as an order
                                 is successfully synchronized.
        :param dict order_data: The order data to process.
        :return: None
        """
        try:
            if auto_commit:
                with self.env.cr.savepoint():
                    self._process_order_data(order_data)
            else:  # Avoid the savepoint in testing
                self._process_order_data(order_data)
        except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY + (utils.TikTokRateLimitError,):
            _logger.info(
                "A concurrency error occurred while processing the order data "
                "with order ID %(order_ref)s for TikTok shop id %(id)s."
                " Discarding the error to trigger the retry mechanism.",
                {"order_ref": order_data["id"], "id": self.id},
            )
            raise
        except utils.TikTokApiError:
            tiktok_order_ref = order_data["id"]
            _logger.warning(
                "A business error occurred while processing the order data"
                " with order ID %(order_ref)s for TikTok shop %(shop)s."
                " Skipping the order data and moving to the next order.",
                {"order_ref": tiktok_order_ref, "shop": self.id},
                exc_info=True,
            )
            # Dismiss business errors to allow the synchronization to skip the
            # problematic orders.
            self.env["ir.cron"]._rollback_progress()
            self._handle_sync_failure(flow="order_sync", tiktok_order_ref=tiktok_order_ref)
            return

        update_time = order_data.get("update_time")
        if update_time:
            update_dt = datetime.fromtimestamp(update_time)
            if not self.last_orders_sync_date or update_dt > self.last_orders_sync_date:
                self.last_orders_sync_date = update_dt

        if auto_commit:
            # Commit to mitigate a potential cron kill.
            self.env["ir.cron"]._commit_progress(1)

    def _fetch_order_list(self, time_from, time_to, page_token=None):
        """Fetch the order list from TikTok Shop.

        :param datetime time_from: Lower limit for pulling orders.
        :param datetime time_to: Upper limit for pulling orders.
        :return: A list composed of TikTok Shop's orders' external IDs.
        :rtype: list
        """
        params = {"shop_cipher": self.tiktok_cipher, "page_size": const.ORDER_LIST_SIZE_LIMIT}
        if page_token:
            params["page_token"] = page_token
        response = utils.make_tiktok_api_request(
            self,
            "get_order_list",
            params=params,
            body={
                "update_time_ge": int(time_from.timestamp()),
                "update_time_lt": int(time_to.timestamp()),
            },
        )
        return {
            "orders": response.get("orders", []),
            "next_page_token": response.get("next_page_token"),
        }

    def _fetch_orders_detail(self, order_sn_list):
        """Fetch the order details from TikTok Shop.

        :param list order_sn_list: A list composed of TikTok Shop's orders' external IDs.
        :return: The orders detail.
        :rtype: list
        """
        orders_detail = []
        for batch in split_every(const.ORDER_DETAIL_SIZE_LIMIT, order_sn_list):
            response = utils.make_tiktok_api_request(
                self,
                "get_order_detail",
                params={"shop_cipher": self.tiktok_cipher, "ids": ",".join(batch)},
            )
            orders_detail += response.get("orders", [])

        return orders_detail

    def _process_order_data(self, order_data):
        """Process the provided order details and return the matching sales order, if any.

        - If the order does not exist and its status belongs to
          `const.ORDER_STATUSES_TO_SYNC`, create it from the TikTok Shop data.
        - If the order exists, update it depending on the status.

        Note: self.ensure_one()

        :param dict order_data: The order data to process.
        :return: The matching TikTok Shop order, if any, as a `sale.order` record.
        :rtype: recordset of `sale.order`
        """
        self.ensure_one()
        fulfillment_type = const.FULFILLMENT_TYPE_MAPPING.get(order_data["fulfillment_type"])
        tiktok_order_ref = order_data["id"]
        tiktok_status = order_data["status"]
        order = self.env["sale.order"].search(
            [("tiktok_order_ref", "=", tiktok_order_ref), ("tiktok_shop_id", "=", self.id)], limit=1
        )
        if order:
            # Order exists, update the status
            self._update_order_from_data(order, order_data)
        elif tiktok_status in const.ORDER_STATUSES_TO_SYNC.get(fulfillment_type, {}):
            order = self._create_order_from_data(order_data)
            order.with_context(mail_notrack=True).action_lock()
            _logger.info(
                "Created a new sales order with tiktok_order_ref %(ref)s for TikTok shop"
                " with id %(id)s.",
                {"ref": tiktok_order_ref, "id": self.id},
            )
        else:
            _logger.info(
                "Ignored TikTok Shop order with reference %(ref)s and status %(status)s"
                " shop with id %(id)s.",
                {"ref": tiktok_order_ref, "status": tiktok_status, "id": self.id},
            )
        return order

    def _update_order_from_data(self, order, order_data):
        """Update the order from data.

        - "CANCELLED": cancel the Odoo order if needed.

        :param record order: The order to update.
        :param dict order_data: The order data to update.
        :return: None
        """
        self.ensure_one()
        tiktok_order_ref = order_data["id"]
        tiktok_status = order_data["status"]
        # Update the delivery status to keep it in sync with TikTok Shop
        order.tiktok_delivery_status = const.DELIVERY_STATUS_MAPPING.get(tiktok_status, "manual")

        if tiktok_status == "CANCELLED" and order.state != "cancel":
            order._action_cancel()
            _logger.info(
                "Canceled sales order with tiktok_order_ref %(ref)s for TikTok shop with id"
                " %(id)s.",
                {"ref": tiktok_order_ref, "id": self.id},
            )
        else:
            _logger.info(
                "Ignored already synchronized sales order with tiktok_order_ref %(ref)s for"
                " TikTok shop with id %(id)s.",
                {"ref": tiktok_order_ref, "id": self.id},
            )

    def _create_order_from_data(self, order_data):
        """Create the order from data.

        :param dict order_data: A dict of order data.
        :return: The created order.
        :rtype: sale.order
        """
        currency = (
            self
            .env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", order_data["payment"]["currency"])], limit=1)
        )
        tiktok_order_ref = order_data["id"]
        contact_partner, delivery_partner = self._find_or_create_partners_from_data(order_data)
        fiscal_position = (
            self
            .env["account.fiscal.position"]
            .with_company(self.company_id)
            ._get_fiscal_position(contact_partner, delivery_partner)
        )
        order_lines_values = self._prepare_order_lines_values(order_data, currency, fiscal_position)
        order_lines = [
            Command.create(order_line_values) for order_line_values in order_lines_values
        ]
        origin = _("TikTok Shop Order %(tiktok_order_ref)s", tiktok_order_ref=tiktok_order_ref)
        delivery_status = const.DELIVERY_STATUS_MAPPING.get(order_data["status"], "draft")
        order_vals = {
            "origin": origin,
            "state": "sale",
            # The order is first created unlocked and later locked to trigger the creation of a
            # stock picking if fulfilled by merchant.
            "date_order": datetime.fromtimestamp(order_data.get("paid_time", order_data["create_time"])),
            "partner_id": contact_partner.id,
            "pricelist_id": self._find_or_create_pricelist(currency).id,
            "order_line": order_lines,
            "invoice_status": "no",
            "partner_shipping_id": delivery_partner.id,
            "require_signature": False,
            "fiscal_position_id": fiscal_position.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "team_id": self.team_id.id,
            "tiktok_order_ref": tiktok_order_ref,
            "tiktok_shop_id": self.id,
            "tiktok_delivery_status": delivery_status,
            "tiktok_packing_ref": order_data.get("packages", [{}])[0].get("id"),
            "warehouse_id": self.fbs_warehouse_id.id,
        }
        shipping_code = order_data.get("shipping_provider")
        shipping_product = self._find_matching_product(
            shipping_code, "default_shipping_product", "TikTok Shop Shipping", "service"
        )
        if shipping_code:  # The buyer chose a specific delivery method
            delivery_method = self._find_or_create_delivery_carrier(shipping_code, shipping_product)
            order_vals["carrier_id"] = delivery_method.id

        order = (
            self
            .env["sale.order"]
            .with_context(mail_create_nosubscribe=True)
            .with_company(self.company_id)
            .create(order_vals)
        )
        tiktok_total = float(order_data["payment"]["total_amount"])
        self._adjust_order_total(order, currency, tiktok_total)
        return order

    def _adjust_order_total(self, order, currency, tiktok_total):
        """Ensure Odoo order total matches TikTok total by adding a balancing line."""
        residue = currency.round(tiktok_total - order.amount_total)
        if not currency.is_zero(residue):
            adjustment_product = self._find_matching_product(
                "", "default_adjustment_product", "TikTok Amount Adjustment", "service"
            )
            self.env["sale.order.line"].create({
                "order_id": order.id,
                "name": _("TikTok Amount Adjustment"),
                "product_id": adjustment_product.id,
                "price_unit": residue,
                "product_uom_qty": 1,
                "tax_ids": [],
                "discount": 0,
            })

    def _prepare_order_lines_values(self, order_data, currency, fiscal_pos):
        """Prepare the values for the order lines to create based on TikTok Shop order data.

        Note: self.ensure_one()

        :param dict order_data: The order data related to the item data.
        :param record currency: The currency of the sales order, as a `res.currency` record.
        :param record fiscal_pos: The fiscal position of the sales order, as an
                                    `account.fiscal.position` record.
        :return: The order lines values.
        :rtype: dict
        """
        self.ensure_one()

        aggregated = {}
        for item_data in order_data["line_items"]:
            sku = item_data["seller_sku"]
            tiktok_item = self._find_or_create_item(
                sku, item_data["product_id"], item_data["sku_id"]
            )
            product = tiktok_item.product_id
            product_id = product.id

            if product_id not in aggregated:
                aggregated[product_id] = {
                    "product": product,
                    "description": self._build_item_description(
                        sku,
                        item_data,
                        float(item_data.get("original_price", 0)),
                        float(item_data["sale_price"]),
                    ),
                    "quantity": 0,
                    "discounted_subtotal": 0.0,
                }
            aggregated[product_id]["quantity"] += 1
            aggregated[product_id]["discounted_subtotal"] += float(item_data["sale_price"])

        order_lines_values = []
        for data in aggregated.values():
            product = data["product"]
            quantity = data["quantity"]
            discounted_subtotal = data["discounted_subtotal"]
            product_taxes = product.taxes_id._filter_taxes_by_company(self.company_id)
            taxes = fiscal_pos.map_tax(product_taxes)

            line_specs = self._compute_reconciled_line_specs(
                quantity, discounted_subtotal, taxes, currency
            )
            for sub_qty, price_unit in line_specs:
                order_lines_values.append({
                    "name": data["description"],
                    "product_id": product.id,
                    "price_unit": price_unit,
                    "tax_ids": taxes.ids,
                    "product_uom_qty": sub_qty,
                    "discount": 0,
                })

        # Shipping line
        payment = order_data.get("payment", {})
        shipping_fee = float(payment.get("shipping_fee", 0) or 0)

        if shipping_fee:
            shipping_code = order_data.get("shipping_provider") or "TikTok Shipping"
            shipping_product = self._find_matching_product(
                shipping_code, "default_shipping_product", "TikTok Shipping", "service"
            )
            shipping_taxes_raw = shipping_product.taxes_id._filter_taxes_by_company(self.company_id)
            shipping_taxes = fiscal_pos.map_tax(shipping_taxes_raw)

            shipping_specs = self._compute_reconciled_line_specs(
                1, shipping_fee, shipping_taxes, currency
            )
            for sub_qty, price_unit in shipping_specs:
                order_lines_values.append({
                    "name": _("Shipping: %(carrier)s", carrier=shipping_code),
                    "product_id": shipping_product.id,
                    "price_unit": price_unit,
                    "tax_ids": shipping_taxes.ids,
                    "product_uom_qty": sub_qty,
                    "discount": 0,
                })

        return order_lines_values

    def _find_or_create_delivery_carrier(self, shipping_code, shipping_product):
        """Find or create a delivery carrier based on the shipping code.

        :param str shipping_code: The shipping code.
        :param record shipping_product: The shipping product matching the shipping code, as a
                                        `product.product` record.
        :return: The delivery carrier.
        :rtype: delivery.carrier
        """
        delivery_method = self.env["delivery.carrier"].search(
            [("name", "=", shipping_code)], limit=1
        )
        if shipping_code and not delivery_method:
            delivery_method = self.env["delivery.carrier"].create({
                "name": shipping_code,
                "product_id": shipping_product.id,
            })
        return delivery_method

    def _find_or_create_pricelist(self, currency):
        """Find or create pricelist for currency.

        :param currency: Currency record (res.currency)
        :return: Pricelist record
        :rtype: product.pricelist
        """
        pricelist = self.env["product.pricelist"].search(
            [
                ("currency_id", "=", currency.id),
                *self.env["product.pricelist"]._check_company_domain(self.company_id),
            ],
            limit=1,
        )

        if not pricelist:
            pricelist = self.env["product.pricelist"].create({
                "name": f"TikTok {currency.name}",
                "currency_id": currency.id,
                "company_id": self.company_id.id,
                "active": False,
            })

        return pricelist

    def _compute_subtotal(self, total, taxes, currency):
        """Compute the subtotal from the taxes.

        TikTok Shop does not provide the tax amount of the order, so we recompute the subtotal
        from the product taxes (or those mapped by the fiscal position) to match the order total.

        If the taxes used are not identical to those used by TikTok Shop, the recomputed subtotal
        may differ from the original subtotal.

        :param float total: The original total.
        :param account.tax taxes: The final taxes to use for the computation of the new subtotal.
        :param res.currency currency: The currency used by the rounding methods.
        :return: The new subtotal.
        :rtype: float
        """
        taxes_res = taxes.with_context(force_price_include=True).compute_all(
            total, currency=currency
        )
        subtotal = taxes_res["total_excluded"]
        for tax_res in taxes_res["taxes"]:
            tax = self.env["account.tax"].browse(tax_res["id"])
            if tax.price_include:
                subtotal += tax_res["amount"]
        return subtotal

    def _build_item_description(self, sku, item_data, original_price, discounted_price):
        lines = [
            _("[%(sku)s] %(product_name)s", sku=sku, product_name=item_data.get("product_name"))
        ]
        if original_price > discounted_price:
            lines.append(_("Original price: %(price)s", price=original_price))

        return "\n".join(lines)

    def _find_or_create_item(self, sku, item_extern_id, sku_extern_id):
        """Find or create the TikTok Shop item based on the SKU and shop.

        Note: self.ensure_one()

        :param str sku: The SKU of the product.
        :param str item_extern_id: The TikTok Shop Item External ID.
        :param str sku_extern_id: The TikTok Shop SKU External ID.
        :return: The found or created tiktok item
        :rtype: tiktok.item
        """
        self.ensure_one()
        tiktok_item = self.tiktok_item_ids.filtered(
            lambda i: i.tiktok_item_extern_id == item_extern_id
        )
        if sku_extern_id:
            tiktok_item = tiktok_item.filtered(lambda i: i.tiktok_sku_extern_id == sku_extern_id)
        if not tiktok_item:
            tiktok_item = (
                self
                .env["tiktok.item"]
                .with_context(tracking_disable=True)
                .create({
                    "product_id": self._find_matching_product(
                        sku, "default_sale_product", "TikTok Shop Sales", "consu"
                    ).id,
                    "shop_id": self.id,
                    "tiktok_seller_sku": sku,
                    "tiktok_item_extern_id": item_extern_id,
                    "tiktok_sku_extern_id": sku_extern_id,
                })
            )
        # If the item has been linked with the default product, search if another product has now
        # been assigned the current SKU as internal reference and update the item if so.
        # This trades off a bit of performance in exchange for a more expected behavior for the
        # matching of products if one was assigned the right SKU after that the item was created.
        elif "sale_tiktok.default_sale_product" in tiktok_item.product_id._get_external_ids().get(
            tiktok_item.product_id.id, []
        ):
            product = self._find_matching_product(sku, "", "", "", fallback=False)
            if product:
                tiktok_item.product_id = product.id

        return tiktok_item

    def _find_matching_product(
        self, internal_reference, default_xmlid, default_name, default_type, fallback=True
    ):
        """Find the matching product for a given internal reference.

        If no product is found for the given internal reference, we fall back on the default
        product. If the default product was deleted, we restore it.

        :param str internal_reference: The internal reference of the product to be searched.
        :param str default_xmlid: The xmlid of the default product to use as fallback.
        :param str default_name: The name of the default product to use as fallback.
        :param str default_type: The product type of the default product to use as fallback.
        :param bool fallback: Whether we should fall back to the default product when no product
            matching the provided internal reference is found.
        :return: The matching product.
        :rtype: product.product
        """
        self.ensure_one()

        product = self.env["product.product"]
        if internal_reference:
            product = self.env["product.product"].search(
                [
                    *self.env["product.product"]._check_company_domain(self.company_id),
                    ("default_code", "=", internal_reference),
                ],
                limit=1,
            )
        if not product and fallback:  # Fallback to the default product
            product = self.env.ref(
                f"sale_tiktok.{default_xmlid}", raise_if_not_found=False
            ) or self.env["product.product"]._restore_tiktok_data_product(
                default_name, default_type, default_xmlid
            )
        return product

    def _find_or_create_partners_from_data(self, order_data):
        """Find or create the partners from data.

        :param dict order_data: A dict of order data.
        :return: The contact partner and the delivery partner.
        :rtype: tuple(res.partner, res.partner)
        """
        self.ensure_one()

        tiktok_buyer_extern_id = order_data["user_id"]
        recipient_address = order_data.get("recipient_address", {})
        buyer_name = recipient_address.get("name")
        shipping_address_name = buyer_name

        city = state_name = None
        for entry in recipient_address.get("district_info", []):
            if entry.get("address_level") == "L2":
                city = entry.get("address_name")
            elif entry.get("address_level") == "L1":
                state_name = entry.get("address_name")
        street = recipient_address.get("address_line1", "")
        street2 = recipient_address.get("address_line2", "")
        zip_code = recipient_address.get("postal_code", "")
        country_code = recipient_address.get("region_code")
        phone = recipient_address.get("phone_number", "")

        country = self.env["res.country"].search([("code", "=", country_code)], limit=1)
        state = self.env["res.country.state"]
        if country and state_name:
            state = self.env["res.country.state"].search(
                [("name", "=ilike", state_name), ("country_id", "=", country.id)], limit=1
            )

        partner_vals = {
            "street": street,
            "street2": street2,
            "zip": zip_code,
            "city": city,
            "country_id": country.id if country else False,
            "state_id": state.id if state else False,
            "phone": phone,
            "customer_rank": 1,
            "company_id": self.company_id.id,
            "tiktok_buyer_extern_id": tiktok_buyer_extern_id,
        }

        # The contact partner is searched based on all the personal information and only if the
        # user id of the buyer is provided. A match thus only occurs if the customer had already
        # made a previous order and if the personal information provided by the API did not change
        # in the meantime. If there is no match, a new contact partner is created. This behavior is
        # preferred over updating the personal information with new values because it allows using
        # the correct contact details when invoicing the customer for an earlier order, should there
        # be a change in the personal information.
        contact = (
            self.env["res.partner"].search(
                [
                    *self.env["product.pricelist"]._check_company_domain(self.company_id),
                    ("type", "=", "contact"),
                    ("tiktok_buyer_extern_id", "=", tiktok_buyer_extern_id),
                ],
                limit=1,
            )
            if tiktok_buyer_extern_id
            else None
        )  # Don't match random partners.
        if not contact:
            contact_name = buyer_name
            contact = (
                self
                .env["res.partner"]
                .with_context(tracking_disable=True)
                .create({"name": contact_name, **partner_vals})
            )

        # The contact partner acts as delivery partner if the address is strictly equal to that of
        # the contact partner. If not, a delivery partner is created.
        delivery = (
            contact
            if (
                contact.name == shipping_address_name
                and contact.street == street
                and contact.street2 == street2
                and contact.zip == zip_code
                and contact.city == city
                and contact.country_id.id == country.id
                and contact.state_id.id == state.id
            )
            else None
        )
        if not delivery:
            delivery = self.env["res.partner"].search(
                [
                    *self.env["res.partner"]._check_company_domain(self.company_id),
                    ("type", "=", "delivery"),
                    ("parent_id", "=", contact.id),
                    ("name", "=", shipping_address_name),
                    ("street", "=", street),
                    ("street2", "=", street2),
                    ("zip", "=", zip_code),
                    ("city", "=", city),
                    ("country_id", "=", country.id),
                    ("state_id", "=", state.id),
                ],
                limit=1,
            )
        if not delivery:
            delivery = (
                self
                .env["res.partner"]
                .with_context(tracking_disable=True)
                .create({
                    "name": shipping_address_name,
                    "type": "delivery",
                    "parent_id": contact.id,
                    **partner_vals,
                })
            )

        return contact, delivery

    def _compute_reconciled_line_specs(self, quantity, discounted_subtotal, taxes, currency):
        """Compute per-line (sub_quantity, price_unit) tuples.

        - Branch 1: any tax has price_include -> use discounted unit price directly
          (Odoo's tax back-out guarantees exact reconciliation at order level).
        - Branch 2a: tax-exclusive path -> call _compute_subtotal to reverse the
          tax-inclusive total to a tax-exclusive subtotal; round to currency
          precision to get nominal_unit_price. Any rounding residue is absorbed at
          order level by _prepare_order_lines_values.

        :param int quantity: Quantity for the line.
        :param float discounted_subtotal: Platform subtotal (post-discount).
        :param account.tax taxes: Taxes applied to the line.
        :param res.currency currency: Currency for rounding.
        :return: List of (sub_quantity, price_unit)
        :rtype: list[tuple[int, float]]
        """
        # Branch 1: tax-inclusive path — use discounted unit price directly.
        if any(tax.price_include for tax in taxes):
            return [(quantity, discounted_subtotal / quantity)]

        # Branch 2a: tax-exclusive path.
        tax_excluded_subtotal = self._compute_subtotal(discounted_subtotal, taxes, currency)
        unit_price = currency.round(tax_excluded_subtotal / quantity)
        return [(quantity, unit_price)]

    def _handle_sync_failure(self, flow="", tiktok_order_ref=False, error_messages=False):
        """Send a mail to the responsible persons to report a synchronization failure.

        :param str flow: Flow name (`order_sync`, `inventory_sync`, `warehouse_sync`,
            `picking_sync`).
        :param str tiktok_order_ref: TikTok Shop order references that failed to sync.
        :param list[dict] error_messages: List of {"order_ref": "error"} entries, required for
            the `picking_sync` flow.
        :return: None
        """
        if flow == "order_sync":
            _logger.error(
                "Failed to synchronize TikTok Shop order %(ref)s for tiktok.shop %(shop_id)s "
                "(%(shop_name)s). Please create the order manually.",
                {"ref": tiktok_order_ref, "shop_id": self.id, "shop_name": self.name},
            )
            mail_template_id = "sale_tiktok.order_sync_failure"
        elif flow == "inventory_sync":
            _logger.error(
                "Failed to synchronize the inventory for items in tiktok.shop with id "
                "%(shop_id)s (Shop Name: %(shop_name)s).",
                {"shop_id": self.id, "shop_name": self.name},
            )
            mail_template_id = "sale_tiktok.inventory_sync_failure"
        if not mail_template_id:
            _logger.warning("Unknown sync failure flow")
            return
        mail_template = self.env.ref(mail_template_id, raise_if_not_found=False)
        if not mail_template:
            _logger.warning(
                "The mail template with xmlid %(mail_template)s has been deleted.",
                {"mail_template": mail_template_id},
            )
        else:
            responsible_emails = {
                u.email
                for u in (self.user_id, self.env.ref("base.user_admin", raise_if_not_found=False))
                if u and u.email
            }
            mail_template.with_context(
                email_to=",".join(responsible_emails),
                tiktok_order_ref=tiktok_order_ref,
                error_messages=error_messages,
                tiktok_shop=self.name,
            ).send_mail(self.env.user.id)
            _logger.info(
                "Sent synchronization failure notification email to %(emails)s",
                {"emails": ", ".join(responsible_emails)},
            )
