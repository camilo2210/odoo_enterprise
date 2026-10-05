from odoo import models
from odoo.fields import Domain


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()

        products = self.order_line.product_id
        if products:
            CampaignSu = self.env["marketing.campaign"].sudo()
            impacted_campaigns = CampaignSu.search(
                CampaignSu._get_campaign_cron_alive_domain() &
                Domain([
                    ("enroll_action_type", "=", "product_bought"),
                    ("enroll_type", "=", "action"),
                    ("product_ids", "any", [("id", "in", products.ids)]),
                ])
            )
            for order in self.filtered(lambda so: not so.partner_id.is_public):
                impacted_campaigns.filtered(
                    lambda c: order.order_line.product_id & c.product_ids
                )._add_participants_manually_from_partners(order.partner_id.ids)

        return res

    def _create_new_cart_line(self, product_id, quantity, *args, **kwargs):
        line = super()._create_new_cart_line(product_id, quantity, *args, **kwargs)
        if not line.product_id or self.partner_id.is_public:
            return line

        CampaignSu = self.env["marketing.campaign"].sudo()
        impacted_campaigns = CampaignSu.search(
            CampaignSu._get_campaign_cron_alive_domain() &
            Domain([
                ("enroll_action_type", "=", "product_cart"),
                ("enroll_type", "=", "action"),
                ("product_ids", "any", [("id", "=", product_id)]),
            ])
        )
        if impacted_campaigns:
            impacted_campaigns._add_participants_manually_from_partners(self.partner_id.ids)

        return line
