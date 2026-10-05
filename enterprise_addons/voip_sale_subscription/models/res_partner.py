from odoo import fields, models
from odoo.exceptions import AccessError

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    commercial_partner_subscription_count = fields.Integer(
        related="commercial_partner_id.subscription_count",
        string="Commercial Partner Subscription Count",
        groups="sales_team.group_sale_salesman",
        related_sudo=False,
    )

    def action_voip_view_subscription(self):
        self.ensure_one()
        return self.commercial_partner_id.open_related_subscription()

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)

        def can_read_subscription_count(partner):
            try:
                partner.read(["commercial_partner_subscription_count"])
            except AccessError:
                return False
            return True

        res.attr("commercial_partner_subscription_count", predicate=can_read_subscription_count)
