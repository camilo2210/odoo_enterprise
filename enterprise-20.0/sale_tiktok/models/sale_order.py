# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    tiktok_order_ref = fields.Char(
        string="TikTok Reference",
        help="The TikTok Shop-defined order reference.",
        readonly=True,
        copy=False,
    )
    tiktok_packing_ref = fields.Char(
        string="TikTok Packing Reference",
        help="The TikTok Shop-defined packing reference.",
        readonly=True,
        copy=False,
    )
    tiktok_shop_id = fields.Many2one(
        string="TikTok Shop",
        help="The TikTok shop from which the order was placed.",
        comodel_name="tiktok.shop",
        readonly=True,
        copy=False,
        index="btree_not_null",
    )
    tiktok_delivery_status = fields.Selection(
        string="TikTok Status",
        help="Status of the delivery order on TikTok Shop:\n"
        "- Awaiting Shipment: The order is ready for shipment, but nothing is shipped yet.\n"
        "- Awaiting Collection: The shipment is arranged and awaits carrier pickup.\n"
        "- Delivered: The package has been collected by the carrier and is shipped.\n"
        "- Canceled: The package has been cancelled.\n"
        "- Manual handling required: Shipment must be rearranged and checked again in TikTok Shop.",
        selection=[
            ("draft", "Awaiting Shipment on TikTok Shop"),
            ("confirmed", "Awaiting Collection on TikTok Shop"),
            ("done", "Delivered on TikTok Shop"),
            ("canceled", "Canceled on TikTok Shop"),
            ("manual", "Manual handling required"),
        ],
        copy=False,
        readonly=True,
    )

    _unique_tiktok_order_ref_tiktok_shop_id = models.Constraint(
        "UNIQUE(tiktok_shop_id, tiktok_order_ref)",
        "There can only exist one sale order for a given TikTok Shop Order Reference per Shop.",
    )
