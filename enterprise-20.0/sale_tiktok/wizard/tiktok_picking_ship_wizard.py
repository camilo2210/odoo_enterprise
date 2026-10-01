# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.sale_tiktok import utils


class TikTokPickingShipWizard(models.TransientModel):
    _name = "tiktok.picking.ship.wizard"
    _description = "TikTok Picking Ship Wizard"

    picking_id = fields.Many2one(comodel_name="stock.picking", required=True)
    pickup_start = fields.Datetime(string="Pickup Start Time")
    pickup_end = fields.Datetime(string="Pickup End Time")

    def action_ship_order(self):
        """Ship the order with selected options."""
        self.ensure_one()

        if self.pickup_start and self.pickup_end and self.pickup_start >= self.pickup_end:
            raise UserError(_("Pickup End Time must be after Pickup Start Time."))
        if bool(self.pickup_start) ^ bool(self.pickup_end):
            raise UserError(_("Please provide both Pickup Start and Pickup End times."))

        payload = {}
        if self.pickup_start and self.pickup_end:
            payload["pickup_slot"] = {
                "start_time": int(fields.Datetime.to_datetime(self.pickup_start).timestamp()),
                "end_time": int(fields.Datetime.to_datetime(self.pickup_end).timestamp()),
            }
        try:
            self.picking_id._ship_tiktok_order(payload)
        except utils.TikTokRateLimitError as exc:
            raise UserError(_("Rate limit reached. Please try again later.")) from exc

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Ship Orders Result"),
                "message": _("Successfully shipped orders."),
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
