from odoo import models


class PosConfig(models.Model):
    _inherit = "pos.config"

    def action_open_wizard(self):
        result = super().action_open_wizard()
        if result.get("type") != "ir.actions.act_url" or not self.env.context.get("open_in_mobile_kiosk"):
            return result
        return {
            "type": "ir.actions.client",
            "tag": "pos_self_order_mobile.open_kiosk",
            "params": {
                "kiosk_url": result["url"],
                "timezone": self.company_id.tz,
            },
        }
