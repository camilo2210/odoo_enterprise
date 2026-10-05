from odoo import fields, models


class VoipCallLeg(models.Model):
    _name = "voip.call.leg"
    _description = "Phone Call Leg"

    conversation_id = fields.Many2one(
        comodel_name="voip.conversation", readonly=True, index=True, ondelete="cascade",
        help="Conversation this leg belongs to (grouped by PBX conversation_id).")
    voip_call_id = fields.Many2one(
        comodel_name="voip.call", readonly=True, index="btree_not_null", ondelete="set null",
        help="User-facing call this leg folds into; empty for routing legs and for the "
             "external source leg of an incoming call.")
    pbx_call_id = fields.Char(
        readonly=True,
        help="PBX call id of this leg's channel (Wazo call_id / Asterisk uniqueid).")
    sip_call_id = fields.Char(
        readonly=True,
        help="SIP Call-ID header of this leg's INVITE.")
    role = fields.Selection(
        [
            ("source", "Source"),
            ("participant", "Participant"),
            ("routing", "Routing"),
        ],
        readonly=True,
        help="Resolved role of this leg's endpoint within the conversation: the source "
             "opened it (the external caller on an incoming call, the user's own leg on an "
             "outgoing one), a participant was reached by it, a routing leg only relayed it.",
    )
    answered_at = fields.Datetime(readonly=True)
    ended_at = fields.Datetime(readonly=True)

    _pbx_call_id_unique_per_conversation = models.UniqueIndex(
        "(conversation_id, pbx_call_id)",
        message="A PBX call id is unique within its conversation.")
    _sip_call_id_unique = models.UniqueIndex(
        "(sip_call_id) WHERE sip_call_id IS NOT NULL",
        message="A SIP Call-ID identifies a single leg.")
