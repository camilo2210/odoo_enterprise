# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class TestImLivechatChannel(TransactionCase):
    def test_is_livechat_available(self):
        ai_agent = self.env['ai.agent'].create({
            'name': 'Test AI Agent',
        })

        channel_1 = self.env['im_livechat.channel'].create({
            'name': 'Test Channel 1',
        })
        self.assertEqual(channel_1.ai_agent_count, 0)
        self.assertEqual(channel_1._is_livechat_available(), False)

        self.env['im_livechat.channel.rule'].create({
            'channel_id': channel_1.id,
            'ai_agent_id': ai_agent.id,
        })
        self.assertEqual(channel_1.ai_agent_count, 1)
        self.assertEqual(channel_1._is_livechat_available(), True)
