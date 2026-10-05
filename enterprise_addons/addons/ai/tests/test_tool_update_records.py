# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.ai.models.ai_session import _logger as tool_logger
from odoo.addons.ai.tests.common import TestAICallbackCommon
from odoo.addons.ai.utils.ai_utils import make_records_update_preview
from odoo.tools.mail import html_to_inner_content
from odoo.tools.misc import format_datetime
from odoo.tests import users
from odoo.sql_db import _logger as sql_logger


class TestAiToolUpdateRecords(TestAICallbackCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.update_tool = cls.env.ref('ai.ir_actions_server_update_records')
        cls.update_records_skill = cls.env["ai.skill"].create({
            'name': 'Test Skill',
            'instructions': 'Skill instructions',
            'tool_ids': cls.update_tool.ids,
        })
        cls.agent.sudo().write({
            'skill_ids': cls.agent.skill_ids | cls.update_records_skill,
        })

    def test_update_records_tool(self):
        """Check that the update records tool asks for confirmation with a preview of the changes,
        and that it correctly updates the records when confirming the tool call.
        """
        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.update_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(self.update_tool, {
                "explanation": "Updating Test Agent to Jimmy",
                "preview_menus": [],
                'updates': [
                    {
                        'model_name': 'ai.agent',
                        'domain': f"[('id', '=', {self.agent.id})]",
                        'changes': [{
                            'field': 'name',
                            'value': 'Jimmy',
                        }]
                    }
                ],
            }),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Change agent name")

        # should ask for the confirmation
        self.assertEqual(session.pending_tool_call['call_id'], 2)

        # pending confirmation should preview the changes
        self.assertIn(
            'AI Agent "Test Agent": Agent Name → Jimmy',
            html_to_inner_content(session.pending_tool_call['user_input_request']['body']),
        )
        # but change should not be done yet
        self.assertEqual(self.agent.name, 'Test Agent')

        # confirm tool
        with self.mock_callback_completions([self.mock_text_response("Changes done")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        # change should be done
        self.assertEqual(self.agent.name, 'Jimmy')

    @users('user_internal')
    def test_update_records_tool_access(self):
        """Users should not be able to update records they cannot access through AI agents
        """
        session_sudo = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.update_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session_sudo, "Load skill")

        mocked_responses = [
            self.mock_tool_response(self.update_tool, {
                "explanation": "Updating AI Agent Jimmy",
                "preview_menus": [],
                'updates': [
                    {
                        'model_name': 'ai.agent',
                        'domain': f"[('id', '=', {self.agent.id})]",
                        'changes': [{
                            'field': 'name',
                            'value': 'Jimmy',
                        }]
                    }
                ],
            }),
            self.mock_text_response("Not allowed")
        ]

        with self.mock_callback_completions(mocked_responses), self.assertLogs(tool_logger, level='WARNING') as mock_tool_logger:
            self._post_user_message_on_session(session_sudo, "Change agent name")

        # error is logged, tool call should be shown as erroneous
        self.assertIn(
            "You are not allowed to modify 'AI Agent' (ai.agent) records",
            mock_tool_logger.records[0].msg,
        )
        self.assertFalse(session_sudo.pending_tool_call)
        tool_result = self._get_tool_result(session_sudo, 2)
        self.assertFalse(tool_result['success'])
        self.assertIn(
            "Error: Tool call failed: You are not allowed to modify 'AI Agent' (ai.agent) records",
            tool_result['result'][0]['text'],
        )

        # message should be in session history and posted
        self.assertEqual(
            {
                'role': 'assistant',
                'content': [{'type': 'text', 'text': 'Not allowed'}],
                'provider_metadata': {},
            },
            session_sudo.event_ids.sorted('id')[-1].metadata,
        )
        self.assertIn("Not allowed", session_sudo.channel_id.message_ids[0].body)

    def test_update_preview_basic_fields(self):
        """Check the formatting of the different field types when using the update tool record.
        """
        message = self.env['mail.message'].create({
            'author_id': self.env.user.partner_id.id,  # many2one
            'message_type': 'email',  # selection
            'is_internal': True,  # bool
            'email_from': "from@example.com",  # char
            'incoming_email_to': "incoming@example.com",  # text
            'body': "<p>Hi</p>",  # html
            'pinned_at': '2025-01-15 12:34:56',  # datetime
        })
        changes = make_records_update_preview(message, {
            'author_id': self.ref('base.partner_root'),
            'message_type': 'comment',
            'is_internal': False,
            'email_from': "fromage@example.com",
            'incoming_email_to': "incoming2@example.com",
            'body': '<p>Hello</p>',
            'pinned_at': '2025-01-16 12:34:56',
        })
        self.assertEqual(changes[0], {
            'old_val': self.env.user.partner_id.display_name,
            'new_val': self.env.ref('base.user_root').display_name,
            'field_name': 'Author',
        })
        self.assertEqual(changes[1], {
            'old_val': 'Incoming Email',
            'new_val': 'Comment',
            'field_name': 'Type',
        })
        self.assertEqual(changes[2], {
            'old_val': True,
            'new_val': "None",
            'field_name': 'Employee Only',
        })
        self.assertEqual(changes[3], {
            'old_val': 'from@example.com',
            'new_val': 'fromage@example.com',
            'field_name': 'From',
        })
        self.assertEqual(changes[4], {
            'old_val': 'incoming@example.com',
            'new_val': 'incoming2@example.com',
            'field_name': 'Emails To',
        })
        self.assertEqual(changes[5], {
            'old_val': 'Hi',
            'new_val': 'Hello',
            'field_name': 'Contents',
        })
        self.assertEqual(changes[6], {
            'old_val': format_datetime(self.env, '2025-01-15 12:34:56'),
            'new_val': format_datetime(self.env, '2025-01-16 12:34:56'),
            'field_name': 'Pinned',
        })

    def test_update_preview_x2m_commands(self):
        message = self.env['mail.message'].create({'body': "<p>Hi</p>"})

        reaction1 = self.env['mail.message.reaction'].create({'content': "🗿", 'message_id': message.id, 'partner_id': self.env.user.partner_id.id})
        reaction2 = self.env['mail.message.reaction'].create({'content': "🥸", 'message_id': message.id, 'partner_id': self.env.user.partner_id.id})
        preview = make_records_update_preview(message, {
            'reaction_ids': [Command.link(reaction1.id), Command.link(reaction2.id)]
        })

        self.assertEqual(preview[0]['field_name'], 'Reactions')
        self.assertEqual(
            html_to_inner_content(preview[0]['new_val']),
            f'Add "mail.message.reaction,{reaction1.id}"Add "mail.message.reaction,{reaction2.id}"'
        )

    def test_update_preview_x2m_create_command_not_allowed(self):
        """Command.create should raise a ValueError when used in an update preview."""
        message = self.env['mail.message'].create({'body': "<p>Hi</p>"})

        with self.assertRaisesRegex(ValueError, f"Command {Command.CREATE} cannot be used during an update."):
            make_records_update_preview(message, {
                'reaction_ids': [Command.create({'content': "🗿"})],
            })

    def test_update_records_accepted_posts_preview_link(self):
        """A preview message should be posted in the channel when an update tool call is accepted"""

        partner = self.env["res.partner"].create({"name": "Test Partner"})

        action = self.env["ir.actions.act_window"].create({
            "res_model": "res.partner",
        })

        menu = self.env["ir.ui.menu"].create({
            "name": "Test Partners",
            "action": f"{action._name},{action.id}",
        })

        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.update_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(self.update_tool, {
                "explanation": "Updating Test Partner to Jimmy",
                "preview_menus": [{"model_name": "res.partner", "menu_id": menu.id}],
                'updates': [
                    {
                        'model_name': 'res.partner',
                        'domain': f"[('id', '=', {partner.id})]",
                        'changes': [{
                            'field': 'name',
                            'value': 'Jimmy',
                        }],
                    },
                ],
            }),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Change agent name")

        # should ask for the confirmation
        self.assertEqual(session.pending_tool_call['call_id'], 2)

        # pending confirmation should preview the changes
        self.assertIn(
            'Contact "Test Partner": Name → Jimmy',
            html_to_inner_content(session.pending_tool_call['user_input_request']['body']),
        )
        # but change should not be done yet
        self.assertEqual(partner.name, 'Test Partner')

        # confirm tool
        with self.mock_callback_completions([self.mock_text_response("Changes done")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        self.assertEqual(partner.name, 'Jimmy', "Name should have been updated")

        all_message_contents = [
            msg.body for msg in session.channel_id.message_ids[::-1]
        ]

        self.assertIn(
            f'has updated <a href="#" data-oe-model="res.partner" data-oe-id="{partner.id}">Jimmy</a>',
            all_message_contents[-1],
            "Preview message should be posted in the channel after update is accepted",
        )
        self.assertEqual(all_message_contents[-2], '<p>Changes done</p>')

    def test_update_records_accepted_posts_preview_link_multiple_records(self):
        """A preview proper preview message should be posted in the channel when a creation tool call is accepted which modifies multiple records."""

        action = self.env["ir.actions.act_window"].create(
            {
                "res_model": "ai.agent",
            },
        )

        menu = self.env["ir.ui.menu"].create(
            {
                "name": "Test Agents",
                "action": f"{action._name},{action.id}",
            },
        )

        another_agent = self.env["ai.agent"].create({
            "name": "Another agent",
        })

        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.update_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(self.update_tool, {
                "explanation": "Updating Test Agent to Jimmy",
                "preview_menus": [{"model_name": "ai.agent", "menu_id": menu.id}],
                'updates': [
                    {
                        'model_name': 'ai.agent',
                        'domain': f"[('id', '=', {self.agent.id})]",
                        'changes': [{
                            'field': 'name',
                            'value': 'Jimmy',
                        }],
                    },
                    {
                        'model_name': 'ai.agent',
                        'domain': f"[('id', '=', {another_agent.id})]",
                        'changes': [{
                            'field': 'name',
                            'value': 'Bob',
                        }],
                    },
                ],
            }),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Change agent name")

        # should ask for the confirmation
        self.assertEqual(session.pending_tool_call['call_id'], 2)

        # pending confirmation should preview the changes
        self.assertIn(
            'AI Agent "Test Agent": Agent Name → Jimmy AI Agent "Another agent": Agent Name → Bob',
            html_to_inner_content(session.pending_tool_call['user_input_request']['body']),
        )
        self.assertEqual(self.agent.name, "Test Agent", "Change should not be done before accepting.")
        self.assertEqual(another_agent.name, 'Another agent', "Change should not be done before accepting.")

        # confirm tool
        with self.mock_callback_completions([self.mock_text_response("Changes done")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        self.assertEqual(self.agent.name, 'Jimmy', "Name should have been updated")
        self.assertEqual(another_agent.name, 'Bob', "Name should have been updated")

        all_message_contents = [
            msg.body for msg in session.channel_id.message_ids[::-1]
        ]

        self.assertIn(
            # agents were updated: ai_agentic replaces the generic link note
            "self-updated its configuration",
            all_message_contents[-1],
            "Preview message should be posted in the channel after update is accepted",
        )
        self.assertEqual(all_message_contents[-2], '<p>Changes done</p>')

    def test_update_records_raises_value_error_on_sql_constraint_fail(self):
        """Check that the update records tool asks for confirmation with a preview of the changes,
        and that it correctly updates the records when confirming the tool call.
        """
        partner = self.env["res.partner"].create({"name": "Marc Demo"})
        activity = self.env["mail.activity"].create(
            {
                "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "res_id": partner.id,
                "summary": "Call Marc Demo",
                "date_deadline": "2026-07-05",
            },
        )
        session = self._create_ai_session(self.agent)

        mocked_responses = [
            self.mock_tool_response(self.skill_loading_tool, {"skill_ids": self.update_records_skill.ids}),
            self.mock_text_response("skills enabled"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Load skill")

        mocked_responses = [
            self.mock_tool_response(
                self.update_tool,
                {
                    "explanation": "Updating activity 'Call Marc Demo'",
                    "preview_menus": [],
                    "updates": [
                        {
                            "model_name": "mail.activity",
                            "domain": f"[('id', '=', {activity.id})]",
                            "changes": [
                                {
                                    "field": "res_id",
                                    "value": 0,
                                },
                            ],
                        },
                    ],
                },
            ),
            self.mock_text_response("Changes done"),
        ]

        with self.mock_callback_completions(mocked_responses):
            self._post_user_message_on_session(session, "Change agent name")

        # should ask for the confirmation
        self.assertEqual(session.pending_tool_call['call_id'], 2)

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
        self.assertEqual(
            activity.res_id,
            partner.id,
            "The invalid update must be rolled back.",
        )
        tool_result = self._get_tool_result(session, 2)
        self.assertFalse(tool_result['success'])
        self.assertIn(
            "Tool call failed:",
            tool_result['result'][0]['text'],
        )
        self.assertIn("Sorry, that failed.", session.channel_id.message_ids[0].body)

    def test_confirmed_update_records_raises_value_error_on_dummy_truthy_domain(self):
        with self.assertRaises(ValueError, msg="You cannot update using a dummy truthy domain (e.g. [], True). To update all records, pass a domain that matches all records instead."):
            self.env['ai.tool'].sudo()._ai_tool_update_records(
                tool_context={"tool_request_confirmed": True},
                explanation="Updating all partners' names to abc",
                preview_menus=[],
                updates=[
                    {
                        "model_name": "res.partner",
                        "domain": "[]",
                        "changes": [
                            {
                                "field": "name",
                                "value": "abc",
                            },
                        ],
                    },
                ],
            )

        with self.assertRaises(ValueError, msg="You cannot update using a dummy truthy domain (e.g. [], True). To update all records, pass a domain that matches all records instead."):
            self.env['ai.tool'].sudo()._ai_tool_update_records(
                tool_context={"tool_request_confirmed": True},
                explanation="Updating all partners' names to abc",
                preview_menus=[],
                updates=[
                    {
                        "model_name": "res.partner",
                        "domain": "True",
                        "changes": [
                            {
                                "field": "name",
                                "value": "abc",
                            },
                        ],
                    },
                ],
            )
