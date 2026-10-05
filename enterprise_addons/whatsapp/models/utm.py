# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class UtmMixin(models.AbstractModel):
    _inherit = "utm.mixin"

    @property
    def SELF_REQUIRED_UTM_REF(self):
        return super().SELF_REQUIRED_UTM_REF | {
            "whatsapp.utm_source_whatsapp": ("WhatsApp", "utm.source"),
        }
