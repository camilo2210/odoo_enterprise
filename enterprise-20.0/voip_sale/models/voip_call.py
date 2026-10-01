from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"
    _name = "voip.call"

    commercial_partner_sale_order_count = fields.Integer(
        related="partner_id.commercial_partner_sale_order_count",
        groups="sales_team.group_sale_salesman",
        related_sudo=False,
    )

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.partner_id.commercial_partner_id.action_voip_view_sale_orders()
        action["context"]["default_partner_id"] = self.partner_id.id
        return action
