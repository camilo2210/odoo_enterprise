from odoo import models


class MarketingCampaign(models.Model):
    _inherit = "marketing.campaign"

    def action_create_step(self, step_type):
        if step_type == "coupon":
            return self.env["ir.actions.act_window"]._for_xml_id(
                "marketing_automation_loyalty.marketing_activity_open_coupon_form_view"
            )
        return super().action_create_step(step_type)
