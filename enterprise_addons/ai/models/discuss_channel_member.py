# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class DiscussChannelMember(models.Model):
    _inherit = "discuss.channel.member"

    def _get_recording_permissions(self, user, sfu_url=True):
        permissions = super()._get_recording_permissions(user, sfu_url)
        permissions["transcription"] = permissions["audioRecording"]
        return permissions
