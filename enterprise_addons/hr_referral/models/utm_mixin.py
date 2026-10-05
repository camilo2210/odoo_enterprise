# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class UtmMixin(models.AbstractModel):
    _inherit = 'utm.mixin'

    @property
    def SELF_REQUIRED_UTM_REF(self):
        return super().SELF_REQUIRED_UTM_REF | {
            'hr_referral.utm_source_referral_link_facebook': ('Referral Link Facebook', 'utm.source'),
            'hr_referral.utm_source_referral_link_twitter': ('Referral Link X', 'utm.source'),
            'hr_referral.utm_source_referral_link_linkedin': ('Referral Link LinkedIn', 'utm.source'),
        }
