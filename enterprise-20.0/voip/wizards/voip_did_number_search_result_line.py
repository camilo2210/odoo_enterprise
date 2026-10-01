from odoo import api, fields, models

from odoo.addons.voip.models.voip_did_number import DID_NUMBER_TYPES


class VoipNumberSearchResultLine(models.TransientModel):
    _name = "voip.did.number.search.result.line"
    _description = "DID Number Search Result Line"

    wizard_id = fields.Many2one("voip.did.number.search.wizard", required=True, ondelete="cascade")
    country_id = fields.Many2one(related="wizard_id.country_id")
    selected = fields.Boolean(string="Select", default=False)
    phone_number = fields.Char(string="Number", required=True)
    location = fields.Char()
    did_number_type = fields.Selection(
        DID_NUMBER_TYPES,
        string="Type",
        help="Phone number type from phone_service (e.g., local, toll_free)",
    )
    monthly_cost = fields.Float(string="Monthly Cost")

    price_display = fields.Char(string="Price", compute="_compute_price_display", help="Formatted price display")

    @api.depends("monthly_cost")
    def _compute_price_display(self):
        wizard_model = self.env["voip.did.number.search.wizard"]
        for line in self:
            line.price_display = self.env._(
                "%(monthly_cost)s credits/month",
                monthly_cost=wizard_model._format_credits(line.monthly_cost),
            )
