# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAIAgent(TransactionCase):
    def test_agent_model_access(self):
        """AI Agentic allows metadata reads and base automation management."""
        ai_tool = self.env['ai.tool']

        for model_name in ('ir.model', 'ir.model.fields', 'ir.model.fields.selection'):
            ai_tool._check_agent_model_access(model_name)
            self.assertEqual(ai_tool._parse_domain(model_name, '[]'), [])
            with self.assertRaisesRegex(ValueError, f"{model_name} cannot be used by AI Agents"):
                ai_tool._parse_domain(model_name, '[]', operation='write')

        ai_tool._check_agent_model_access('base.automation')
        # automations are written through the dedicated tool only
        with self.assertRaisesRegex(ValueError, "base.automation cannot be used by AI Agents"):
            ai_tool._check_agent_model_access('base.automation', operation='write')
        with self.assertRaisesRegex(ValueError, "ir.config_parameter cannot be used by AI Agents"):
            ai_tool._check_agent_model_access('ir.config_parameter')

    def _channel_from_result(self, result):
        active_id = result["context"]["active_id"]
        channel_id = int(active_id.split("_")[-1])
        return self.env["discuss.channel"].browse(channel_id)

    def test_open_agent_chat_reuses_empty_agent_session(self):
        """Opening an agent chat should reuse only empty sessions without composer."""
        agent = self.env["ai.agent"].create({
            "name": "Test Agent",
        })
        first_result = agent.open_agent_chat()
        self.assertEqual(first_result["tag"], "mail.action_discuss")
        self.assertEqual(first_result["id"], self.env.ref("mail.action_discuss").id)
        self.assertEqual(first_result["path"], "discuss")
        self.assertEqual(first_result["target"], "current")
        self.assertEqual(first_result["context"]["scoped_ai_agent_id"], agent.id)
        self.assertNotIn("scoped_ai_agent_name", first_result["context"])
        first_channel = self._channel_from_result(first_result)
        second_channel = self._channel_from_result(agent.open_agent_chat())

        self.assertEqual(first_channel, second_channel, "Opening an agent chat should reuse the latest empty agent chat.")
        self.assertEqual(len(first_channel.sudo().ai_session_ids), 1)

        first_channel.message_post(body="Hello", message_type="comment")
        third_channel = self._channel_from_result(agent.open_agent_chat())

        self.assertNotEqual(first_channel, third_channel, "Opening an agent chat should create a new channel after a message.")
        self.assertEqual(len(third_channel.sudo().ai_session_ids), 1)

        composer = self.env["ai.composer"].create({
            "name": "Test Composer",
            "interface_key": "systray_ai_button",
            "ai_agent_id": agent.id,
            "focused_model_id": self.env["ir.model"]._get("res.partner").id,
        })
        composer_channel = agent._create_ai_chat_channel("Composer Chat")
        self.env["ai.session"].sudo().create({
            "agent_id": agent.id,
            "ai_composer_id": composer.id,
            "channel_id": composer_channel.id,
        })

        fourth_channel = self._channel_from_result(agent.open_agent_chat())

        self.assertNotEqual(composer_channel, fourth_channel, "Opening an agent chat should not reuse composer chats.")
