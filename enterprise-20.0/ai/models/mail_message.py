# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

from ..utils.types import AIMessageParts


class MailMessage(models.Model):
    _inherit = "mail.message"

    def _convert_to_parts(self) -> AIMessageParts:
        self.ensure_one()
        message_parts: AIMessageParts = [{
            'type': 'text', 'text': self.body,
            'metadata': {'attachment_ids': self.attachment_ids.ids},
        }]
        if self.attachment_ids:
            message_parts.append({'type': 'text', 'text': f"Attachments (id, name): {[(a.id, a.name) for a in self.attachment_ids]}"})
        # sudo as public users can link attachments to their messages with agents
        message_parts.extend(self.attachment_ids.sudo()._ai_read()[1])
        return message_parts

    def _store_author_dynamic_fields(self, res):
        super()._store_author_dynamic_fields(res)
        if self.channel_id.channel_type == "ai_chat":
            # sudo: ai.agent - knowing if a partner is an AI agent is acceptable
            res.many("agent_ids", [], sudo=True)
