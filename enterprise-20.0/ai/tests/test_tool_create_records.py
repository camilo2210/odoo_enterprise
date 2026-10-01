# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from markupsafe import Markup

from odoo.sql_db import _logger as sql_logger
from odoo.tests import users
from odoo.tools.mail import html_sanitize, html_to_inner_content
from odoo.tools.misc import format_datetime

from odoo.addons.ai.models.ai_session import _logger as tool_logger
from odoo.addons.ai.tests.common import TestAICallbackCommon
from odoo.addons.ai.utils.ai_utils import (
    make_create_preview,
    make_record_create_preview,
)


class TestAIToolCreateRecords(TestAICallbackCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_tool = cls.env.ref("ai.ir_actions_server_create_records")
        cls.create_records_skill = cls.env["ai.skill"].create(
            {
                "name": "Create records Skill",
                "instructions": "Skill instructions",
                "tool_ids": cls.create_tool.ids,
            },
        )
        cls.agent.sudo().write(
            {
                "skill_ids": cls.agent.skill_ids | cls.create_records_skill,
            },
        )

    def test_create_records(self):
        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.create_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(
                self.create_tool,
                {
                    "explanation": "Creating new AI agent named Jimmy",
                    "model_name": "ai.agent",
                    "values": [
                        {
                            "field_values": [
                                {
                                    "field": "name",
                                    "value": "Jimmy",
                                },
                            ],
                        },
                    ],
                },
            ),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Create an agent named 'Jimmy'")

        self.assertEqual(
            session.pending_tool_call['call_id'],
            2,
            "Creation tool should be pending on first call.",
        )

        self.assertIn(
            "Name: Jimmy",
            html_to_inner_content(session.pending_tool_call['user_input_request']['body']),
        )

        self.assertFalse(self.env["ai.agent"].search([("name", "=", "Jimmy")]), "Agent should not exist if tool hasn't been confirmed.")

        # Tool confirmation
        with self.mock_callback_completions([self.mock_text_response("Agent Jimmy created")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call, "Creation tool call should be confirmed")

        self.assertTrue(self.env["ai.agent"].search([("name", "=", "Jimmy")]), "Agent should exist after tool confirmation")

    def test_create_preview_single_record(self):
        create_values = {
            "author_id": self.env.user.partner_id.id,  # many2one
            "message_type": "email",  # selection
            "is_internal": True,  # bool
            "email_from": "from@example.com",  # char
            "incoming_email_to": "incoming@example.com",  # text
            "body": "<p>Hi</p>",  # html
            "pinned_at": "2025-01-15 12:34:56",  # datetime
        }
        message = self.env["mail.message"].create(create_values)
        preview = make_record_create_preview(message, create_values)

        self.assertEqual(
            preview[0],
            {"label": "Author", "value": self.env.user.partner_id.display_name},
        )
        self.assertEqual(preview[1], {"label": "Type", "value": "email"})
        self.assertEqual(preview[2], {"label": "Employee Only", "value": True})
        self.assertEqual(preview[3], {"label": "From", "value": "from@example.com"})
        self.assertEqual(
            preview[4],
            {"label": "Emails To", "value": "incoming@example.com"},
        )
        self.assertEqual(preview[5], {"label": "Contents", "value": "Hi"})
        self.assertEqual(
            preview[6],
            {
                "label": "Pinned",
                "value": format_datetime(self.env, "2025-01-15 12:34:56"),
            },
        )

    def test_create_preview_multiple_records(self):
        create_values = [
            {
                "field_values": [{"field": "body", "value": "<p>Hi</p>"}],
            },
            {
                "field_values": [
                    {
                        "field": "body",
                        "value": "<p>Hello</p>",
                    },
                ],
            },
        ]
        preview = make_create_preview(
            self.env,
            "Understood, I'll create the following messages.",
            "mail.message",
            create_values,
        )

        clean_whitespace_preview = re.sub(
            r"[\n\r\t]+",
            "",
            preview,
        )  # Removing all whitespaces from the preview
        clean_preview = re.sub(
            r" {2,}",
            "",
            clean_whitespace_preview,
        )  # Removing all multiple leftover spaces
        changes = re.findall(r"<li>(.*?)</li>", clean_preview)

        self.assertEqual(len(changes), 2)
        self.assertEqual(
            changes[0].strip(),
            '<b>Message 1:</b>Hi',
        )
        self.assertEqual(
            changes[1].strip(),
            '<b>Message 2:</b>Hello',
        )

    def test_create_preview_x2m_commands(self):
        child_message = self.env["mail.message"].create(
            {"subject": "Greetings", "body": "<p>Hey!</p>"},
        )
        create_values = [
            {
                "model_name": "mail.message",
                "field_values": [
                    {"field": "body", "value": "<p>Hi</p>"},
                    {"field": "child_ids", "x2m_link_ids": child_message.ids},
                ],
            },
        ]

        preview = make_create_preview(
            self.env,
            "Understood, I'll create the following messages.",
            "mail.message",
            create_values,
        )
        self.assertEqual(
            html_to_inner_content(preview),
            'Understood, I\'ll create the following messages. Contents: Hi Child Messages: Message 1: "Greetings" (existing)',
        )

    @users("user_internal")
    def test_create_records_tool_access(self):
        """Users should not be able to create records they cannot access through AI agents"""
        session_sudo = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.create_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session_sudo, "Load skill")

        mocked_responses = [
            self.mock_tool_response(
                self.create_tool,
                {
                    "explanation": "Creating an AI Agent called Jimmy",
                    "model_name": "ai.agent",
                    "values": [
                        {
                            "field_values": [
                                {
                                    "field": "name",
                                    "value": "Jimmy",
                                },
                            ],
                        },
                    ],
                },
            ),
            self.mock_text_response("Not allowed"),
        ]

        with (
            self.mock_callback_completions(mocked_responses),
            self.assertLogs(tool_logger, level="WARNING") as mock_tool_logger,
        ):
            self._post_user_message_on_session(session_sudo, "Change agent name")

        # error is logged, tool call should be shown as erroneous
        self.assertIn(
            "You are not allowed to create 'AI Agent' (ai.agent) records.",
            mock_tool_logger.records[0].msg,
        )
        self.assertFalse(session_sudo.pending_tool_call)
        tool_result = self._get_tool_result(session_sudo, 2)
        self.assertFalse(tool_result['success'])
        self.assertIn(
            "Error: Tool call failed: You are not allowed to create 'AI Agent' (ai.agent) records",
            tool_result['result'][0]['text'],
        )

        # message should be in session history and posted
        self.assertEqual(
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Not allowed"}],
                "provider_metadata": {},
            },
            session_sudo.event_ids.sorted('id')[-1].metadata,
        )
        self.assertIn("Not allowed", session_sudo.channel_id.message_ids[0].body)

    def test_create_records_accepted_posts_preview_link(self):
        """A preview message should be posted in the channel when a creation tool call is accepted"""

        action = self.env["ir.actions.act_window"].create({
            "res_model": "ai.agent"
        })

        menu = self.env["ir.ui.menu"].create({
            "name": "Test Agents",
            "action": f"{action._name},{action.id}",
        })

        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.create_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(
                self.create_tool,
                {
                    "explanation": "Creating new AI agent named Jimmy",
                    "model_name": "ai.agent",
                    "preview_menu_id": menu.id,
                    "values": [
                        {
                            "field_values": [
                                {
                                    "field": "name",
                                    "value": "Jimmy",
                                },
                            ],
                        },
                    ],
                },
            ),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Create an agent named 'Jimmy'")

        self.assertEqual(
            session.pending_tool_call['call_id'],
            2,
            "Creation tool should be pending on first call.",
        )

        with self.mock_callback_completions([self.mock_text_response("Agent Jimmy created")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call, "Creation tool call should be confirmed")

        created_agent = self.env["ai.agent"].search([("name", "=", "Jimmy")])
        self.assertTrue(created_agent)

        all_message_contents = [
            msg.body for msg in session.channel_id.message_ids[::-1]
        ]

        self.assertIn(
            f'has created <a href="#" data-oe-model="ai.agent" data-oe-id="{created_agent.id}">Jimmy</a>',
            all_message_contents[-1],
            "Preview message should be posted in the channel after creation is accepted",
        )
        self.assertEqual(all_message_contents[-2], '<p>Agent Jimmy created</p>')

    def test_create_records_accepted_posts_preview_link_multiple_records(self):
        """Links should be properly formatted in the preview message when multiple records are created"""

        action = self.env["ir.actions.act_window"].create({
            "res_model": "ai.agent"
        })

        menu = self.env["ir.ui.menu"].create({
            "name": "Test Agents",
            "action": f"{action._name},{action.id}",
        })

        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.create_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(
                self.create_tool,
                {
                    "explanation": "Creating new AI agent named Jimmy",
                    "model_name": "ai.agent",
                    "preview_menu_id": menu.id,
                    "values": [
                        {
                            "field_values": [
                                {
                                    "field": "name",
                                    "value": "Jimmy",
                                },
                            ],
                        },
                        {
                            "field_values": [
                                {
                                    "field": "name",
                                    "value": "Bob",
                                },
                            ],
                        },
                    ],
                },
            ),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Create an agent named 'Jimmy'")

        self.assertEqual(
            session.pending_tool_call['call_id'],
            2,
            "Creation tool should be pending on first call.",
        )

        with self.mock_callback_completions([self.mock_text_response("Agent Jimmy created")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call, "Creation tool call should be confirmed")

        created_agents = self.env["ai.agent"].search(["|", ("name", "=", "Jimmy"), ("name", "=", "Bob")], order="id ASC")
        self.assertEqual(2, len(created_agents))

        all_message_contents = [
            msg.body for msg in session.channel_id.message_ids[::-1]
        ]

        self.assertEqual(
            html_sanitize(Markup('<div class="o_mail_notification" data-oe-type="ai_preview"><span>%s</span></div>')
            % self.env._(
                "has created %s",
                Markup(
                    "<a href=\"/web#action=%d&domain=[('id', 'in', %r)]\">multiple records (%s)</a>",
                )
                % (action.id, created_agents.ids, self.env["ai.agent"]._description),
            )),
            all_message_contents[-1],
            "Preview message should be posted in the channel after creation is accepted",
        )
        self.assertEqual(all_message_contents[-2], '<p>Agent Jimmy created</p>')

    def test_create_records_raises_value_error_on_sql_constraint_fail(self):
        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.create_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skills")

        mocked_responses = [
            self.mock_tool_response(
                self.create_tool,
                {
                    "explanation": "Creating new mail activity: Call Marc Demo",
                    "model_name": "mail.activity",
                    "values": [
                        {
                            "field_values": [
                                {
                                    "field": "res_id",
                                    "value": 9999,
                                },
                                {
                                    "field": "res_model",
                                    "value": "res.partner",
                                },
                                {
                                    "field": "summary",
                                    "value": "Call Marc Demo",
                                },
                            ],
                        },
                    ],
                },
            ),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(
                session,
                "Create a mail activity for tomorrow: Call Marc Demo",
            )

        self.assertEqual(
            session.pending_tool_call['call_id'],
            2,
            "Creation tool should be pending on first call.",
        )

        # Tool confirmation
        with (
            self.mock_callback_completions(
                [self.mock_text_response("Sorry, that failed.")],
            ),
            self.assertLogs(tool_logger, level="WARNING") as mock_tool_logger,
            self.assertLogs(sql_logger, level="ERROR"),
        ):
            self._confirm_pending_tool(session)

        self.assertIn(
            "mail_activity_check_res_id_is_set_if_model",
            "".join(r.msg for r in mock_tool_logger.records),
        )
        self.assertFalse(session.pending_tool_call)
        self.assertFalse(
            self.env["mail.activity"].search([("summary", "=", "Call Marc Demo")]),
        )
        tool_result = self._get_tool_result(session, 2)
        self.assertFalse(tool_result['success'])
        self.assertIn(
            "Tool call failed:",
            tool_result['result'][0]['text'],
        )
        # follow-up assistant message posted
        self.assertIn("Sorry, that failed.", session.channel_id.message_ids[0].body)
