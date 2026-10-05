# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _get_meta_fetch_messages_platform(self, media_type):
        if media_type == "instagram":
            return "instagram"
        return super()._get_meta_fetch_messages_platform(media_type)
