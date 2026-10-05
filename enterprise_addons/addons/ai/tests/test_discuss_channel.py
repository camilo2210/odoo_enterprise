# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged, HttpCase, users

from .common import TestAICommon


@tagged('-at_install', 'post_install')
class TestDiscussChannel(HttpCase, TestAICommon):

    def test_create_ai_chat(self):
        agent = self.env["ai.agent"].create({"name": "Odoo AI"})
        channel = agent._create_ai_chat_channel()

        self.assertTrue(channel)
        self.assertTrue(channel.is_member, "Current user should be member of the created channel")
        self.assertEqual("ai_chat", channel.channel_type, "AI channel should be of 'ai_chat' type")
        self.assertEqual(channel.name, "", "Channel name should originally be empty - will be filled in later")
        self.assertEqual(agent.partner_id.name, channel.display_name, "Channel's display_name should be the agent's name")
        self.assertEqual(agent, channel.sudo().ai_agent_id, "ai_agent_id should be set on the newly created ai_chat channel")

    @users('user_internal')
    def test_delete_ai_chat_only_deletes_channel_with_proper_types(self):
        # Sudo => creating an agent requires creating a 'res.partner' to be used for chat channels.
        # This is only allowed for admins
        agent = self.env["ai.agent"].sudo().create({"name": "Odoo AI"})
        ai_chat_channel = agent._create_ai_chat_channel()
        regular_channel = self.env["discuss.channel"].create({
            "channel_member_ids": [
                Command.create(
                    {
                        "partner_id": self.env.user.partner_id.id,
                    }
                ),
            ],
            "channel_type": "chat",
            "name": "Non AI chat"
        })

        with self.assertRaises(AccessError):
            regular_channel.unlink()
        self.assertTrue(regular_channel.exists(), "Only channels of type 'ai_chat' should be deleted on close.")

        ai_chat_channel.unlink()
        self.assertFalse(ai_chat_channel.exists(), "Channel of type 'ai_chat' should be deleted when closed.")

    @users('user_internal')
    def test_member_can_delete_own_ai_chat(self):
        """A non-admin user should be able to delete their own AI chat channel."""
        agent = self.env["ai.agent"].sudo().create({"name": "Odoo AI"})
        channel = agent._create_ai_chat_channel()

        self.assertIn(self.env.user.partner_id, channel.channel_member_ids.partner_id)
        channel.unlink()
        self.assertFalse(channel.exists(), "A member should be able to delete their own AI chat.")

    @users('user_internal')
    def test_non_member_cannot_delete_ai_chat(self):
        """User should only be able to delete their AI chat channels."""
        user_admin = self.env.ref('base.user_admin')
        agent = self.env['ai.agent'].sudo().create({'name': 'test agent'})
        channel = agent.with_user(user_admin)._create_ai_chat_channel('test AI chat')

        self.assertIn(user_admin.partner_id, channel.channel_member_ids.partner_id)
        self.assertNotIn(self.env.user.partner_id, channel.channel_member_ids.partner_id)
        with self.assertRaises(AccessError):
            channel.with_user(self.env.user).unlink()
        self.assertTrue(channel.exists(), "A non-member should not be able to delete an AI chat.")
