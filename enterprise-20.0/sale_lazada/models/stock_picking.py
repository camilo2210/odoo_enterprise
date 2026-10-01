# Part of Odoo. See LICENSE file for full copyright and licensing details.

from urllib.parse import urlparse

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import split_every

from odoo.addons.sale_lazada import const, utils


class StockPicking(models.Model):
    _inherit = "stock.picking"

    lazada_order_ref = fields.Char(related="sale_id.lazada_order_ref")

    # Computed fields for Lazada package management
    lazada_package_status = fields.Selection(
        selection=[
            ("draft", "Package Pending on Lazada"),
            ("confirmed", "Package Confirmed on Lazada"),
            ("processing", "Ready to Ship on Lazada"),
            ("delivered", "Delivered on Lazada"),
            ("canceled", "Canceled on Lazada"),
            ("manual", "Manual handling required"),
        ],
        compute="_compute_lazada_package_status",
    )

    # Lazada-specific fields
    last_lazada_picking_sync_date = fields.Datetime(
        help="The last time the picking was synchronized with Lazada.",
        readonly=True,
        default=fields.Datetime.now,
    )
    package_extern_id = fields.Char(
        string="Lazada Package ID", help="The package identifier for the picking.", readonly=True
    )
    lazada_shipping_allocate_type = fields.Char(
        string="Lazada Shipping Allocate Type",
        help="The shipping allocate type for the picking.",
        readonly=True,
    )
    lazada_label_attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="stock_picking_lazada_label_attachment_rel",
        help="The attachments that are related to the Lazada label.",
    )

    # === COMPUTED FIELDS === #

    @api.depends("move_ids.lazada_order_item_ids.status")
    def _compute_lazada_package_status(self):
        for picking in self:
            picking.lazada_package_status = utils.get_lazada_aggregated_status(
                picking.move_ids.lazada_order_item_ids.mapped("status")
            )

    # === BUSINESS METHODS === #

    def _pack_lazada_package(self):
        """Pack Lazada packages for eligible pickings.

        Packs order items with 'draft' status.
        """
        pickings_by_shop = self._get_lazada_pickings_by_shop()

        for all_pickings in pickings_by_shop.values():
            # Filter pickings that need packing
            to_pack_pickings = all_pickings.filtered(
                lambda p: (
                    p.move_ids.lazada_order_item_ids
                    and p.lazada_package_status == "draft"
                    and not p.package_extern_id
                )
            )
            picking_sorted = to_pack_pickings.sorted("last_lazada_picking_sync_date")
            for picking in picking_sorted:
                if not picking.lazada_shipping_allocate_type:
                    picking._get_shipment_provider()
                picking._pack_picking()

    def _fetch_lazada_shipping_label(self):
        """Fetch shipping labels and set Ready to Ship status.

        Downloads labels via PrintAWB API and updates status via SetReadyToShip API.
        """
        pickings_by_shop = self._get_lazada_pickings_by_shop()

        error_messages = []
        for shop, all_pickings in pickings_by_shop.items():
            # Download shipping labels
            to_download_pickings = all_pickings.filtered(
                lambda p: p.lazada_package_status not in ["canceled", "draft"]
            )
            for picking in to_download_pickings:
                try:
                    picking._download_lazada_shipping_label(shop)
                except utils.LazadaApiError as error:
                    error_messages.append({"picking_ids": picking.id, "message": str(error)})
                    continue

            # Set Ready to Ship status
            to_update_rts_pickings = all_pickings.filtered(
                lambda p: p.lazada_package_status == "processing" and p.lazada_label_attachment_ids
            )

            for picking_batch in split_every(
                const.SET_RTS_SIZE_LIMIT, to_update_rts_pickings.ids, self.browse
            ):
                try:
                    picking_batch._set_lazada_rts(shop)
                except utils.LazadaApiError as error:
                    error_messages.append({"picking_ids": picking_batch.ids, "message": str(error)})
                    continue
        if error_messages:
            formatted_errors = "\n".join(
                f"- {err['picking_ids']}: {err['message']}" for err in error_messages
            )
            raise UserError(
                self.env._(
                    "Failed to set Ready to Ship status for pickings:\n%(error_msg)s",
                    error_msg=formatted_errors,
                )
            )

    # === LAZADA API METHODS === #

    def _fetch_shipment_provider(self, order_id, order_item_ids):
        """Fetch shipment provider information from Lazada API.

        :param int order_id: Order identifier
        :param list order_item_ids: List of order item IDs
        :return: Shipment provider data
        :rtype: dict
        """
        shop = self.sale_id.lazada_shop_id
        shop.ensure_one()
        response = utils.make_lazada_api_request(
            "GetShipmentProvider",
            shop,
            params={
                "getShipmentProvidersReq": str({
                    "orders": [{"order_id": order_id, "order_item_ids": order_item_ids}]
                })
            },
        )
        if response["result"]["success"]:
            return response["result"]["data"]
        raise UserError(
            self.env._(
                "Failed to get shipment provider for order: %(order_id)s. Error: %(error_msg)s",
                order_id=order_id,
                error_msg=response["error_msg"],
            )
        )

    def _set_lazada_rts(self, shop):
        """Set Ready to Ship status on Lazada for pickings.

        :param shop: Lazada shop record
        """
        for pickings in split_every(const.SET_RTS_SIZE_LIMIT, self.ids, self.browse):
            payload = pickings._prepare_lazada_rts_payload()
            payload = {"readyToShipReq": str(payload)}
            content = utils.make_lazada_api_request(
                "SetReadyToShip", shop, params=payload, method="POST"
            )

            if not content.get("result", {}).get("success"):
                raise utils.LazadaApiError(
                    shop,
                    "SetReadyToShip",
                    content.get("request_id"),
                    content.get("result", {}).get("error_code"),
                    content.get("result", {}).get("error_msg"),
                )

            pickings.lazada_package_status = "processing"

    def _download_lazada_shipping_label(self, shop):
        """Download shipping label PDF and attach to picking.

        :param shop: Lazada shop record
        """
        for picking in self:
            payload = picking._prepare_lazada_shipping_label_payload()
            content = utils.make_lazada_api_request(
                "PrintAWB", shop, params={"getDocumentReq": str(payload)}, method="POST"
            )

            if not content.get("result", {}).get("success"):
                raise utils.LazadaApiError(
                    shop,
                    "PrintAWB",
                    content.get("request_id"),
                    content.get("result", {}).get("error_code"),
                    content.get("result", {}).get("error_msg"),
                )
            attachment_name = f"Lazada_Label_{picking.carrier_tracking_ref}.pdf"

            pdf_url = content["result"]["data"]["pdf_url"]
            parsed = urlparse(pdf_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or not any(
                    parsed.hostname.endswith(domain) for domain in const.ALLOWED_LAZADA_DOC_HOSTS
                )
            ):
                raise UserError(self.env._("Invalid Lazada document URL"))
            response = requests.get(pdf_url, timeout=10, allow_redirects=False)

            if response.status_code != 200:
                raise UserError(
                    self.env._(
                        "Failed to download shipping label for picking %(picking_id)s: "
                        "HTTP Status Code %(error_code)s",
                        picking_id=picking.id,
                        error_msg=str(response.status_code),
                    )
                )

            message = picking.message_post(
                subject=self.env._("Lazada Label"),
                attachments=[(attachment_name, response.content)],
            )
            picking.lazada_label_attachment_ids += message.attachment_ids

            picking.move_ids.lazada_order_item_ids.status = "processing"

    def _pack_picking(self):
        """Pack products on Lazada via PackagePack API."""
        self.ensure_one()
        try:
            payload = self._prepare_package_payload()
            shop = self.sale_id.lazada_shop_id
            date_now = fields.Datetime.now()
            content = utils.make_lazada_api_request(
                "PackagePack", shop, params={"packReq": str(payload)}, method="POST"
            )

            if not content.get("result", {}).get("success"):
                raise utils.LazadaApiError(
                    shop,
                    "PackagePack",
                    content.get("request_id"),
                    content.get("result", {}).get("error_code"),
                    content.get("result", {}).get("error_msg"),
                )

            for package_data in content["result"]["data"]["pack_order_list"]:
                error_items = []
                valid_items = []
                for item in package_data["order_item_list"]:
                    if int(item.get("item_err_code")):
                        error_items.append(item)
                    else:
                        valid_items.append(item)
                if error_items:
                    error_msg = "\n".join([
                        f"Item #{item['order_item_id']} - {item['msg']}" for item in error_items
                    ])
                    raise utils.LazadaApiError(
                        shop,
                        "PackagePack",
                        content.get("request_id"),
                        content.get("result", {}).get("error_code", "N/A"),
                        error_msg,
                    )
                package_extern_id = next(iter({item["package_id"] for item in valid_items}))
                tracking_number = next(iter({item["tracking_number"] for item in valid_items}))
                self.package_extern_id = package_extern_id
                self.carrier_tracking_ref = tracking_number
                self.last_lazada_picking_sync_date = date_now

                # Capture order_item_extern_ids in lambda default parameter to avoid closure issue
                order_item_extern_ids = {str(item["order_item_id"]) for item in valid_items}
                self.move_ids.lazada_order_item_ids.filtered(
                    lambda i, ids=order_item_extern_ids: i.order_item_extern_id in ids
                ).write({"status": "confirmed"})
        except utils.LazadaRateLimitError as e:
            raise UserError(
                self.env._("Lazada API rate limit reached. Please try again later.")
            ) from e

    def _get_shipment_provider(self):
        """Fetch shipment provider and allocate type from Lazada API.

        Determines shipping_allocate_type (NTFS/TFS) for the picking.
        """
        self.ensure_one()
        if not self.lazada_order_ref:
            raise UserError(
                self.env._("The Lazada order reference is required to get the shipment provider.")
            )
        draft_items = self.move_ids.lazada_order_item_ids.filtered(lambda i: i.status == "draft")
        order_id = int(self.lazada_order_ref)
        order_item_ids = list(map(int, draft_items.mapped("order_item_extern_id")))
        data = self._fetch_shipment_provider(order_id, order_item_ids)
        if not data.get("shipping_allocate_type"):
            raise UserError(self.env._("Failed to get shipment provider."))

        self.lazada_shipping_allocate_type = data["shipping_allocate_type"]
        return True

    # === HELPER METHODS === #

    def _get_lazada_pickings_by_shop(self):
        """Group pickings by Lazada shop.

        :return: Dict mapping shop to pickings
        :rtype: dict
        """
        domain = [
            ("id", "in", self.ids),
            ("sale_id.lazada_shop_id", "!=", False),
            ("lazada_order_ref", "!=", False),
            ("state", "not in", ["done", "cancel"]),
        ]
        return self.search(domain).grouped(lambda p: p.sale_id.lazada_shop_id)

    def _prepare_package_payload(self):
        """Prepare payload for PackagePack API request.

        :return: Package payload dict
        :rtype: dict
        """
        self.ensure_one()
        if not self.lazada_order_ref:
            raise ValidationError(self.env._("No Lazada order reference found."))

        result = {
            "shipping_allocate_type": self.lazada_shipping_allocate_type,
            "delivery_type": "dropship",  # Must be dropship
        }
        draft_order_item_extern_ids = self.move_ids.lazada_order_item_ids.filtered(
            lambda i: i.status == "draft"
        ).mapped("order_item_extern_id")
        if not draft_order_item_extern_ids:
            raise ValidationError(self.env._("No Lazada order item found to pack."))

        return {
            **result,
            "pack_order_list": [
                {"order_id": self.lazada_order_ref, "order_item_list": draft_order_item_extern_ids}
            ],
        }

    def _prepare_lazada_shipping_label_payload(self):
        """Prepare payload for PrintAWB API request.

        :return: Shipping label payload dict
        :rtype: dict
        """
        self.ensure_one()
        return {"packages": [{"package_id": self.package_extern_id}], "doc_type": "PDF"}

    def _prepare_lazada_rts_payload(self):
        """Prepare payload for SetReadyToShip API request.

        :return: RTS payload dict
        :rtype: dict
        """
        return {"packages": [{"package_id": picking.package_extern_id} for picking in self]}

    # === ACTION METHODS === #

    def action_fetch_shipping_label(self):
        """Manually fetch shipping label for this picking."""
        self._fetch_lazada_shipping_label()

    def action_pack_lazada_package(self):
        """Manually pack this Lazada package."""
        self._pack_lazada_package()
