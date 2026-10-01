from odoo import api, fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"
    _name = "voip.call"

    commercial_partner_subscription_count = fields.Integer(
        related="partner_id.commercial_partner_subscription_count",
        groups="sales_team.group_sale_salesman",
        related_sudo=False,
    )
    is_related_activity_document_subscription = fields.Boolean(compute="_compute_is_related_activity_document_subscription", compute_sudo=True)

    @api.depends("activity_res_id", "activity_res_model")
    def _compute_is_related_activity_document_subscription(self):
        self.is_related_activity_document_subscription = False
        sale_calls = self.filtered(lambda c: c.activity_res_model == "sale.order")
        if not sale_calls:
            return
        so_ids = sale_calls.mapped("activity_res_id")
        sale_orders = self.env["sale.order"].browse(so_ids)
        so_by_id = {so.id: so.is_subscription for so in sale_orders}
        for call in sale_calls:
            call.is_related_activity_document_subscription = so_by_id.get(call.activity_res_id, False)

    def action_open_subscription(self):
        self.ensure_one()
        action = self.partner_id.commercial_partner_id.action_voip_view_subscription()
        action["context"]["default_partner_id"] = self.partner_id.id
        action["context"]["search_default_partner_id"] = [self.partner_id.id, self.partner_id.commercial_partner_id.id]
        return action
