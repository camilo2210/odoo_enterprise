from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.exceptions import ConcurrencyError


class VoipConversation(models.Model):
    _name = "voip.conversation"
    _description = "Phone Conversation"

    call_ids = fields.One2many(comodel_name="voip.call", inverse_name="conversation_id", readonly=True)
    leg_ids = fields.One2many(comodel_name="voip.call.leg", inverse_name="conversation_id", readonly=True)
    conversation_identifier = fields.Char(
        readonly=True,
        help="PBX conversation id grouping the call's SIP legs (Wazo conversation_id).",
    )

    _check_conversation_identifier = models.UniqueIndex(
        "(conversation_identifier)",
        message="Conversation ID must be unique if set."
    )

    @api.model
    def _get_or_create(self, conversation_identifier):
        """Return the conversation the PBX names, creating it if it is new.

        Both the browser INVITE and the webhook legs reach a conversation by its
        PBX identifier, in either order and in parallel transactions, so the
        loser of an insert race raises ``ConcurrencyError`` and its event is
        retried, by which time the row is visible.
        """
        if not conversation_identifier:
            return self.browse()
        conversation = self.sudo().search(
            [("conversation_identifier", "=", conversation_identifier)], limit=1)
        if conversation:
            return conversation
        try:
            return self.sudo().create({"conversation_identifier": conversation_identifier})
        except UniqueViolation as e:
            raise ConcurrencyError() from e
