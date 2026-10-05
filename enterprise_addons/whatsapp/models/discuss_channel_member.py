# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import api, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class DiscussChannelMember(models.Model):
    _inherit = 'discuss.channel.member'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_whatsapp_channel_owner(self):
        if self.env.su:
            return
        whatsapp_members = self.filtered(
            lambda m: m.is_self and m.channel_id.channel_type == "whatsapp",
        )
        for channel, channel_members in whatsapp_members.grouped("channel_id").items():
            owner_member = next(
                (member for member in channel.channel_member_ids if not member.partner_id.partner_share),
                self.browse(),
            )
            if owner_member in channel_members:
                raise UserError(self.env._(
                    "You can't leave this channel. As you are the owner of this WhatsApp channel, you can only delete it.",
                ))

    @api.autovacuum
    def _gc_unpin_whatsapp_channels(self):
        """ Unpin read whatsapp channels with no activity for at least one day to
            clean the operator's interface. """
        one_day_ago = datetime.now() - timedelta(days=1)
        five_days_ago = datetime.now() - timedelta(days=5)
        members = self.env['discuss.channel.member'].search(Domain.AND([
            [("is_pinned", "=", True)],
            [("channel_id.channel_type", "=", "whatsapp")],
            Domain.OR([
                [("last_seen_dt", "<", one_day_ago)],
                [
                    ("last_seen_dt", "=", False),
                    ("channel_id.create_date", "<=", five_days_ago),
                ],
            ]),
        ]), limit=1000)
        members_to_be_unpinned = members.filtered(
            lambda m: m.message_unread_counter == 0 or (not m.last_seen_dt and m.channel_id.create_date <= five_days_ago) or m.last_seen_dt <= five_days_ago
        )
        members_to_be_unpinned.unpin_dt = datetime.now()
        for member, store in members_to_be_unpinned._get_member_store_list():
            store.add(member.channel_id, {"close_chat_window": True})
