# Part of Odoo. See LICENSE file for full copyright and licensing details.


import logging
from urllib.parse import urlsplit

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import split_every

from odoo.addons.sale_tiktok import const, utils

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    tiktok_order_ref = fields.Char(related="sale_id.tiktok_order_ref")
    tiktok_packing_ref = fields.Char(related="sale_id.tiktok_packing_ref")
    tiktok_delivery_status = fields.Selection(related="sale_id.tiktok_delivery_status")
    tiktok_label_attachment_id = fields.Many2one(
        comodel_name="ir.attachment", help="The attachment related to the TikTok shipping label."
    )

    # === ACTION METHODS === #

    def action_tiktok_sync_pickings(self):
        return self._sync_tiktok_pickings()

    def action_tiktok_ship_order(self):
        self.ensure_one()
        if not (
            self.tiktok_order_ref
            and self.tiktok_packing_ref
            and self.tiktok_delivery_status == "draft"
        ):
            raise UserError(_("The collection of this order was already scheduled."))

        wizard = self.env["tiktok.picking.ship.wizard"].create({"picking_id": self.id})
        return wizard._get_records_action(name=_("Ship TikTok Orders"), target="new")

    # === BUSINESS METHODS === #

    def _sync_tiktok_pickings(self):
        """Fetch tracking number and shipping label from TikTok Shop.

        Delivery information must be filled on TikTok Shop. Once TikTok assigns a tracking
        number to the pickings, this method fetches the number and the shipping label.

        :return: None
        """
        pickings_by_shop = self._get_tiktok_pickings_by_shop()
        for shop, shop_pickings in pickings_by_shop.items():
            try:
                if not shop.active:
                    continue
                shop_pickings._fetch_tiktok_shipping_label(shop)
            except utils.TikTokRateLimitError as error:
                _logger.info(
                    "Rate limit reached while synchronizing pickings for TikTok Shop with"
                    " id %(shop)s. Operation: %(error_operation)s",
                    {"shop": shop.id, "error_operation": error.operation},
                )
                continue

    def _get_tiktok_pickings_by_shop(self):
        """Group the pickings by their respective shops.

        :return: The pickings grouped by TikTok shop.
        :rtype: recordset of stock.picking
        """
        domain = [
            ("sale_id.tiktok_shop_id", "!=", False),
            ("tiktok_order_ref", "!=", False),
            ("state", "!=", "cancel"),
        ]
        pickings = self.filtered_domain(domain) if self else self.search(domain)
        return pickings.grouped(lambda p: p.sale_id.tiktok_shop_id)

    def _fetch_tiktok_shipping_label(self, shop):
        """Fetch tracking number and shipping label from TikTok Shop.

        Delivery information is first recorded on TikTok Shop, which assigns the tracking
        number. This helper fetches the number and creates the associated shipping label.

        :param record shop: The shop whose shipments are synchronized.
        :return: None
        """
        shop.ensure_one()
        error_messages = []

        picking_sorted = self.filtered(
            lambda p: (
                not p.tiktok_label_attachment_id
                and p.tiktok_delivery_status in ["draft", "confirmed"]
            )
        )

        batch_size = min(const.ORDER_DETAIL_SIZE_LIMIT, const.SHIPPING_DOCUMENT_SIZE_LIMIT)
        for picking_batch in split_every(batch_size, picking_sorted.ids, self.browse):
            # Update delivery status to keep the order status up-to-date
            try:
                orders = picking_batch.sale_id.mapped("tiktok_order_ref")
                picking_batch._update_tiktok_delivery_status(shop, orders)
            except utils.TikTokApiError as error:
                error_messages.append({
                    "picking_refs": ", ".join(picking_batch.mapped("name")),
                    "message": str(error),
                })
                continue

            picking_to_label = picking_batch.filtered(
                lambda p: (
                    p.tiktok_delivery_status == "confirmed" and not p.tiktok_label_attachment_id
                )
            )
            for picking in picking_to_label:
                try:
                    picking._download_tiktok_shipping_label(shop)
                except utils.TikTokApiError as error:
                    error_messages.append({"picking_refs": picking.name, "message": str(error)})
                    continue

        if error_messages:
            _logger.info(
                "Failed to fetch label for TikTok Shop with id %(shop)s. Error: %(message)s",
                {"shop": shop.id, "message": error_messages},
            )
            raise ValidationError(
                _("Failed to fetch label. Please wait and try again later. %s", error_messages)
            )

    def _download_tiktok_shipping_label(self, shop):
        """Fetch the shipping labels and tracking number.

        :param record shop: The TikTok shop of the pickings as a `tiktok.shop` record.
        :return: None
        """
        self.ensure_one()

        package_id = self.tiktok_packing_ref
        response = utils.make_tiktok_api_request(
            shop,
            "get_package_label",
            params={"document_type": "SHIPPING_LABEL", "shop_cipher": shop.tiktok_cipher},
            path_params={"package_id": package_id},
        )
        # Packages with no shipping label will return 'None'
        if not response:
            return

        self.carrier_tracking_ref = response.get("tracking_number")
        label_url = response.get("doc_url")
        if not (self.carrier_tracking_ref and label_url):
            return
        parsed_label_url = urlsplit(label_url)
        if (
            parsed_label_url.scheme != "https"
            or not parsed_label_url.hostname
            or not any(
                parsed_label_url.hostname.endswith(domain)
                for domain in const.ALLOWED_TIKTOK_DOC_HOSTS
            )
        ):
            raise UserError(self.env._("Invalid TikTok document URL"))

        try:
            label_response = requests.get(label_url, timeout=10, allow_redirects=False)
            label_response.raise_for_status()
            attachment_name = f"TikTok_Shop_Label_{self.carrier_tracking_ref}.pdf"

            message = self.message_post(
                subject=_("TikTok Shop Label"),
                body=_("TikTok Shop Label"),
                attachments=[(attachment_name, label_response.content)],
            )
            self.tiktok_label_attachment_id = message.attachment_ids[:1]
        except requests.exceptions.RequestException:
            self.message_post(
                subject=_("TikTok Shop Label"),
                body=_(
                    "Failed to download the shipping label. Use the provided link:\n%(link)s",
                    link=label_url,
                ),
            )

    def _ship_tiktok_order(self, time_period):
        self.ensure_one()
        if not self.tiktok_order_ref:
            raise UserError(_("This picking is not linked to a TikTok order."))

        shop = self.sale_id.tiktok_shop_id
        if not shop:
            raise UserError(_("No TikTok shop found for this order."))

        try:
            utils.make_tiktok_api_request(
                shop,
                "ship_package",
                params={"shop_cipher": shop.tiktok_cipher},
                path_params={"package_id": self.tiktok_packing_ref},
                body=time_period or {"pickup_slot": {}},
            )
            self.sale_id.tiktok_delivery_status = "confirmed"
        except utils.TikTokApiError as error:
            raise UserError(_("Failed to ship order: %s", error)) from error

    def _update_tiktok_delivery_status(self, shop, order_refs):
        """Update tiktok_delivery_status on associated orders based on TikTok order detail."""
        orders_detail = shop._fetch_orders_detail(order_refs)
        order_by_tiktok_ref = self.sale_id.grouped("tiktok_order_ref")
        for order_detail in orders_detail:
            new_delivery_status = const.DELIVERY_STATUS_MAPPING.get(
                order_detail["status"], "manual"
            )
            order = order_by_tiktok_ref.get(order_detail["id"])
            if order and order.tiktok_delivery_status != new_delivery_status:
                order.tiktok_delivery_status = new_delivery_status
