# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import split_every

from odoo.addons.sale_lazada import const, utils


class LazadaItem(models.Model):
    """Lazada Item - Mapping between Odoo products and Lazada items.

    Used for inventory synchronization from Odoo to Lazada.
    """

    _name = "lazada.item"
    _description = "Lazada Item"
    _check_company_auto = True

    shop_id = fields.Many2one(
        string="Shop", comodel_name="lazada.shop", ondelete="cascade", required=True, index=True
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        ondelete="cascade",
        required=True,
        index=True,
        check_company=True,
    )
    product_tmpl_id = fields.Many2one(
        string="Product Template", related="product_id.product_tmpl_id"
    )
    company_id = fields.Many2one(related="shop_id.company_id")
    lazada_sku = fields.Char(
        string="Lazada SKU",
        help="The SKU of the item in Lazada. Odoo can match the product when the Lazada SKU is "
        "equivalent to the default code of the product.",
        readonly=True,
    )
    lazada_item_extern_id = fields.Char(
        string="Lazada Item ID",
        help="The unique identifier for an item in Lazada. An item in Lazada is equivalent "
        "to a product variant in Odoo.",
        readonly=True,
        required=True,
    )
    last_inventory_sync_date = fields.Datetime(readonly=True, default=fields.Datetime.now)
    sync_lazada_inventory = fields.Boolean(
        string="Synchronize Inventory to Lazada",
        help="Enable this to allow pushing the product inventory quantities from Odoo to Lazada.",
        precompute=True,
        compute="_compute_sync_lazada_inventory",
        store=True,
        readonly=False,
    )
    fulfillment_type = fields.Selection(
        selection=[("fbm", "Fulfillment by Merchant"), ("fbl", "Fulfillment by Lazada")],
        readonly=True,
        default="fbm",
    )

    _unique_lazada_item_extern_id = models.Constraint(
        "UNIQUE(shop_id, lazada_item_extern_id)",
        "Item External IDs must be unique for a given shop.",
    )

    # === BUSINESS METHODS === #

    @api.constrains("sync_lazada_inventory", "fulfillment_type", "product_id")
    def _check_sync_to_lazada(self):
        """Ensure only FBM items can be synced to Lazada and only products that track stock in Odoo
        can be synced to Lazada."""
        default_sale_product = self.env.ref("sale_lazada.default_sale_product")
        for item in self.filtered(lambda item: item.product_id != default_sale_product):
            if item.product_id.type != "consu":
                raise ValidationError(self.env._("Only goods are supported with Lazada."))
            if item.sync_lazada_inventory and item.fulfillment_type != "fbm":
                raise ValidationError(self.env._("Only FBM items can be synced to Lazada."))
            if item.sync_lazada_inventory and not item.product_id.is_storable:
                raise ValidationError(
                    self.env._(
                        "This product does not track inventory and can not be"
                        " synchronized with Lazada."
                    )
                )

    @api.depends("fulfillment_type", "product_id.is_storable")
    def _compute_sync_lazada_inventory(self):
        for item in self:
            item.sync_lazada_inventory = (
                item.fulfillment_type == "fbm" and item.product_id.is_storable
            )

    def _sync_inventory(self, auto_commit=True):
        """Synchronize inventory from Odoo to Lazada for FBM items.

        Only syncs storable products marked for synchronization.

        :param bool auto_commit: Whether to commit after each successful sync
        """
        error_messages = []
        valid_items = self.filtered("sync_lazada_inventory").sorted("last_inventory_sync_date")
        for shop, items in valid_items.grouped("shop_id").items():
            try:
                shop = shop.with_prefetch()
                items = items.with_prefetch()
                self._update_inventory(shop, items)
                if auto_commit:
                    self.env.cr.commit()
            except utils.LazadaApiError as error:
                error_messages.append({
                    "default_codes": items.mapped("product_id.default_code"),
                    "message": str(error),
                })
        if error_messages:
            self.shop_id._handle_sync_failure(flow="inventory_sync", error_messages=error_messages)

    @api.model
    def _prepare_sync_inventory_payload(self, shop, items):
        """Prepare JSON payload for inventory sync API request.

        :param shop: Lazada shop record
        :param items: Items to synchronize
        :return: JSON string payload
        :rtype: str
        """
        vals = []
        warehouse_id = shop.fbm_warehouse_id.id
        is_same_warehouse = shop.fbl_location_id.warehouse_id.id == warehouse_id
        for item in items:
            # Quantity of stock in FBM warehouse is calculated as:
            # FBM warehouse stock - FBL location stock (if same warehouse)
            fbm_item = item.with_context(warehouse_id=warehouse_id).with_company(shop.company_id)
            fbm_qty = fbm_item.product_id.free_qty
            if not shop.manage_fbl_inventory and is_same_warehouse:
                fbl_item = item.with_context(location=shop.fbl_location_id.id).with_company(
                    shop.company_id
                )
                fbm_qty = fbm_qty - fbl_item.product_id.free_qty
            fbm_qty = int(max(fbm_qty, 0))
            vals.append({
                "SkuId": item.lazada_item_extern_id,
                "SellerSku": item.lazada_sku,
                "SellableQuantity": fbm_qty,
            })
        return json.dumps({"Request": {"Product": {"Skus": {"Sku": vals}}}})

    # === API METHODS === #

    def _update_inventory(self, shop, items):
        """Update inventory quantities on Lazada for given items.

        Processes items in batches to respect API limits.

        :param shop: Lazada shop record
        :param items: Items to update
        :raises Exception: If API response indicates failure
        """
        shop.ensure_one()
        for batch_items in split_every(const.SYNC_INVENTORY_SIZE_LIMIT, items.ids, items.browse):
            current_datetime = fields.Datetime.now()
            payload = self._prepare_sync_inventory_payload(shop, batch_items)
            utils.make_lazada_api_request(
                "UpdateSellableQuantity", shop, params={"payload": payload}, method="POST"
            )

            batch_items.last_inventory_sync_date = current_datetime
