# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo

from werkzeug import urls

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY
from odoo.tools import split_every

from odoo.addons.sale_lazada import const, utils

_logger = logging.getLogger(__name__)


class LazadaShop(models.Model):
    _name = "lazada.shop"
    _description = "Lazada Shop"
    _check_company_auto = True

    # === BASIC FIELDS === #
    name = fields.Char(string="Name", required=True, default="Unnamed Lazada Shop")
    active = fields.Boolean(default=True, required=True)
    country_id = fields.Many2one(string="Shop Region", comodel_name="res.country", readonly=True)
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )
    lazada_item_ids = fields.One2many(
        string="Lazada Items", comodel_name="lazada.item", inverse_name="shop_id"
    )
    lazada_item_count = fields.Integer(string="Item Count", compute="_compute_lazada_item_count")
    order_ids = fields.One2many(
        string="Orders", comodel_name="sale.order", inverse_name="lazada_shop_id"
    )
    order_count = fields.Integer(string="Order Count", compute="_compute_order_count")
    shop_extern_id = fields.Char(
        string="Lazada Seller ID",
        help="Your unique seller ID assigned by Lazada. This is automatically set during "
        "authorization and ensures the same Lazada shop cannot be linked twice to the "
        "same company.",
        readonly=True,
        required=True,
        default="",
    )

    # === API & AUTHENTICATION FIELDS === #
    api_endpoint = fields.Char(string="API Endpoint", compute="_compute_api_endpoint")
    app_key = fields.Char(
        help="Your Lazada application key (App Key). You can find this in your Lazada "
        "Service Provider Center after creating an application. Enter this before "
        "authorizing the connection.",
        required=True,
    )
    app_secret = fields.Char(
        help="Your Lazada application secret (App Secret). This is provided alongside your "
        "App Key in the Lazada Service Provider Center. Keep this confidential "
        "and enter it before authorizing the connection.",
        required=True,
    )
    access_token = fields.Char(
        help="Temporary access token provided by Lazada for API authentication. This token "
        "expires after 4 hours and is automatically refreshed using the refresh token. "
        "You don't need to manage this manually.",
        readonly=True,
    )
    access_token_expiration_date = fields.Datetime(
        help="The date and time when the current access token will expire. The system "
        "automatically refreshes the token before expiration, so no action is required.",
        readonly=True,
    )
    refresh_token = fields.Char(
        help="Long-term refresh token used to automatically obtain new access tokens. This "
        "token expires after 30 days. If it expires, you'll need to re-authorize the "
        "connection by clicking the authorization button in the Lazada shop view.",
        readonly=True,
    )
    refresh_token_expiration_date = fields.Datetime(
        help="The date and time when the refresh token will expire. If this date passes, "
        "you'll need to re-authorize the connection to continue synchronizing with Lazada.",
        readonly=True,
    )

    # === CONFIGURATION FIELDS === #
    user_id = fields.Many2one(
        string="Default Salesperson",
        help="The default Salesperson assigned to orders imported from this Lazada shop",
        comodel_name="res.users",
        default=lambda self: self.env.user,
        check_company=True,
    )
    team_id = fields.Many2one(
        string="Default Sales Team",
        help="The default Sales Team assigned to orders imported from this Lazada shop",
        comodel_name="crm.team",
        check_company=True,
    )
    last_product_catalog_sync_date = fields.Datetime(
        string="Last Catalog Synchronization",
        help="Shows when the product catalog was last synchronized from Lazada to Odoo. "
        "Only products updated in Lazada after this date will be fetched in the next "
        "synchronization. This is automatically updated after each sync. "
        "To re-initialize the full catalog, clear this value.",
    )
    last_orders_sync_date = fields.Datetime(
        string="Last Order Synchronization Date",
        help="Shows when orders were last synchronized from Lazada. Only orders that have "
        "changed since this date will be imported or updated in Odoo.",
        required=True,
        default=fields.Datetime.now,
    )
    synchronize_inventory = fields.Boolean(
        string="Allow inventory synchronization",
        default=False,
        help="Enable this to automatically sync your Odoo inventory quantities to Lazada. "
        "When enabled, product stock levels in Odoo will be pushed to Lazada for "
        "FBM (Fulfilled by Merchant) items. This ensures your Lazada listings show "
        "accurate stock availability.",
    )
    manage_fbl_inventory = fields.Boolean(
        string="Track FBL Inventory",
        help="Enable this to track inventory for FBL (Fulfilled by Lazada) items in Odoo. "
        "When enabled, stock in the FBL location will be deducted from your available "
        "FBM stock. The FBL location is automatically created when you set up the shop.",
        default=False,
    )
    fbl_location_id = fields.Many2one(
        string="FBL Stock Location",
        help="The stock location representing inventory managed by Lazada under the FBL "
        "(Fulfilled by Lazada) program. This location is automatically created when "
        "you set up the shop. Stock moves to this location represent items sent to "
        "Lazada warehouses for fulfillment.",
        comodel_name="stock.location",
        domain="[('usage', '=', 'internal')]",
        check_company=True,
    )
    fbm_warehouse_id = fields.Many2one(
        string="FBM Warehouse",
        help="The warehouse containing inventory that will be synchronized to Lazada for "
        "FBM (Fulfilled by Merchant) orders. Select the warehouse where you store "
        "products that you ship directly to customers. If not set, your company's "
        "default warehouse will be used.",
        comodel_name="stock.warehouse",
        domain="[('company_id', '=', company_id)]",
        required=True,
        default=lambda self: self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        ),
    )
    lazada_oauth_state = fields.Char(
        string="Lazada OAuth State", help="The state of the OAuth flow for this shop.", copy=False
    )

    _unique_shop_extern_id_company = models.Constraint(
        "UNIQUE(shop_extern_id, company_id)",
        "A shop with this external identifier already exists in this company. "
        "The same Lazada shop cannot be linked twice to the same company.",
    )

    # === COMPUTE METHODS === #

    @api.depends("lazada_item_ids")
    def _compute_lazada_item_count(self):
        """Compute the count of Lazada items for this shop."""
        for shop in self:
            shop.lazada_item_count = len(shop.lazada_item_ids)

    @api.depends("order_ids")
    def _compute_order_count(self):
        """Compute the count of orders for this shop."""
        for shop in self:
            shop.order_count = len(shop.order_ids)

    @api.depends("country_id")
    def _compute_api_endpoint(self):
        """Compute the API endpoint based on the shop's country."""
        for shop in self:
            if not shop.country_id:
                shop.api_endpoint = ""
                continue
            api_endpoint = const.API_ENDPOINTS.get(shop.country_id.code)
            if api_endpoint:
                shop.api_endpoint = api_endpoint
            else:
                raise UserError(
                    self.env._(
                        "The API Endpoint for the country %(country)s is not supported.",
                        country=shop.country_id.name,
                    )
                )

    # === CRUD METHODS === #

    @api.model_create_multi
    def create(self, vals_list):
        """Create Lazada shops and configure FBL locations.

        Each shop is automatically assigned a dedicated FBL (Fulfilled by Lazada) location.
        """
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            # Find or create the lazada warehouse to be associated with the shop
            parent_warehouse = self.env["stock.warehouse"].search_read(
                self.env["stock.warehouse"]._check_company_domain(company_id),
                ["view_location_id"],
                limit=1,
            )
            location_name = self.env._("Lazada FBL Stock - %(shop)s", shop=vals.get("name"))
            if parent_warehouse:
                location = self.env["stock.location"].search(
                    [
                        *self.env["stock.location"]._check_company_domain(company_id),
                        ("name", "=", location_name),
                        ("location_id", "=", parent_warehouse[0]["view_location_id"][0]),
                    ],
                    limit=1,
                )
                # Create FBL location if it doesn't exist
                if not location:
                    location = self.env["stock.location"].create({
                        "name": location_name,
                        "usage": "internal",
                        "location_id": parent_warehouse[0]["view_location_id"][0],
                        "company_id": company_id,
                    })
                vals.update({"fbl_location_id": location.id})

        return super().create(vals_list)

    # === ACTION METHODS === #

    def action_view_orders(self):
        """Open the list of orders for this shop."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_orders")
        action["domain"] = [("lazada_shop_id", "=", self.id)]
        action["context"] = dict(self.env.context, create=False)
        return action

    def action_sync_orders(self):
        """Manually sync orders for this shop."""
        self.ensure_one()
        self._sync_orders()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_view_lazada_items(self):
        """Open the list of Lazada items for this shop."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "sale_lazada.action_lazada_item_list"
        )
        action["domain"] = [("shop_id", "=", self.id)]
        action["context"] = dict(self.env.context, default_shop_id=self.id, create=False)
        return action

    def action_sync_inventory(self):
        """Manually sync inventory for this shop."""
        self.ensure_one()
        self._sync_inventory()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_sync_product_catalog(self):
        """Manually sync product catalog for this shop."""
        self.ensure_one()
        self._sync_product_catalog()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_archive(self):
        """Disconnect and archive the Lazada shop."""
        self._reset_refresh_token()
        return super().action_archive()

    def action_open_auth_link(self):
        """Redirect to Lazada authorization page.

        :return: Action dictionary for URL redirect
        :rtype: dict
        """
        self.ensure_one()

        if not (self.app_key and self.app_secret):
            raise UserError(self.env._("App Key and App Secret are required for authorization."))

        auth_url = const.AUTH_URL
        timestamp = int(fields.Datetime.now().timestamp())
        sign = utils.get_public_sign(self, timestamp)
        redirect_url = (
            f"{self.get_base_url()}/lazada/return_from_authorization/{self.id}/{timestamp}/{sign}"
        )
        state = secrets.token_urlsafe(32)
        self.lazada_oauth_state = state
        params = {
            "response_type": "code",
            "force_auth": "true",
            "redirect_uri": redirect_url,
            "client_id": self.app_key,
            "state": state,
        }

        # The url needs to be accessed to authorize the Lazada app. It will return to a callback URL
        # with the authorization code needed to get the access and refresh tokens.
        url = f"{auth_url}?{urls.url_encode(params)}"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    # === TOKEN MANAGEMENT === #

    def _reset_refresh_token(self):
        """Reset refresh and access tokens for the shop."""
        self.write({
            "refresh_token": False,
            "refresh_token_expiration_date": False,
            "access_token": False,
            "access_token_expiration_date": False,
        })

    # === INVENTORY & PRODUCT CATALOG SYNCHRONIZATION === #

    def _sync_inventory(self, auto_commit=True):
        """Synchronize inventory from Odoo to Lazada.

        Syncs all active shops if called on empty recordset.

        :param bool auto_commit: Whether to commit after each successful sync
        """
        shops = self or self.search([("active", "=", True)])
        for shop in shops.filtered(lambda s: s.synchronize_inventory):
            shop.lazada_item_ids._sync_inventory(auto_commit=auto_commit)

    def _sync_product_catalog(self):
        """Synchronize Lazada product catalog to Odoo.

        Syncs all active shops if called on empty recordset. If initialize is True,
        fetches all products; otherwise only products updated since last sync.
        """
        sync_start_dt = fields.Datetime.now()
        shops = self or self.search([("active", "=", True)])
        for shop in shops:
            # If the sync date is empty, initialize the catalog (fetch all items)
            initialize_shop = not shop.last_product_catalog_sync_date
            time_from = shop.last_product_catalog_sync_date
            time_to = sync_start_dt
            offset = 0
            total_products = False
            while (
                total_products is False or offset * const.PRODUCT_LIST_SIZE_LIMIT < total_products
            ):
                if initialize_shop:
                    offset, new_total_products, lazada_products = shop._fetch_lazada_products(
                        offset=offset
                    )
                else:
                    offset, new_total_products, lazada_products = shop._fetch_lazada_products(
                        time_from=time_from, time_to=time_to, offset=offset
                    )

                if total_products is False:
                    total_products = new_total_products
                elif new_total_products != total_products:
                    raise ValidationError(
                        self.env._(
                            "Failed to synchronize Lazada product catalog for shop: %(shop)d.\n"
                            "The total number of products in Lazada changed during"
                            " synchronization. Please re-run the synchronization.",
                            shop=shop.id,
                        )
                    )

                for product in lazada_products:
                    product_status = (product.get("status") or "").lower()
                    for product_sku in product.get("skus"):
                        fulfillment_type = (
                            len(product_sku.get("fblWarehouseInventories", [])) and "fbl"
                        ) or "fbm"
                        # Consider item inactive if either product or SKU status is not "active"
                        sku_status = (product_sku.get("Status") or "").lower()
                        is_active = all(
                            status in ("", "active") for status in [product_status, sku_status]
                        )
                        lazada_item = shop._find_or_create_item(
                            product_sku["SellerSku"],
                            product_sku["SkuId"],
                            fulfillment_type=fulfillment_type,
                            no_create=not is_active,
                        )
                        # Disable inventory sync when Lazada item is inactive/deleted
                        if not is_active and lazada_item.sync_lazada_inventory:
                            lazada_item.sync_lazada_inventory &= is_active

            shop.last_product_catalog_sync_date = sync_start_dt

    def _fetch_lazada_products(self, time_from=None, time_to=None, offset=0):
        """Fetch products from Lazada API.

        :param datetime time_from: Lower time limit for filtering products
        :param datetime time_to: Upper time limit for filtering products
        :param int offset: Page offset for pagination
        :return: Tuple of (next_offset, total_products, products_list)
        :rtype: tuple
        """
        target_timezone = ZoneInfo(const.COUNTRY_TIMEZONE_MAPPING.get(self.country_id.code, "UTC"))
        params = {
            "offset": offset * const.PRODUCT_LIST_SIZE_LIMIT,
            "limit": const.PRODUCT_LIST_SIZE_LIMIT,
            "filter": "all",
        }
        if time_from and time_to:
            params.update({
                "update_after": time_from.astimezone(target_timezone).isoformat(),
                "update_before": time_to.astimezone(target_timezone).isoformat(),
            })
        response = utils.make_lazada_api_request("GetProducts", self, params=params)
        total_products = response["data"]["total_products"] if response.get("data") else 0
        products = response["data"]["products"] if response.get("data") else []
        return offset + 1, total_products, products

    # === ORDER SYNCHRONIZATION METHODS === #

    def _sync_orders(self, auto_commit=True):
        """Synchronize orders updated in Lazada since last sync.

        Syncs all active shops if called on empty recordset.

        :param bool auto_commit: Whether to commit after each successful order sync
        """
        shops = self or self.search([("active", "=", True)])
        for shop in shops:
            shop = shop.with_prefetch()
            start_sync_dt = fields.Datetime.now()
            try:
                # Orders are pulled in batches of up to ORDER_LIST_SIZE_LIMIT orders. If more can be
                # synchronized, the request results are paginated and the next page holds another
                # batch.
                while shop.last_orders_sync_date < start_sync_dt:
                    status_update_lower_limit = shop.last_orders_sync_date
                    status_update_upper_limit = min(
                        status_update_lower_limit + timedelta(days=const.ORDER_LIST_DAYS_LIMIT),
                        start_sync_dt,
                    )
                    orders_map = shop._fetch_order_list(
                        time_from=status_update_lower_limit, time_to=status_update_upper_limit
                    )
                    if not orders_map:
                        shop.last_orders_sync_date = status_update_upper_limit
                        continue

                    order_extern_id_list = list(orders_map.keys())
                    order_items_map = shop._fetch_orders_items(order_extern_id_list)
                    for order_id, order in orders_map.items():
                        order["order_items"] = order_items_map.get(int(order_id), [])

                    # Convert the maximum updated_at timestamp of the order items of
                    # each order to a timestamp at UTC timezone
                    for order in orders_map.values():
                        max_order_item_timestamp = max(
                            utils.lazada_timestamp_to_datetime(item.get("updated_at"))
                            for item in order["order_items"]
                        )
                        order["last_order_item_updated_at"] = max_order_item_timestamp

                    # As we fetched these order items based on order ids, not their updated time,
                    # orders might have been updated later than the set upper limit. We discard
                    # them for now to avoid skipping the intermediary orders by setting a wrong
                    # last updated time as they'll be sync later anyway.
                    valid_orders_map = {
                        id: order
                        for id, order in orders_map.items()
                        if order["last_order_item_updated_at"] <= status_update_upper_limit
                    }
                    if not valid_orders_map:
                        shop.last_orders_sync_date = status_update_upper_limit
                        continue

                    for order_data in valid_orders_map.values():
                        shop._create_or_update_sale_order(order_data, auto_commit)

                    # The sync of this orders batch went through, save the last status update time
                    valid_update_times = [
                        order["last_order_item_updated_at"] for order in valid_orders_map.values()
                    ]
                    if valid_update_times and len(order_items_map) == const.ORDER_LIST_SIZE_LIMIT:
                        shop.last_orders_sync_date = max(valid_update_times)
                    else:
                        shop.last_orders_sync_date = status_update_upper_limit

            except utils.LazadaRateLimitError as error:
                _logger.info(
                    "Rate limit reached while synchronizing sales orders for Lazada shop with"
                    " id %(shop)d. Operation: %(error_operation)s",
                    {"shop": shop.id, "error_operation": error.operation},
                )
                continue  # The remaining orders will be pulled in the next cron run.

    def _fetch_order_list(self, time_from, time_to):
        """Fetch order list from Lazada API.

        :param datetime time_from: Lower time limit
        :param datetime time_to: Upper time limit
        :return: Dict mapping order_id to order details
        :rtype: dict
        """
        target_timezone = ZoneInfo(const.COUNTRY_TIMEZONE_MAPPING.get(self.country_id.code, "UTC"))

        response = utils.make_lazada_api_request(
            "GetOrders",
            self,
            params={
                "update_after": time_from.astimezone(target_timezone).isoformat(),
                "update_before": time_to.astimezone(target_timezone).isoformat(),
                "limit": const.ORDER_LIST_SIZE_LIMIT,
                "offset": 0,
                "sort_by": "updated_at",
                "sort_direction": "ASC",
            },
        )
        return {i["order_id"]: i for i in response["data"].get("orders", [])}

    def _fetch_orders_items(self, order_extern_id_list):
        """Fetch order items from Lazada API.

        :param list order_extern_id_list: List of order identifiers
        :return: Dict mapping order_id to order items
        :rtype: dict
        """
        order_items_map = {}
        for batch in split_every(const.ORDER_DETAIL_SIZE_LIMIT, order_extern_id_list, list):
            response = utils.make_lazada_api_request(
                "GetMultipleOrderItems", self, params={"order_ids": str(batch)}
            )
            order_items_map.update({
                item["order_id"]: item["order_items"] for item in response["data"]
            })

        return order_items_map

    def _fetch_seller_information(self):
        """Fetch seller information from Lazada API.

        :return: Seller data including seller_id, name
        :rtype: dict
        """
        self.ensure_one()
        response = utils.make_lazada_api_request("GetSeller", self, params={})
        return response["data"]

    def _create_or_update_sale_order(self, order_data, auto_commit=True):
        """Create or update sale order from Lazada order data.

        :param dict order_data: Order data from Lazada API
        :param bool auto_commit: Whether to commit after successful sync
        """
        try:
            if order_data["items_count"] == 0:
                return

            if auto_commit:
                with self.env.cr.savepoint():
                    self._process_order_data(order_data)
            else:  # Avoid the savepoint in testing
                self._process_order_data(order_data)
        except utils.LazadaRateLimitError:
            raise
        except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY as error:
            _logger.info(
                "A concurrency error happened while synchronizing order %(order_id)s, it will be"
                " synchronized later. %(error)s",
                {"order_id": order_data["order_id"], "error": error},
            )
        except utils.LazadaApiError:
            lazada_order_ref = order_data["order_id"]
            _logger.warning(
                "A business error occurred while processing the order data"
                " with lazada_order_ref %(order_ref)s for Lazada shop %(shop)s.",
                {"order_ref": lazada_order_ref, "shop": self.id},
                exc_info=True,
            )
            # Dismiss business errors to allow the synchronization to skip the
            #  problematic orders.
            # The order will then require creating the order manually.
            self.env.cr.rollback()
            self._handle_sync_failure(flow="order_sync", lazada_order_ref=lazada_order_ref)
        if auto_commit:
            self.env.cr.commit()  # Commit to mitigate a potential cron kill.

    def _process_order_data(self, order_data):
        """Process Lazada order data and create or update sale order.

        Creates new orders if status is in ORDER_STATUSES_TO_SYNC, otherwise updates
        existing order items.

        :param dict order_data: Order data from Lazada API
        :return: Created or updated sale order
        :rtype: sale.order or None
        """
        fulfillment_type = self._get_fulfillment_type(order_data)
        if not fulfillment_type:
            _logger.info(
                "Ignored Lazada order with reference %(ref)s for Lazada shop with id %(id)s."
                " Multiple fulfillment types in 1 order is not supported.",
                {"ref": order_data["order_id"], "id": self.id},
            )
            return None

        lazada_order_ref = order_data["order_id"]
        order = self.env["sale.order"].search(
            [("lazada_order_ref", "=", lazada_order_ref), ("lazada_shop_id", "=", self.id)], limit=1
        )

        if order:
            self._update_order_from_data(order, order_data)
        elif self._should_create_order(order_data, fulfillment_type):
            order = self._create_order_from_data(order_data)
            if order.lazada_fulfillment_type == "fbl":
                self._generate_stock_moves(order)
            elif order.lazada_fulfillment_type == "fbm":
                order.action_lock()
            _logger.info(
                "Created a new sales order with lazada_order_ref %(ref)s for Lazada shop"
                " with id %(id)s.",
                {"ref": lazada_order_ref, "id": self.id},
            )
        return order

    def _get_fulfillment_type(self, order_data):
        """Get fulfillment type from order data.

        :param dict order_data: Order data from Lazada API
        :return: 'fbm' or 'fbl'
        :rtype: str
        """
        fulfillment_type_list = list({
            "fbl" if int(item["is_fbl"]) else "fbm" for item in order_data["order_items"]
        })
        if len(fulfillment_type_list) == 1:
            return fulfillment_type_list[0]
        return None

    def _should_create_order(self, order_data, fulfillment_type):
        """Determine if order should be created based on status.

        :param dict order_data: Order data from Lazada API
        :param str fulfillment_type: 'fbm' or 'fbl'
        :return: True if order should be created
        :rtype: bool
        """
        # The provider type of DBS order is "seller_own_fleet", which is not supported for now.
        provider_types = {item.get("shipping_provider_type") for item in order_data["order_items"]}
        invalid_types = provider_types - const.SUPPORTED_SHIPPING_PROVIDER_TYPES
        statuses = set(order_data["statuses"])
        statuses_to_sync = const.ORDER_STATUSES_TO_SYNC.get(fulfillment_type, set())
        invalid_statuses = statuses - statuses_to_sync

        skip_reasons = []
        if invalid_types:
            skip_reasons.append(
                f"- Unsupported shipping provider type(s): {', '.join(invalid_types)}."
                f" Supported type(s): {', '.join(const.SUPPORTED_SHIPPING_PROVIDER_TYPES)}."
            )
        if invalid_statuses:
            skip_reasons.append(
                f"- Unsupported order status(es): {', '.join(invalid_statuses)}."
                f" Expected status(es): {', '.join(statuses_to_sync)}."
            )
        if skip_reasons:
            _logger.info(
                "Skipped Lazada order %(ref)s for Lazada shop %(id)s.\n%(reasons)s",
                {"ref": order_data["order_id"], "id": self.id, "reasons": "\n".join(skip_reasons)},
            )

        return not (invalid_statuses or invalid_types)

    def _generate_stock_moves(self, order):
        """
        Generate a stock move for each product of the provided sales order.

        :param sale.order order: The sales order to generate stock moves.
        :return: The generated stock moves.
        :rtype: stock.move
        """
        customers_location = self.env.ref("stock.stock_location_customers")
        for order_line in order.order_line.filtered(
            lambda line: line.product_id.type != "service" and not line.display_type
        ):
            stock_move = self.env["stock.move"].create({
                "company_id": self.company_id.id,
                "product_id": order_line.product_id.id,
                "product_uom_qty": order_line.product_uom_qty,
                "uom_id": order_line.product_uom_id.id,
                "location_id": self.fbl_location_id.id,
                "location_dest_id": customers_location.id,
                "state": "confirmed",
                "sale_line_id": order_line.id,
            })
            stock_move._set_quantity_done(order_line.product_uom_qty)
            stock_move.picked = True  # To also change move lines created in `_set_quantity_done`
            stock_move._action_done()

    def _get_shipping_carrier(self, order_data):
        """Extract shipping carrier code from order data.

        :param dict order_data: Order data from Lazada API
        :return: Shipping carrier code or empty string
        :rtype: str
        """
        unique_providers = []
        for item in order_data["order_items"]:
            provider_type = item.get("shipping_provider_type")
            provider = item.get("shipment_provider")
            if not (provider and provider_type):
                continue
            provider_info = {"provider_type": provider_type, "shipment_provider": provider}
            if provider_info not in unique_providers:
                unique_providers.append(provider_info)

        if (
            len(unique_providers) != 1
            or unique_providers[0]["provider_type"] not in const.SUPPORTED_SHIPPING_PROVIDER_TYPES
        ):
            return ""

        return unique_providers[0]["shipment_provider"]

    def _update_picking_from_data(self, picking, order_data):
        """Update picking from Lazada order data.

        :param stock.picking picking: Picking record
        :param dict order_data: Order data from Lazada API
        """
        if picking.package_extern_id:
            package_item_data = [
                item
                for item in order_data["order_items"]
                if item.get("package_id") == picking.package_extern_id
            ]
        else:
            package_item_data = order_data["order_items"]

        if not package_item_data:
            return

        # ignore if the picking is already synced
        max_update_time = max(
            utils.lazada_timestamp_to_datetime(item["updated_at"]) for item in package_item_data
        )
        if max_update_time <= picking.last_lazada_picking_sync_date:
            return

        shipping_carrier_code = self._get_shipping_carrier(order_data)
        shipping_product = self._find_matching_product(
            shipping_carrier_code, "default_shipping_product", "Shipping", "service"
        )
        delivery_method = self._find_or_create_delivery_carrier(
            shipping_carrier_code, shipping_product
        )

        tracking_number_list = list({
            item["tracking_code"] for item in package_item_data if item["tracking_code"]
        })
        tracking_number = tracking_number_list[0] if len(tracking_number_list) == 1 else ""

        picking.write({
            "carrier_id": delivery_method.id,
            "carrier_tracking_ref": tracking_number,
            "package_extern_id": package_item_data[0].get("package_id"),
            "last_lazada_picking_sync_date": max_update_time,
        })

    def _update_order_from_data(self, order, order_data):
        """Update sale order from Lazada order data.

        :param sale.order order: Sale order record
        :param dict order_data: Order data from Lazada API
        """
        order.ensure_one()
        if order.lazada_fulfillment_type != "fbl":
            order_item_map = {
                str(item["order_item_id"]): item for item in order_data["order_items"]
            }
            for order_item in order.order_line.lazada_order_item_ids:
                item_data = order_item_map.get(order_item.order_item_extern_id)
                if item_data:
                    order_item.status = const.ORDER_ITEM_STATUS_MAPPING.get(
                        item_data.get("status"), "manual"
                    )

            for picking in order.picking_ids.filtered("last_lazada_picking_sync_date"):
                self._update_picking_from_data(picking, order_data)

        if order.lazada_order_status == "canceled" and order.state != "cancel":
            order._action_cancel()
            _logger.info(
                "Cancelled sales order with Lazada Order Ref %(ref)s of shop %(name)s.",
                {"ref": order.lazada_order_ref, "name": self.name},
            )

    def _create_order_from_data(self, order_data):
        """Create sale order from Lazada order data.

        :param dict order_data: Order data from Lazada API
        :return: Created sale order
        :rtype: sale.order
        """
        # Prepare the order values
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", order_data["order_items"][0]["currency"])], limit=1)
        )
        lazada_order_ref = order_data["order_id"]
        contact_partner, delivery_partner = self._find_or_create_partners_from_data(
            order_data
        )
        fiscal_position = (
            self.env["account.fiscal.position"]
            .with_company(self.company_id)
            ._get_fiscal_position(contact_partner, delivery_partner)
        )

        fulfillment_type = self._get_fulfillment_type(order_data)
        order_income = {
            "voucher": order_data.get("voucher"),
            "shipping_fee": order_data.get("shipping_fee"),
        }
        order_lines_values = self.with_context(
            order_income=order_income
        )._prepare_order_lines_values(order_data, currency, fiscal_position)
        order_lines = [
            Command.create(order_line_values)
            for order_line_values in order_lines_values
        ]
        origin = self.env._(
            "Lazada Order %(lazada_order_ref)s at %(name)s",
            lazada_order_ref=lazada_order_ref,
            name=self.name,
        )
        date_order = utils.lazada_timestamp_to_datetime(order_data["created_at"])

        order_vals = {
            "origin": origin,
            "state": "sale",
            "locked": fulfillment_type == "fbl",
            "date_order": date_order,
            "partner_id": contact_partner.id,
            "pricelist_id": self._find_or_create_pricelist(currency).id,
            "order_line": order_lines,
            "invoice_status": "no",
            "partner_shipping_id": delivery_partner.id,
            "require_signature": False,
            "prepayment_percent": 0,
            "fiscal_position_id": fiscal_position.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "team_id": self.team_id.id,
            "lazada_order_ref": lazada_order_ref,
            "lazada_shop_id": self.id,
            "lazada_fulfillment_type": fulfillment_type or "fbm",
        }
        if fulfillment_type == "fbl" and self.fbl_location_id.warehouse_id:
            order_vals["warehouse_id"] = self.fbl_location_id.warehouse_id.id
        elif fulfillment_type == "fbm" and self.fbm_warehouse_id:
            order_vals["warehouse_id"] = self.fbm_warehouse_id.id

        order = (
            self.env["sale.order"]
            .with_context(mail_create_nosubscribe=True)
            .with_company(self.company_id)
            .create(order_vals)
        )

        # price from Lazada API does not include shipping fee and voucher
        lazada_total = (
            float(order_data.get("price") or 0)
            + float(order_data.get("shipping_fee") or 0)
            - float(order_data.get("voucher") or 0)
        )
        self._adjust_order_total(order, currency, lazada_total)

        if order.picking_ids and fulfillment_type != "fbl":
            # Initialize the lazada order items from the sale order lines
            order.picking_ids.move_ids.initialize_lazada_order_items()
            self._update_order_from_data(order, order_data)
        return order

    def _adjust_order_total(self, order, currency, lazada_total):
        """Adjust the order total to reconcile with Lazada's ``price``.

        A single tax-free adjustment line absorbs the full residue. The residue
        can come from any other component not explicitly modeled as a sale order line.

        :param sale.order order: The order to adjust.
        :param res.currency currency: The currency of the order.
        :param float lazada_total: The total amount from Lazada.
        """
        residue = lazada_total - order.amount_total
        if not order.amount_total or currency.is_zero(residue):
            return

        adjustment_product = self._find_matching_product(
            internal_reference="",
            default_xmlid="default_adjustment_product",
            default_name=self.env._("Lazada Amount Adjustment"),
            default_type="service",
        )
        order.order_line.create(
            {
                "order_id": order.id,
                "product_id": adjustment_product.id,
                "price_unit": residue,
                "tax_ids": [],
            }
        )

    def _prepare_discount_lines_values(self, currency, tax_group_bases, discount_total):
        """Distribute an order-level discount across the product tax groups.

        One negative discount line is created per distinct tax group, allocated
        pro-rata to each group's buyer-paid (tax-inclusive) merchandise, so the
        discount reduces each group's taxable base correctly. The allocation
        sums exactly to ``discount_total``; the remainder lands on the largest
        group, leaving only price rounding for the amount-adjustment line. With
        a single tax group, this collapses to one discount line.

        :param res.currency currency: The currency of the sale order.
        :param dict tax_group_bases: Map of tax-id tuple to ``{'taxes', 'base'}``.
        :param float discount_total: The order-level discount to distribute.
        :return: The discount-line values list ready for ``Command.create``.
        :rtype: list[dict]
        """
        if currency.is_zero(discount_total) or not tax_group_bases:
            return []

        discount_product = self._find_matching_product(
            internal_reference="",
            default_xmlid="default_discount_product",
            default_name=self.env._("Lazada Order Discount"),
            default_type="service",
        )
        total_base = sum(tax_group_bases.values())

        # Largest group first: in the degenerate zero-base case (no merchandise to weight the
        # split by) the whole discount lands on it rather than on a marginal group.
        tax_groups = sorted(
            [{"taxes": taxes, "base": base} for taxes, base in tax_group_bases.items()],
            key=lambda tax_group: tax_group["base"],
            reverse=True,
        )

        discount_lines_values = []
        allocated_discount = 0.0
        for index, tax_group in enumerate(tax_groups):
            if index == len(tax_groups) - 1 or currency.is_zero(total_base):
                group_discount = discount_total - allocated_discount
            else:
                group_discount = currency.round(
                    discount_total * tax_group["base"] / total_base
                )
            allocated_discount += group_discount
            if currency.is_zero(group_discount):
                continue
            discount_subtotal = self._compute_subtotal(
                -group_discount, tax_group["taxes"], currency
            )
            discount_lines_values.append(
                self._convert_to_order_line_values(
                    product_id=discount_product.id,
                    subtotal=discount_subtotal,
                    description=self.env._("Order Discount"),
                    tax_ids=tax_group["taxes"].ids,
                )
            )
        return discount_lines_values

    def _convert_to_order_line_values(self, **kwargs):
        """Convert values to sale order line format.

        :param dict kwargs: Values including product_id, quantity, subtotal, order_items, etc.
        :return: Sale order line values dict
        :rtype: dict
        """
        subtotal = kwargs.get("subtotal", 0)
        quantity = kwargs.get("quantity", 1)
        tax_ids = kwargs.get("tax_ids")
        order_item_values = [
            Command.create(
                {
                    "order_item_extern_id": str(item["order_item_id"]),
                    "status": const.ORDER_ITEM_STATUS_MAPPING.get(
                        item.get("status"), "manual"
                    ),
                }
            )
            for item in kwargs.get("order_items") or []
        ]
        return {
            "name": kwargs.get("description", ""),
            "product_id": kwargs.get("product_id"),
            "price_unit": subtotal / quantity if quantity else 0,
            "tax_ids": tax_ids if tax_ids else [],
            "product_uom_qty": quantity,
            "lazada_order_item_ids": order_item_values,
        }

    def _prepare_order_lines_values(self, order_data, currency, fiscal_pos):
        """Prepare the sale order lines values from the Lazada order data.

        Each SKU becomes one ``sale.order.line`` values dict (Lazada groups
        multiple order items under the same SKU). The order-level voucher and
        shipping fee are read from the ``order_income`` context key. Shipping
        is appended as a final line when the shipping fee is non-zero.

        :param dict order_data: The order data from the Lazada API.
        :param res.currency currency: The currency of the sale order.
        :param account.fiscal.position fiscal_pos: The fiscal position of the sale order.
        :return: The order-line values list ready for ``Command.create``.
        :rtype: list[dict]
        """
        self.ensure_one()

        order_income = self.env.context.get("order_income") or {}
        order_lines_values = []
        # Buyer-paid (tax-inclusive) merchandise per distinct tax group, used to
        # distribute the order-level discount in `_prepare_discount_lines_values`.
        tax_group_bases = {}
        sku_items = {}
        for item_data in order_data["order_items"]:
            sku_items.setdefault(item_data["sku"], []).append(item_data)

        for sku, items in sku_items.items():
            # Use first item for common info
            common_item_data = items[0]
            fulfillment_type = "fbl" if common_item_data["is_fbl"] else "fbm"
            item_extern_id = common_item_data["sku_id"]

            lazada_item = self._find_or_create_item(
                sku, item_extern_id, fulfillment_type=fulfillment_type
            )
            product_taxes = lazada_item.product_id.taxes_id._filter_taxes_by_company(
                self.company_id
            )
            taxes = fiscal_pos.map_tax(product_taxes)

            quantity = len([i for i in items if i.get("status") != "canceled"])
            paid_total = sum(float(item["paid_price"]) for item in items)

            description = self._build_item_description(sku, common_item_data, currency)
            subtotal = self._compute_subtotal(paid_total, taxes, currency)

            order_lines_values.append(
                self._convert_to_order_line_values(
                    product_id=lazada_item.product_id.id,
                    subtotal=subtotal,
                    description=description,
                    quantity=quantity,
                    tax_ids=taxes.ids,
                    order_items=items,
                )
            )
            tax_group_bases[taxes] = tax_group_bases.get(taxes, 0.0) + paid_total

        # Order-level discount lines (e.g. cart vouchers), distributed per tax group.
        discount_total = float(order_income.get("voucher") or 0)
        order_lines_values += self._prepare_discount_lines_values(
            currency, tax_group_bases, discount_total
        )

        # Shipping line.
        shipping_fee = float(order_income.get("shipping_fee") or 0)
        if not currency.is_zero(shipping_fee):
            shipping_carrier_code = self._get_shipping_carrier(order_data)
            shipping_product = self._find_matching_product(
                internal_reference=shipping_carrier_code,
                default_xmlid="default_shipping_product",
                default_name=self.env._("Lazada Shipping"),
                default_type="service",
            )
            shipping_taxes_raw = shipping_product.taxes_id._filter_taxes_by_company(
                self.company_id
            )
            shipping_taxes = fiscal_pos.map_tax(shipping_taxes_raw)
            shipping_subtotal = self._compute_subtotal(
                shipping_fee, shipping_taxes, currency
            )
            shipping_name = (
                self.env._("Shipping: %(carrier)s", carrier=shipping_carrier_code)
                if shipping_carrier_code
                else self.env._("Shipping")
            )
            order_lines_values.append(
                self._convert_to_order_line_values(
                    product_id=shipping_product.id,
                    subtotal=shipping_subtotal,
                    description=shipping_name,
                    tax_ids=shipping_taxes.ids,
                )
            )

        return order_lines_values

    def _build_item_description(self, sku, item_data, currency):
        """Build the base description text for a Lazada item line.

        Includes header, optional voucher line (guarded against absence of
        ``voucher_code_seller``), and an original-price line when the item
        was discounted.

        :param str sku: The item SKU (used in the header).
        :param dict item_data: The Lazada item payload.
        :param res.currency currency: The currency (used to format the original price).
        :return: The multi-line description text.
        :rtype: str
        """
        lines = [f"[{sku}] {item_data['name']}"]
        voucher_code = item_data.get("voucher_code_seller")
        if voucher_code:
            lines.append(
                self.env._(
                    "Voucher id: %(voucher_id)s\nOriginal price: %(price)s",
                    voucher_id=voucher_code,
                    price=currency.format(float(item_data["item_price"])),
                )
            )

        return "\n".join(lines)

    def _find_matching_product(
        self, internal_reference, default_xmlid, default_name, default_type, fallback=True
    ):
        """Find product by internal reference or return default product.

        :param str internal_reference: Product internal reference (SKU)
        :param str default_xmlid: XML ID of default fallback product
        :param str default_name: Name for default product if restored
        :param str default_type: Type for default product if restored
        :param bool fallback: Whether to fallback to default product
        :return: Product record
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
                f"sale_lazada.{default_xmlid}", raise_if_not_found=False
            ) or self.env["product.product"]._restore_lazada_data_product(
                default_name, default_type, default_xmlid
            )
        return product

    def _find_or_create_partners_from_data(self, order_data):
        """Find or create contact and delivery partners from order data.

        :param dict order_data: Order data from Lazada API
        :return: Tuple of (contact_partner, delivery_partner)
        :rtype: tuple
        """
        self.ensure_one()

        lazada_buyer_extern_id = str(order_data["order_items"][0]["buyer_id"])
        buyer_name = f"{order_data['customer_first_name']} {order_data['customer_last_name']}"
        shipping_address_name = (
            f"{order_data['address_shipping']['first_name']}"
            f" {order_data['address_shipping']['last_name']}"
        )
        city = order_data["address_shipping"]["city"]
        street = order_data["address_shipping"]["address1"]
        street2 = order_data["address_shipping"]["address2"]
        zip_code = order_data["address_shipping"].get("post_code")
        state_name = order_data["address_shipping"]["address3"]
        country_name = order_data["address_shipping"]["country"]
        phone = order_data["address_shipping"]["phone"]

        country = self.env["res.country"].search([("code", "=ilike", country_name)], limit=1)
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
            "lazada_buyer_extern_id": lazada_buyer_extern_id,
        }

        # Try to find existing contact partner
        contact_partner = self.env["res.partner"].search(
            [
                ("lazada_buyer_extern_id", "=", lazada_buyer_extern_id),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )

        if not contact_partner:
            partner_vals["name"] = buyer_name
            contact_partner = self.env["res.partner"].create(partner_vals)

        if (
            shipping_address_name != buyer_name
            or partner_vals["street"] != contact_partner.street
            or partner_vals["street2"] != contact_partner.street2
            or partner_vals["city"] != contact_partner.city
            or partner_vals["phone"] != contact_partner.phone
        ):
            delivery_vals = partner_vals.copy()
            delivery_vals.update({
                "name": shipping_address_name,
                "parent_id": contact_partner.id,
                "type": "delivery",
            })
            delivery_partner = self.env["res.partner"].create(delivery_vals)
        else:
            delivery_partner = contact_partner

        return contact_partner, delivery_partner

    def _find_or_create_delivery_carrier(self, shipping_carrier_code, shipping_product):
        """Find or create delivery carrier by shipping code.

        :param str shipping_carrier_code: Shipping carrier code
        :param record shipping_product: Shipping product record (product.product)
        :return: Delivery carrier record
        :rtype: delivery.carrier
        """
        delivery_method = self.env["delivery.carrier"].search(
            [("name", "=", shipping_carrier_code)], limit=1
        )
        if shipping_carrier_code and not delivery_method:
            delivery_method = self.env["delivery.carrier"].create({
                "name": shipping_carrier_code,
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
                "name": f"Lazada {currency.name}",
                "currency_id": currency.id,
                "company_id": self.company_id.id,
                "active": False,
            })

        return pricelist

    def _compute_subtotal(self, total, taxes, currency):
        """Compute the subtotal from the taxes.

        Lazada does not include the tax amount of the order; we need to recompute the subtotal from
        the taxes on the product (or those given by the fiscal position) to match the order total.

        To achieve this, the subtotal is recomputed from the taxes for the total to match that of
        the order. If the taxes used are not identical to those used by Lazada, the recomputed
        subtotal will differ from the original subtotal.

        :param float total: The original total.
        :param account.tax taxes: The final taxes to use for the computation of the new subtotal.
        :param res.currency currency: The currency used by the rounding methods.
        :return: The new subtotal.
        :rtype: float
        """
        taxes_res = taxes.with_context(
            force_price_include=True, round_base=False
        ).compute_all(total, currency=currency)
        subtotal = taxes_res["total_included"]
        for tax_res in taxes_res["taxes"]:
            tax = self.env["account.tax"].browse(tax_res["id"])
            if not tax.price_include:
                subtotal -= tax_res["amount"]
        return subtotal

    def _find_or_create_item(self, sku, item_extern_id, fulfillment_type="fbm", no_create=False):
        """Find or create Lazada item mapping.

        Links Lazada items to Odoo products based on SKU.

        :param str sku: Product SKU
        :param str item_extern_id: Lazada item ID
        :param str fulfillment_type: 'fbm' or 'fbl' (optional)
        :return: Lazada item record
        :rtype: lazada.item
        """
        self.ensure_one()
        lazada_item = self.lazada_item_ids.filtered(
            lambda i: i.lazada_item_extern_id == str(item_extern_id)
        )
        if not lazada_item and not no_create:
            item_vals = {
                "product_id": self._find_matching_product(
                    sku, "default_sale_product", "Lazada Sales", "consu"
                ).id,
                "shop_id": self.id,
                "lazada_item_extern_id": item_extern_id,
                "fulfillment_type": fulfillment_type,
                "lazada_sku": sku,
            }
            lazada_item = self.env["lazada.item"].create(item_vals)
        # If the item has been linked with the default product, check if another product
        # has now been assigned the current SKU as internal reference and update if so
        else:
            if "sale_lazada.default_sale_product" in lazada_item.product_id._get_external_ids().get(
                lazada_item.product_id.id, []
            ):
                product = self._find_matching_product(sku, "", "", "", fallback=False)
                if product:
                    lazada_item.product_id = product.id

            item_vals = {}
            if lazada_item.lazada_sku != sku:
                item_vals["lazada_sku"] = sku
            if fulfillment_type and lazada_item.fulfillment_type != fulfillment_type:
                item_vals["fulfillment_type"] = fulfillment_type
            if item_vals:
                lazada_item.write(item_vals)

        return lazada_item

    # === OTHER HELPER METHODS === #

    def _get_shop_vals(self, code):
        """Create shop values from Lazada authorization code.

        :param str code: Authorization code from Lazada
        :return: Dict of shop values (tokens, country_id, shop_extern_id)
        :rtype: dict
        """
        self.ensure_one()
        token_data = utils.request_access_token(self, authorization_code=code)
        if not token_data:
            raise ValidationError(self.env._("Failed to get token from Lazada."))
        country_id = (
            self.env["res.country"].search([("code", "=", token_data["country"].upper())]).id
        )
        if not country_id:
            raise ValidationError(
                self.env._("Could not find country with code %(code)s", code=token_data["country"])
            )
        if not len(token_data.get("country_user_info", [])):
            raise ValidationError(self.env._("Could not allocate the shop identifier"))

        shop_extern_id = token_data["country_user_info"][0]["seller_id"]
        expiration_date = fields.Datetime.now() + timedelta(seconds=token_data["expires_in"])
        refresh_expiration_date = fields.Datetime.now() + timedelta(
            seconds=token_data["refresh_expires_in"]
        )
        return {
            "country_id": country_id,
            "shop_extern_id": shop_extern_id,
            "access_token": token_data["access_token"],
            "access_token_expiration_date": expiration_date,
            "refresh_token": token_data["refresh_token"],
            "refresh_token_expiration_date": refresh_expiration_date,
        }

    def _handle_sync_failure(self, flow="", lazada_order_ref=False, error_messages=False):
        """Send failure notification email to shop manager.

        :param str flow: Sync flow type: 'order_sync' or 'inventory_sync'
        :param str lazada_order_ref: Lazada order reference (for order_sync flow)
        """
        mail_template_id = ""
        if flow == "order_sync":
            _logger.error(
                "Failed to synchronize order with lazada reference %(ref)s for lazada.shop with"
                " id %(shop_id)s (Shope Name: %(shop_name)s)."
                "Please create the order manually.",
                {"ref": lazada_order_ref, "shop_id": self.id, "shop_name": self.name},
            )
            mail_template_id = "sale_lazada.order_sync_failure"
        elif flow == "inventory_sync":
            _logger.error(
                "Failed to synchronize the inventory for items in lazada.shop with id"
                " %(shop_id)s (Shope Name: %(shop_name)s).",
                {"shop_id": self.id, "shop_name": self.name},
            )
            mail_template_id = "sale_lazada.inventory_sync_failure"

        mail_template = self.env.ref(mail_template_id, raise_if_not_found=False)
        if not mail_template:
            _logger.error(
                "The mail template with xmlid %(mail_template)s has been deleted.",
                {"mail_template": mail_template_id},
            )
        else:
            responsible_emails = {
                user.email
                for user in filter(
                    None, (self.user_id, self.env.ref("base.user_admin", raise_if_not_found=False))
                )
            }
            mail_template.with_context(
                email_to=",".join(responsible_emails),
                lazada_order_ref=lazada_order_ref,
                error_messages=error_messages,
                lazada_shop=self.name,
            ).send_mail(self.env.user.id)
            _logger.info(
                "Sent synchronization failure notification email to %(emails)s",
                {"emails": ", ".join(responsible_emails)},
            )
