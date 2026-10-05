# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from odoo.addons.sale_lazada import utils


class SaleOrder(models.Model):
    _inherit = "sale.order"

    lazada_order_ref = fields.Char(
        string="Lazada Reference",
        help="The Lazada-defined order reference.",
        readonly=True,
        copy=False,
    )
    lazada_shop_id = fields.Many2one(
        string="Lazada Shop",
        help="The Lazada shop from which the order was placed.",
        comodel_name="lazada.shop",
        copy=False,
        index="btree_not_null",
    )
    lazada_order_status = fields.Selection(
        string="Lazada Status",
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("processing", "Processing"),
            ("delivered", "Delivered"),
            ("canceled", "Canceled"),
            ("manual", "Manual"),
        ],
        compute="_compute_lazada_order_status",
    )
    lazada_fulfillment_type = fields.Selection(
        string="Lazada Fulfillment Type",
        selection=[("fbm", "Fulfillment by Merchant"), ("fbl", "Fulfillment by Lazada")],
        copy=False,
    )

    _unique_lazada_order_ref_lazada_shop_id = models.Constraint(
        "UNIQUE(lazada_order_ref, lazada_shop_id)",
        "There can only exist one sale order for a given Lazada Order Reference per Shop.",
    )

    @api.depends("picking_ids.lazada_package_status")
    def _compute_lazada_order_status(self):
        """Compute delivery status from Lazada order item statuses."""
        for order in self:
            package_statuses = order.picking_ids.mapped("lazada_package_status")
            order.lazada_order_status = utils.get_lazada_aggregated_status(package_statuses)
