# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.sale_tiktok import utils

_logger = logging.getLogger(__name__)


class TikTokItem(models.Model):
    """TikTok Item - Mapping between Odoo products and TikTok Shop items.

    Used for inventory synchronization from Odoo to TikTok Shop.
    """

    _name = "tiktok.item"
    _description = "TikTok Shop Item"
    _check_company_auto = True

    shop_id = fields.Many2one(
        string="Shop", comodel_name="tiktok.shop", ondelete="cascade", required=True, index=True
    )
    product_id = fields.Many2one(
        string="Product",
        comodel_name="product.product",
        ondelete="cascade",
        required=True,
        check_company=True,
        index="btree_not_null",
    )
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id")
    company_id = fields.Many2one(related="shop_id.company_id")
    tiktok_seller_sku = fields.Char(
        string="Seller SKU",
        help="The seller SKU in TikTok. A Seller SKU in TikTok is equivalent to"
        " the product default code in Odoo.",
        readonly=True,
    )
    tiktok_sku_extern_id = fields.Char(
        string="SKU ID",
        help="The unique identifier for a SKU in TikTok. A SKU in TikTok is equivalent to a"
        " product variant in Odoo.",
    )
    tiktok_item_extern_id = fields.Char(
        string="Item ID",
        help="The unique identifier for an item in TikTok. An item in TikTok is equivalent"
        " to a product in Odoo.",
    )
    sync_to_tiktok = fields.Boolean(
        string="Sync Inventory to TikTok",
        help="Enable this to allow pushing the product inventory quantities from Odoo to TikTok.",
        precompute=True,
        compute="_compute_sync_to_tiktok",
        store=True,
        readonly=False,
    )
    last_inventory_sync_date = fields.Datetime(
        string="Last Sync Date", readonly=True, default=fields.Datetime.now
    )

    _unique_tiktok_item_and_sku_external_ids = models.Constraint(
        "UNIQUE(shop_id, tiktok_item_extern_id, tiktok_sku_extern_id)",
        "Item and SKU external IDs must be unique for a given shop.",
    )

    @api.constrains("sync_to_tiktok", "product_id")
    def _check_sync_to_tiktok_constraints(self):
        """Ensure only products that track stock in Odoo can be synced to TikTok."""
        for item in self:
            if item.sync_to_tiktok and (
                item.product_id.type != "consu" or not item.product_id.is_storable
            ):
                raise ValidationError(
                    _(
                        "We do not support syncing services or combo products to TikTok Shop. "
                        "Only storable products are supported."
                    )
                )

    @api.depends("product_id")
    def _compute_sync_to_tiktok(self):
        for item in self:
            item.sync_to_tiktok = item.product_id.type == "consu" and item.product_id.is_storable

    # === BUSINESS METHODS === #

    def _sync_inventory(self, auto_commit=True):
        valid_items = self.filtered("sync_to_tiktok").sorted("last_inventory_sync_date")

        for shop, shop_items in valid_items.grouped("shop_id").items():
            error_messages = []

            # We group variant by tiktok_item_extern_id (TikTok product template) to optimize
            # the inventory update. So only one inventory update is needed for all variants
            # in the same TikTok product template.
            if auto_commit:
                self.env["ir.cron"]._commit_progress(0, remaining=len(shop_items))
            for tiktok_item_extern_id, items in shop_items.grouped("tiktok_item_extern_id").items():
                try:
                    self._update_inventory(
                        shop, tiktok_item_extern_id, items, auto_commit=auto_commit
                    )
                except utils.TikTokApiError as error:
                    error_messages.append({
                        "default_codes": items.mapped("product_id.default_code"),
                        "message": str(error),
                    })
            if error_messages:
                shop._handle_sync_failure(flow="inventory_sync", error_messages=error_messages)

    def _update_inventory(self, shop, tiktok_item_extern_id, grouped_items, auto_commit=True):
        """Update the inventory for the given items.

        :param tiktok.shop shop: The shop to update the inventory.
        :param str tiktok_item_extern_id: The TikTok Shop Item External ID.
        :param tiktok.item grouped_items: The grouped items to update the inventory for.
        :param bool auto_commit: Whether to commit the transaction after updating the inventory.
        :return: None
        """
        skus_payload = []
        skus_to_skip = grouped_items.filtered(lambda i: not i.tiktok_sku_extern_id)
        if skus_to_skip:
            _logger.warning(
                "Missing SKU ID for products %(products)s, skipping inventory update.",
                {"products": skus_to_skip.mapped("product_id.display_name")},
            )

        items_to_update = grouped_items - skus_to_skip
        skus_payload.extend(
            item._prepare_sync_inventory_payload(shop, item.tiktok_sku_extern_id)
            for item in items_to_update
        )

        if skus_payload:
            utils.make_tiktok_api_request(
                shop,
                "update_inventory",
                params={"shop_cipher": shop.tiktok_cipher},
                path_params={"tiktok_item_extern_id": tiktok_item_extern_id},
                body={"skus": skus_payload},
            )
            items_to_update.last_inventory_sync_date = fields.Datetime.now()
            if auto_commit:
                self.env["ir.cron"]._commit_progress(len(items_to_update))

    def _prepare_sync_inventory_payload(self, shop, sku_extern_id):
        """Return the inventory update payload for this item and shop.

        :param tiktok.shop shop: The shop to update the inventory.
        :param str sku_extern_id: SKU external ID for this product.

        :return: The payload value for updating inventory.
        :rtype: dict
        """
        self.ensure_one()
        warehouse_id = shop.fbs_warehouse_id.id
        fbs_item = self.with_context(warehouse_id=warehouse_id).with_company(shop.company_id)
        fbs_qty = fbs_item.product_id.free_qty
        fbs_qty = max(fbs_qty, 0)
        return {"id": sku_extern_id, "inventory": [{"quantity": int(fbs_qty)}]}
