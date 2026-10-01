# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _prepare_lead_create_values(self, partner, key):
        values = super()._prepare_lead_create_values(partner, key)
        if self.channel_type == "whatsapp":
            values["source_id"] = self.env["utm.mixin"]._utm_ref("whatsapp.utm_source_whatsapp").id
            values["medium_id"] = self.env["utm.mixin"]._utm_ref("utm.utm_medium_messaging").id
            if self.wa_account_id:
                values["utm_reference"] = f"{self.wa_account_id._name},{self.wa_account_id.id}"
        return values
