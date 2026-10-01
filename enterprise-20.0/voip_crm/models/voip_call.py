from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"
    _name = "voip.call"

    commercial_partner_opportunity_count = fields.Integer(
        related="partner_id.commercial_partner_opportunity_count",
        groups="sales_team.group_sale_salesman",
        related_sudo=False,
    )

    def action_view_opportunity(self):
        action = self.partner_id.commercial_partner_id.get_view_opportunities_action()
        action["context"]["default_partner_id"] = self.partner_id.id
        return action
