# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from textwrap import dedent
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.exceptions import ValidationError

from odoo.addons.ai.tests.common import TestAICallbackCommon
from odoo.addons.ai.utils.agent_instructions_prompts import RESTRICT_TO_SOURCES
from odoo.addons.ai.utils.ai_utils import UserInputResponse, format_tool_summary
from odoo.addons.bus.tests.common import BusCase, BusResult
from odoo.addons.mail.tools.discuss import Store


@tagged("post_install", "-at_install")
class TestAISession(TestAICallbackCommon, BusCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tool = cls.env['ir.actions.server'].create([{
            'model_id': cls.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'tool',
            'ai_tool_name': 'tool',
            'use_in_ai': True,
            'code': "ai['result'] = 'done'",
            'ai_tool_schema': dedent("""
                {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string"
                        }
                    },
                    "required": []
                }
            """),
        }])
        cls.tool_w_confirm = cls.env['ir.actions.server'].create([{
            'model_id': cls.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'tool_w_confirm',
            'ai_tool_name': 'tool_w_confirm',
            'use_in_ai': True,
            'code': dedent("""
                if not ai['tool_request_confirmed']:
                    ai['user_input_request'] = {
                        'type': 'confirmation',
                        'body': 'Do this?',
                        'choices': [
                            {'label': 'Yes, do it', 'value': 'confirm_once'},
                            {'label': 'Yes, always approve in this chat', 'value': 'auto_confirm'},
                        ],
                    }
                else:
                    ai['result'] = 'Confirmed!'
            """),
            'ai_tool_schema': dedent("""
                {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string"
                        }
                    },
                    "required": []
                }
            """)
        }])
        cls.tool_with_summary = cls.env['ir.actions.server'].create({
            'model_id': cls.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'tool_with_summary',
            'ai_tool_name': 'tool_with_summary',
            'use_in_ai': True,
            'code': dedent("""
                ai['result'] = {
                    'response': 'done',
                    'summary': {'icon': 'check', 'text': 'Updated records'},
                }
            """),
            'ai_tool_schema': dedent("""
                {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string"
                        }
                    },
                    "required": []
                }
            """),
        })
        cls.tool_failing = cls.env['ir.actions.server'].create({
            'model_id': cls.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'tool_failing',
            'ai_tool_name': 'tool_failing',
            'use_in_ai': True,
            'code': "int('invalid')",
        })
        cls.skill.sudo().write({
            'name': 'Test Skill',
            'instructions': 'Skill instructions',
            'tool_ids': (cls.tool | cls.tool_w_confirm).ids,
        })
        cls.agent.sudo().write({
            'skill_ids': cls.skill,
        })

    def test_session_configuration_defaults(self):
        agent_session = self._create_ai_session(self.agent)
        self.agent_with_sources.restrict_to_sources = True
        agent_with_sources_session = self._create_ai_session(self.agent_with_sources)

        ai_session_config = self._get_ai_session_default_controls()
        self.assertEqual(
            ai_session_config,
            agent_session.get_session_config(),
        )

        # Default behavior for session of an agent with restrict_to_sources
        ai_session_config["enable_resources_only"] = True
        ai_session_config["enable_web_search"] = False

        self.assertEqual(
            ai_session_config,
            agent_with_sources_session.get_session_config(),
        )

    def test_session_configuration_update(self):
        session = self._create_ai_session(self.agent)

        new_config = {
            "enable_web_search": False,
            "enable_resources_only": True,
            "enable_think_longer": True,
            "auto_confirm": True,
            "show_agent_steps": True,
        }

        with self.mock_callback_completions([
            self.mock_text_response("Hi"),
        ]):
            # Session configurations are updated after each request
            self._post_user_message_on_session(session, "Hello", ai_session_config=new_config)

        self.assertEqual(new_config, session.get_session_config())

    def test_session_configuration_invalid_update(self):
        session = self._create_ai_session(self.agent)

        # Sending unrecognized flags raises an error.
        random_config = {"is_omar_awesome": True, "is_earth_falt": False}
        with self.assertRaises(ValidationError):
            session.update_session_config(random_config)

        # Sending conflicting flags raises an error.
        conflicting_config = {
            "enable_resources_only": True,
            "enable_web_search": True,
        }
        with self.assertRaises(ValidationError):
            session.update_session_config(conflicting_config)

    def test_ai_chat_is_renamed_after_first_message(self):
        session = self._create_ai_session(self.agent)
        session.channel_id.name = "Existing conversation title"

        with self.mock_callback_completions(
            [self.mock_text_response("Agent response")],
            channel_name="Updated conversation title",
        ):
            self._post_user_message_on_session(session, "Hello")

        self.assertEqual(session.channel_id.name, "Updated conversation title")

    def test_agent_instructions_intermediary_messages_protocol(self):
        """Check that the instructions about the intermediary messages only asks to provide
        technical details when the debug mode is active"""
        standard_instructions = self.agent._get_instructions()
        debug_instructions = self.agent.with_context(debug=True)._get_instructions()

        self.assertIn("<intermediary_messages>", standard_instructions)
        self.assertIn("Do not mention technical names", standard_instructions)
        self.assertNotIn("Contain technical details", standard_instructions)
        self.assertIn("<intermediary_messages>", debug_instructions)
        self.assertIn("Contain technical details", debug_instructions)

    def test_failed_tool_yields_summary(self):
        """Check that when a tool call raises an error, a tool call failure summary is posted"""
        session = self._create_ai_session(self.agent)
        tool_call = {
            'name': self.tool_failing.ai_tool_name,
            'args': {'tool_status': 'Running tool'},
            'call_id': 'call_1',
        }

        with mute_logger('odoo.addons.ai.models.ai_session'):
            items = list(session._handle_tool_calls(
                [tool_call],
                {self.tool_failing.ai_tool_name: self.tool_failing},
                tools_context=session._build_tools_context({}),
                record=None,
            ))

        self.assertIn({
            'intermediary_message': format_tool_summary({
                'icon': 'warning',
                'text': self.tool_failing.name,
            }, tool_call),
            'is_tool_summary': True,
        }, items)

    def test_tool_status_is_published_after_sending_tool_results(self):
        session = self._create_ai_session(self.agent)
        with self.mock_default_tools(self.tool):
            session._submit_agent_request(self.mock_text_response("Update the records"))
        tool_call, = self.mock_tool_response(self.tool, {
            'value': 'test',
            'tool_status': 'Updating records',
        })
        completion_result = {
            'kind': 'success',
            'message': {
                'role': 'assistant',
                'content': [tool_call],
                'provider_metadata': {},
            },
        }

        def expected_notification():
            expected_store = Store().add(session, '_store_session_fields')
            expected_store.add(session, {'toolStatus': 'Updating records'})
            return BusResult(session.channel_id, 'mail.record/insert', expected_store)

        with (
            patch.object(session.__class__, 'post_agent_step'),
            self.assertBus(expected_notification),
        ):
            session._continue_agent_loop(completion_result)

        self.assertEqual(session.loop_state, 'waiting_model')
        self.assertEqual(session.event_ids[0].metadata['role'], 'user')
        self.assertEqual(session.event_ids[1].metadata['role'], 'assistant')
        self.assertEqual(session.request_payload['messages'][-1]['role'], 'user')

    def test_intermediary_message_and_tool_summary_are_posted(self):
        """Check that when the agent sends a message with a tool call, the message and the tool
        summary are posted as intermediary message.
        type comment for verbose messages
        subtype mt_note for intermediary messages"""
        session = self._create_ai_session(self.agent)
        mocked_responses = [
            [
                *self.mock_text_response("I found the records. I'll now update them."),
                *self.mock_tool_response(self.tool_with_summary, {
                    'value': 'test',
                    'tool_status': 'Updating records',
                }),
            ],
            self.mock_text_response("Done"),
        ]

        with (
            self.mock_callback_completions(mocked_responses),
            self.mock_default_tools(self.tool_with_summary),
        ):
            self._post_user_message_on_session(
                session,
                "Update the records",
            )
        # check tool was called
        self.assertEqual(
            session.event_ids[1].metadata['content'][0]['result'],
            [{'type': 'text', 'text': 'done'}],
        )
        agent_messages = session.channel_id.message_ids.filtered(
            lambda message: message.author_id == self.agent.partner_id
        ).sorted('id')
        self.assertEqual(len(agent_messages), 3)
        # first the intermediary message
        self.assertIn("I found the records. I'll now update them.", agent_messages[0].body)
        self.assertEqual('comment', agent_messages[0].message_type)
        self.assertEqual(self.env.ref('mail.mt_note'), agent_messages[0].subtype_id)
        # then the tool summary
        self.assertIn("Updated records", agent_messages[1].body)
        self.assertEqual('notification', agent_messages[1].message_type)
        self.assertEqual(self.env.ref('mail.mt_note'), agent_messages[1].subtype_id)
        # finally the response
        self.assertIn("Done", agent_messages[2].body)
        self.assertEqual('comment', agent_messages[2].message_type)
        self.assertEqual(self.env.ref('mail.mt_comment'), agent_messages[2].subtype_id)

    def test_post_agent_step_notification_depends_on_user(self):
        """Check that the intermediary messages are not posted with non-internal users,
        but they should be logged (so that internal users can debug sessions)"""
        session = self._create_ai_session(self.agent)
        event = self.env['ai.session.event'].sudo().create({
            'ai_session_id': session.id,
            'metadata': self.mock_text_response("Checking records"),
        })
        expected_body = f'<div class="o-ai-agent-step" data-id="{event.id}">Checking records</div>'
        channel_model = session.channel_id.__class__

        with (
            patch.object(channel_model, '_message_log') as message_log,
            patch.object(channel_model, 'message_post') as message_post,
        ):
            session.post_agent_step("Checking records", 'comment')

        message_log.assert_not_called()
        message_post.assert_called_once_with(
            body=expected_body,
            author_id=self.agent.partner_id.id,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
            is_internal=True,
            silent=True,
        )

        with (
            patch.object(channel_model, '_message_log') as message_log,
            patch.object(channel_model, 'message_post') as message_post,
        ):
            session.with_user(self.env.ref('base.public_user')).sudo().post_agent_step("Checking records", 'comment')

        message_log.assert_called_once_with(
            body=expected_body,
            author_id=self.agent.partner_id.id,
            message_type='comment',
        )
        message_post.assert_not_called()

    def test_prepare_tools_adds_status_only_when_enabled(self):
        """Check that the toolStatus parameter is only added when the ai_show_tool_status context
        key is set (toolStatus is not needed for background AI tasks)"""
        tools_by_name = {self.tool.ai_tool_name: self.tool}

        tool_without_steps, = self.env['ai.session']._prepare_tools(tools_by_name)
        tool_with_steps, = self.env['ai.session'].with_context(ai_show_tool_status=True)._prepare_tools(
            tools_by_name,
        )

        self.assertNotIn('tool_status', tool_without_steps['schema']['properties'])
        self.assertIn('tool_status', tool_with_steps['schema']['properties'])
        self.assertIn('tool_status', tool_with_steps['schema']['required'])

    def test_action_launch_ai_chat(self):
        """Ensure action_launch_ai_chat creates a new session and suggests the latest non-empty chat."""

        session_1_data = self.env['ai.agent'].action_launch_ai_chat(interface_key='systray_ai_button')
        channel_1 = self.env['discuss.channel'].browse(session_1_data['ai_channel_id'])
        channel_1.message_post(body="Hello", message_type="comment")
        session_2_data = self.env['ai.agent'].action_launch_ai_chat(interface_key='systray_ai_button')

        self.assertLess(
            session_1_data['ai_channel_id'],
            session_2_data['ai_channel_id'],
            "Each call to action_launch_ai_chat should open a new ai chat channel."
        )
        channel_2_data = next(
            channel_data
            for channel_data in session_2_data['data']._build_result()['discuss.channel']
            if channel_data['id'] == session_2_data['ai_channel_id']
        )
        self.assertEqual(
            channel_2_data['suggestedAiChannel'],
            session_1_data['ai_channel_id'],
            "The new AI chat should store the latest matching non-empty chat as its suggestion.",
        )

    def test_remove_inactive_ai_chat_channels(self):
        """Check inactive AI chats are deleted after 30 days, or 1 day if empty."""
        session = self._create_ai_session(self.agent)
        channel = session.channel_id
        empty_session = self._create_ai_session(self.agent)
        empty_channel = empty_session.channel_id
        now = fields.Datetime.now()
        last_message_date = now - timedelta(days=30, seconds=1)
        empty_channel.sudo().last_interest_dt = now - timedelta(days=1, seconds=1)

        with self.mock_datetime_and_now(last_message_date), \
            self.mock_callback_completions([self.mock_text_response("Hello")]):
            self._post_user_message_on_session(session, "Hello")
        event = session.event_ids

        self.assertEqual(channel.last_interest_dt, last_message_date)
        self.assertEqual(len(event), 2)

        self.env['discuss.channel']._remove_ai_chat_channels()

        self.assertFalse(session.exists())
        self.assertFalse(channel.exists())
        self.assertFalse(event.exists())
        self.assertFalse(empty_session.exists())
        self.assertFalse(empty_channel.exists())

    def test_tool_confirmation_request(self):
        """Check that a tool with a tool confirmation request asks for confirmation
        """
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions(
                [self.mock_tool_response(self.tool_w_confirm)]
            ),
            self.mock_default_tools(self.tool_w_confirm),
        ):
            self._post_user_message_on_session(session, "hey")

        self.assertEqual(session.loop_state, 'waiting_confirmation')
        self.assertTrue(session.resume_token)
        self.assertIn("Do this?", session.pending_tool_call['user_input_request']['body'])
        self.assertEqual(session.pending_tool_call['user_input_request']['type'], 'confirmation')
        self.assertEqual(
            session.pending_tool_call['user_input_request']['choices'],
            [
                {'label': 'Yes, do it', 'value': UserInputResponse.CONFIRM_ONCE},
                {'label': 'Yes, always approve in this chat', 'value': UserInputResponse.AUTO_CONFIRM},
            ],
        )
        self.assertEqual(session.pending_tool_call['call_id'], 1)
        self.assertFalse(session.pending_tool_call.get('pending_results'))

        # confirming the request
        with self.mock_callback_completions([self.mock_text_response("Done")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        # tool call result should be in the session history
        self._assert_tool_result_texts(
            session.event_ids[1], [(1, 'Confirmed!', True)],
        )
        # final message should be in the session history
        self.assertEqual(
            session.event_ids[0].metadata,
            {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Done'}], 'provider_metadata': {}},
        )
        # final message should be posted
        self.assertIn("Done", session.channel_id.message_ids[0].body)

        # Delegated confirmations keep the child's routing but speak as the root agent.
        child_agent = self.env['ai.agent'].create({'name': 'Child Agent'})
        self.agent.allowed_agent_ids = child_agent
        root = self._create_ai_session(self.agent)
        start_tool = self.env.ref('ai.ir_actions_server_start_session')
        start_call = self.mock_tool_response(start_tool, {'agent_id': child_agent.id, 'message': 'Do the work'})
        child_call = self.mock_tool_response(self.tool_w_confirm)
        with (
            self.mock_callback_completions([start_call, child_call]),
            self.mock_default_tools(start_tool | self.tool_w_confirm),
        ):
            self._post_user_message_on_session(root, "Delegate this")
        child = self.env['ai.session'].sudo().search([('parent_session_id', '=', root.id)])
        self.assertEqual(child.loop_state, 'waiting_confirmation')
        self.assertEqual(root.loop_state, 'waiting_child')

        with self.mock_callback_completions([self.mock_text_response("Child done"), self.mock_text_response("Root done")]):
            self._confirm_pending_tool(child)
        self.assertEqual(root.loop_state, 'ready')
        self.assertEqual(child.loop_state, 'ready')
        messages = root.channel_id.message_ids
        prompt = messages.filtered(lambda msg: 'ai_user_input_request' in (msg.body or ''))
        self.assertEqual(prompt.author_id, root.agent_id.partner_id)

    def test_record_preview_suffix_across_callbacks(self):
        session = self._create_ai_session(self.agent)
        preview_tool = self.env.ref('ai.ir_actions_server_preview_records')
        partner = self.env['res.partner'].create({'name': 'Preview Partner'})
        preview_args = {
            'model_name': 'res.partner',
            'records_to_preview': [{'id': partner.id}],
        }
        with (
            self.mock_default_tools(preview_tool | self.tool_w_confirm),
            self.mock_callback_completions([
                self.mock_tool_response(preview_tool, preview_args)
                + self.mock_tool_response(self.tool_w_confirm),
            ]),
        ):
            self._post_user_message_on_session(session, 'Show records, then ask for confirmation')

        with self.mock_callback_completions([
            self.mock_tool_response(preview_tool, preview_args),
            self.mock_text_response('Here are the records.'),
        ]):
            self._confirm_pending_tool(session)

        body = session.channel_id.message_ids[0].body
        self.assertEqual(body.count('class="o_ai_preview_data"'), 2)
        self.assertFalse(session.message_body_suffix)

    def test_client_tool_result(self):
        """Check that a client tool result resumes the loop without re-running its Python tool."""
        client_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'client_tool',
            'ai_tool_name': 'client_tool',
            'use_in_ai': True,
            'code': dedent("""
                ai['state']['client_tool_calls'] = ai['state'].get('client_tool_calls', 0) + 1
                ai['result'] = {
                    'client_tool': {
                        'name': 'get_client_data',
                        'params': {'key': 'value'},
                    },
                }
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([[
                *self.mock_tool_response(client_tool),
                *self.mock_tool_response(self.tool),
            ]]),
            self.mock_default_tools(client_tool | self.tool),
        ):
            self._post_user_message_on_session(session, "Get client data")

        self.assertEqual(session.pending_tool_call['client_tool'], {
            'name': 'get_client_data',
            'params': {'key': 'value'},
        })
        self.assertEqual(session.pending_tool_call['call_id'], 1)
        self.assertFalse(session.pending_tool_call.get('pending_results'))

        with (
            self.mock_callback_completions([self.mock_text_response("Done")]),
            self.mock_default_tools(client_tool | self.tool),
        ):
            self._resume_pending_tool_on_session(
                session, {'kind': 'client_result', 'value': {'client_value': 42}},
            )

        self.assertEqual(session.state['client_tool_calls'], 1)
        self.assertFalse(session.pending_tool_call)
        self._assert_tool_result_texts(
            session.event_ids[1],
            [(1, '{"client_value": 42}', True), (2, 'done', True)],
        )
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_async_tool_continuation(self):
        """An asynchronous server tool stays pending, flagged as waiting on an external result."""
        async_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'async_tool',
            'ai_tool_name': 'async_tool',
            'use_in_ai': True,
            'code': dedent("""
                if not ai['state'].get('external_result_available'):
                    ai['state']['external_result_available'] = True
                    ai['await_external_result'] = True
                else:
                    ai['result'] = 'External result received'
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([self.mock_tool_response(async_tool)]),
            self.mock_default_tools(async_tool),
        ):
            self._post_user_message_on_session(session, "Start external work")

        self.assertEqual(session.loop_state, 'waiting_external_result')
        self.assertEqual(session.pending_tool_call['call_id'], 1)
        self.assertTrue(session.pending_tool_call['await_external_result'])
        self.assertFalse(session.pending_tool_call.get('user_input_request'))
        self.assertIn("Waiting for an external result", session.channel_id.message_ids[0].body)

        with (
            self.mock_callback_completions([self.mock_text_response("Done")]),
            self.mock_default_tools(async_tool),
        ):
            self._resume_pending_tool_on_session(session, {
                'kind': 'async',
                'call_id': session.pending_tool_call['call_id'],
            })

        self.assertEqual(session.loop_state, 'ready')
        self.assertTrue(session.state['external_result_available'])
        self.assertFalse(session.pending_tool_call)
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_tool_response_without_pending_tool(self):
        """Ignore a client result when there is no pending interaction."""
        session = self._create_ai_session(self.agent)

        with self.mock_callback_completions([]) as transport:
            response = self._call_ai_endpoint("/ai/resume_pending_interaction", {
                "channel_id": session.channel_id.id,
                "session_id": session.id,
                "resume_token": "",
                "response": {'kind': 'client_result', 'value': "client result"},
            })

        self.assertEqual(response['loop_state'], 'ready')
        self.assertFalse(session.event_ids)
        transport.assert_not_called()

    def test_client_tool_error(self):
        """Check that a client tool error is sent to the LLM."""
        client_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'client_tool',
            'ai_tool_name': 'client_tool',
            'use_in_ai': True,
            'code': dedent("""
                ai['state']['client_tool_calls'] = ai['state'].get('client_tool_calls', 0) + 1
                ai['result'] = {
                    'client_tool': {
                        'name': 'get_client_data',
                        'params': {},
                    },
                }
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([self.mock_tool_response(client_tool)]),
            self.mock_default_tools(client_tool),
        ):
            self._post_user_message_on_session(session, "Get client data")

        with (
            self.mock_callback_completions([self.mock_text_response("Done")]),
            self.mock_default_tools(client_tool),
        ):
            self._resume_pending_tool_on_session(
                session, {'kind': 'client_error', 'value': "Client tool failed"},
            )

        self.assertEqual(session.state['client_tool_calls'], 1)
        self.assertFalse(session.pending_tool_call)
        self._assert_tool_result_texts(
            session.event_ids[1], [(1, 'Error: Client tool failed', False)],
        )
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_oneway_client_tool(self):
        """Check that a one-way client tool does not wait for a result."""
        client_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'client_tool',
            'ai_tool_name': 'client_tool',
            'use_in_ai': True,
            'code': dedent("""
                ai['state']['client_tool_calls'] = ai['state'].get('client_tool_calls', 0) + 1
                ai['result'] = {
                    'response': 'server result',
                    'client_tool': {
                        'name': 'show_client_data',
                        'params': {'key': 'value'},
                        'oneway': True,
                    },
                }
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([
                self.mock_tool_response(client_tool),
                self.mock_text_response("Done"),
            ]),
            self.mock_default_tools(client_tool),
        ):
            self._post_user_message_on_session(session, "Show client data")

        self.assertEqual(session.state['client_tool_calls'], 1)
        self.assertFalse(session.pending_tool_call)
        self._assert_tool_result_texts(
            session.event_ids[1], [(1, 'server result', True)],
        )
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_oneway_reload_client_tool(self):
        """Check that a one-way reload does not wait for a result."""
        reload_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'reload_tool',
            'ai_tool_name': 'reload_tool',
            'use_in_ai': True,
            'code': dedent("""
                ai['result'] = {
                    'response': 'server result',
                    'client_tool': {
                        'name': 'reload',
                        'oneway': True,
                    },
                }
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([
                self.mock_tool_response(reload_tool),
                self.mock_text_response("Done"),
            ]),
            self.mock_default_tools(reload_tool),
        ):
            self._post_user_message_on_session(session, "Reload")

        self.assertFalse(session.pending_tool_call)
        self._assert_tool_result_texts(
            session.event_ids[1], [(1, 'server result', True)],
        )
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_client_tool_falsy_result(self):
        """Check that falsy client tool results are preserved."""
        client_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'client_tool',
            'ai_tool_name': 'client_tool',
            'use_in_ai': True,
            'code': dedent("""
                ai['state']['client_tool_calls'] = ai['state'].get('client_tool_calls', 0) + 1
                ai['result'] = {
                    'client_tool': {
                        'name': 'get_client_data',
                        'params': {},
                    },
                }
            """),
        })

        for tool_result, expected_data in [
            (False, 'false'),
            (0, '0'),
            (None, 'success'),
        ]:
            with self.subTest(tool_result=tool_result):
                self.call_id = 0
                session = self._create_ai_session(self.agent)
                with (
                    self.mock_callback_completions([self.mock_tool_response(client_tool)]),
                    self.mock_default_tools(client_tool),
                ):
                    self._post_user_message_on_session(session, "Get client data")

                with (
                    self.mock_callback_completions([self.mock_text_response("Done")]),
                    self.mock_default_tools(client_tool),
                ):
                    self._resume_pending_tool_on_session(
                        session, {'kind': 'client_result', 'value': tool_result},
                    )

                self.assertEqual(session.state['client_tool_calls'], 1)
                self.assertFalse(session.pending_tool_call)
                self._assert_tool_result_texts(
                    session.event_ids[1], [(1, expected_data, True)],
                )

    def test_client_tool_result_w_final_message(self):
        """Check that a client tool result keeps the tool's final message."""
        client_tool = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('ai.agent'),
            'state': 'code',
            'name': 'client_tool',
            'ai_tool_name': 'client_tool',
            'use_in_ai': True,
            'code': dedent("""
                ai['final_message'] = [{
                    'type': 'text',
                    'text': 'Done',
                }]
                ai['result'] = {
                    'client_tool': {
                        'name': 'get_client_data',
                        'params': {},
                    },
                }
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([
                self.mock_tool_response(client_tool),
            ]),
            self.mock_default_tools(client_tool),
        ):
            self._post_user_message_on_session(session, "Get client data")

        with (
            self.mock_callback_completions([]),
            self.mock_default_tools(client_tool),
        ):
            self._resume_pending_tool_on_session(
                session, {'kind': 'client_result', 'value': "client result"},
            )

        self._assert_tool_result_texts(
            session.event_ids[0], [(1, 'client result', True)],
        )
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_tool_confirmation_request_w_final_message(self):
        """If a tool requiring confirmation supplies a final message, it should be posted
        when the user confirms the tool call.
        """
        tool_w_confirm_final = self.tool_w_confirm.copy({
            'name': 'tool_w_confirm_final',
            'ai_tool_name': 'tool_w_confirm_final',
            'code': dedent("""
                if not ai['tool_request_confirmed']:
                    ai['user_input_request'] = {
                        'type': 'confirmation',
                        'body': 'Do this?',
                        'choices': [
                            {'label': 'Yes, do it', 'value': 'confirm_once'},
                            {'label': 'Yes, always approve in this chat', 'value': 'auto_confirm'},
                        ],
                    }
                else:
                    ai['result'] = 'Confirmed!'
                    ai['final_message'] = [{
                        'type': 'text',
                        'text': 'Done',
                    }]
            """),
        })
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([self.mock_tool_response(tool_w_confirm_final)]),
            self.mock_default_tools(tool_w_confirm_final),
        ):
            self._post_user_message_on_session(session, "hey")

        self.assertEqual(session.loop_state, 'waiting_confirmation')
        self.assertTrue(session.resume_token)
        self.assertIn("Do this?", session.pending_tool_call['user_input_request']['body'])
        self.assertEqual(session.pending_tool_call['call_id'], 1)

        # confirming the request (no response bc it should not do a call since tool has final msg)
        with self.mock_callback_completions([]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        # tool call result should be in the session history
        self._assert_tool_result_texts(
            session.event_ids[0], [(1, 'Confirmed!', True)],
        )
        # final message should be posted
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_tool_confirmation_request_parallel_tool_calls(self):
        """Parallel tool calls with a tool confirmation request should request for the confirmation
        and next message to the LLM should include every tool output
        """
        session = self._create_ai_session(self.agent)

        mocked_responses = [
            [
                *self.mock_tool_response(self.tool, {'value': "val1"}),
                *self.mock_tool_response(self.tool, {'value': "val2"}),
                *self.mock_tool_response(self.tool_w_confirm, {'value': "val3"}),
                *self.mock_tool_response(self.tool, {'value': "val4"}),
                *self.mock_tool_response(self.tool, {'value': "val5"}),
            ],
        ]

        with (
            self.mock_callback_completions(mocked_responses),
            self.mock_default_tools(self.tool | self.tool_w_confirm),
        ):
            self._post_user_message_on_session(session, "hey")

        self.assertEqual(session.loop_state, 'waiting_confirmation')
        self.assertTrue(session.resume_token)
        self.assertIn("Do this?", session.pending_tool_call['user_input_request']['body'])
        # pending tool call fields should be set correctly
        self.assertEqual(session.pending_tool_call['call_id'], 3)
        self.assertEqual(
            session.pending_tool_call['pending_results'],
            [
                {'result': [{'text': 'done', 'type': 'text'}], 'success': True, 'tool_call_id': 1, 'tool_name': 'tool'},
                {'result': [{'text': 'done', 'type': 'text'}], 'success': True, 'tool_call_id': 2, 'tool_name': 'tool'},
            ]
        )

        # confirm tool request
        with (
            self.mock_callback_completions([self.mock_text_response("all done")]),
            self.mock_default_tools(self.tool | self.tool_w_confirm),
        ):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        # all tool calls should be in the session history
        self._assert_tool_result_texts(
            session.event_ids[1],
            [
                (1, 'done', True),
                (2, 'done', True),
                (3, 'Confirmed!', True),
                (4, 'done', True),
                (5, 'done', True),
            ],
        )

        # final message should be in the session history
        self.assertEqual(
            session.event_ids[0].metadata,
            {'role': 'assistant', 'content': [{'type': 'text', 'text': 'all done'}], 'provider_metadata': {}},
        )
        # final message should be posted
        self.assertIn("all done", session.channel_id.message_ids[0].body)

    def test_tool_confirmation_multi_confirmation(self):
        """All tools should require user confirmation if the model asks for several tool calls
        in parallel requiring user confirmation
        """
        session = self._create_ai_session(self.agent)

        mocked_responses = [
            [
                *self.mock_tool_response(self.tool_w_confirm, {'value': "val1"}),
                *self.mock_tool_response(self.tool_w_confirm, {'value': "val2"}),
                *self.mock_tool_response(self.tool_w_confirm, {'value': "val3"}),
            ],
        ]

        with (
            self.mock_callback_completions(mocked_responses),
            self.mock_default_tools(self.tool_w_confirm)
        ):
            self._post_user_message_on_session(session, "hey")

        self.assertEqual(session.loop_state, 'waiting_confirmation')
        self.assertTrue(session.resume_token)
        self.assertIn("Do this?", session.pending_tool_call['user_input_request']['body'])
        self.assertEqual(session.pending_tool_call['call_id'], 1)
        self.assertFalse(session.pending_tool_call.get('pending_results'))

        # confirming the request
        with self.mock_callback_completions([]):
            self._confirm_pending_tool(session)

        self.assertEqual(session.loop_state, 'waiting_confirmation')
        self.assertTrue(session.resume_token)
        self.assertIn("Do this?", session.pending_tool_call['user_input_request']['body'])
        self.assertEqual(session.pending_tool_call['call_id'], 2)
        self.assertEqual(
            session.pending_tool_call['pending_results'],
            [{
                'tool_name': 'tool_w_confirm',
                'tool_call_id': 1,
                'result': [{'type': 'text', 'text': 'Confirmed!'}],
                'success': True,
            }],
        )

        # confirming the request
        with self.mock_callback_completions([]):
            self._confirm_pending_tool(session)

        self.assertEqual(session.loop_state, 'waiting_confirmation')
        self.assertTrue(session.resume_token)
        self.assertIn("Do this?", session.pending_tool_call['user_input_request']['body'])
        self.assertEqual(session.pending_tool_call['call_id'], 3)
        self.assertEqual(
            session.pending_tool_call['pending_results'],
            [
                {
                    'tool_name': 'tool_w_confirm',
                    'tool_call_id': 1,
                    'result': [{'type': 'text', 'text': 'Confirmed!'}],
                    'success': True,
                },
                {
                    'tool_name': 'tool_w_confirm',
                    'tool_call_id': 2,
                    'result': [{'type': 'text', 'text': 'Confirmed!'}],
                    'success': True,
                },
            ]
        )

        # confirming the request
        with self.mock_callback_completions([self.mock_text_response("all done")]):
            self._confirm_pending_tool(session)

        self.assertFalse(session.pending_tool_call)

        # all tool calls should be in the session history
        self._assert_tool_result_texts(
            session.event_ids[1],
            [(1, 'Confirmed!', True), (2, 'Confirmed!', True), (3, 'Confirmed!', True)],
        )

        # final message should be in the session history
        self.assertEqual(
            session.event_ids[0].metadata,
            {'role': 'assistant', 'content': [{'type': 'text', 'text': 'all done'}], 'provider_metadata': {}},
        )
        # final message should be posted
        self.assertIn("all done", session.channel_id.message_ids[0].body)

    def test_tool_ask_user_question(self):
        """The generic ask_user_question tool should pause with a 'question' user_input_request
        and resolve the answer once the user replies through the widget."""
        session = self._create_ai_session(self.agent)
        ask_user_question_tool = self.env.ref("ai.ir_actions_server_ask_user_question")

        with (
            self.mock_callback_completions([self.mock_tool_response(ask_user_question_tool, {
                'question': "Which one?",
                'choices': ["Draft", "Send"],
                'multi_select': False,
                'allow_free_text': False,
            })]),
            self.mock_default_tools(ask_user_question_tool),
        ):
            self._post_user_message_on_session(session, "hey")

        self.assertEqual(session.loop_state, 'waiting_answer')
        self.assertTrue(session.resume_token)
        self.assertIn("Which one?", session.pending_tool_call['user_input_request']['body'])
        self.assertEqual(session.pending_tool_call['user_input_request']['type'], 'question')
        self.assertEqual(
            session.pending_tool_call['user_input_request']['choices'],
            [{'label': 'Draft', 'value': 'Draft'}, {'label': 'Send', 'value': 'Send'}],
        )
        self.assertEqual(session.pending_tool_call['user_input_request']['allow_free_text'], False)
        self.assertEqual(session.pending_tool_call['call_id'], 1)

        # answering the question (through the widget, ie. a structured pending_tool_user_response)
        with self.mock_callback_completions([self.mock_text_response("Done")]):
            self._resume_pending_tool_on_session(session, {'kind': 'question', 'value': ['Draft']})

        self.assertFalse(session.pending_tool_call)
        prompt = session.channel_id.message_ids.filtered(
            lambda message: 'ai_user_input_request' in (message.body or '')
        )
        self.assertIn("<p>Which one?</p>", prompt.body)

        # the synthesized answer should be in the session history as the tool call result
        self._assert_tool_result_texts(
            session.event_ids[1], [(1, 'USER ANSWER: Draft', True)],
        )
        # final message should be in the session history
        self.assertEqual(
            session.event_ids[0].metadata,
            {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Done'}], 'provider_metadata': {}},
        )
        # final message should be posted
        self.assertIn("Done", session.channel_id.message_ids[0].body)

    def test_abort_pending_tools(self):
        """Aborting a pending tool call should refuse it (and every other one buffered behind it
        in the same request), post an interruption note, and clear the pending state."""
        session = self._create_ai_session(self.agent)
        mocked_responses = [
            [
                *self.mock_tool_response(self.tool, {'value': "val1"}),
                *self.mock_tool_response(self.tool_w_confirm, {'value': "val2"}),
                *self.mock_tool_response(self.tool, {'value': "val3"}),
            ]
        ]
        with (
            self.mock_callback_completions(mocked_responses),
            self.mock_default_tools(self.tool | self.tool_w_confirm),
        ):
            self._post_user_message_on_session(session, "hey")

        self.assertEqual(session.pending_tool_call['call_id'], 2)
        previous_events = session.event_ids
        session._abort_pending_tools()
        tool_results_event = session.event_ids - previous_events
        self.assertEqual(len(tool_results_event), 1)
        self.assertFalse(session.pending_tool_call)
        # every tool call (buffered + remaining) should be reflected in the session history
        refusal = (
            'Error: The user chose not to proceed with this. Do not attempt it again unless '
            'they bring it up themselves.'
        )
        self._assert_tool_result_texts(
            tool_results_event,
            [(1, 'done', True), (2, refusal, False), (3, refusal, False)],
        )
        # the interruption note should be posted in the channel
        self.assertIn("Skipped", session.channel_id.message_ids[0].body)

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_search_tool_raises_for_blocked_model(self):
        """The AI search tool should raise an error when called with a blocked model like 'ir.config_parameter'."""
        search_tool = self.env.ref('ai.ir_actions_server_search')
        self.agent.skill_ids = self.env.ref('ai.ai_skill_information_retrieval_query')
        session = self._create_ai_session(self.agent)

        load_skills = self.mock_tool_response(
            self.skill_loading_tool,
            {"skill_ids": self.agent.skill_ids.ids},
        )
        blocked_search = self.mock_tool_response(
            search_tool,
            {'model_name': 'ir.config_parameter', 'domain': '[]', 'fields': ['key']},
        )
        with self.mock_callback_completions([
            load_skills,
            self.mock_text_response("skills enabled"),
            blocked_search,
            self.mock_text_response("I cannot do that."),
        ]):
            self._post_user_message_on_session(session, "Load skills")
            self._post_user_message_on_session(session, "Get all ir.config_parameter records")

        self.assertIn(
            "ir.config_parameter cannot be used by AI Agents",
            self._get_tool_result(session, blocked_search[0]['call_id'])['result'][0]['text'],
        )

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_read_group_tool_raises_for_blocked_model(self):
        """The AI search tool should raise an error when called with a blocked model like 'ir.config_parameter'."""
        rg_tool = self.env.ref('ai.ir_actions_server_read_group')
        self.agent.skill_ids = self.env.ref('ai.ai_skill_information_retrieval_query')
        session = self._create_ai_session(self.agent)

        load_skills = self.mock_tool_response(
            self.skill_loading_tool,
            {"skill_ids": self.agent.skill_ids.ids},
        )
        blocked_read_group = self.mock_tool_response(
            rg_tool,
            {'model_name': 'ir.config_parameter', 'domain': '[]'},
        )
        with self.mock_callback_completions([
            load_skills,
            self.mock_text_response("skills enabled"),
            blocked_read_group,
            self.mock_text_response("I cannot do that."),
        ]):
            self._post_user_message_on_session(session, "Load skill")
            self._post_user_message_on_session(session, "Get all ir.config_parameter records")

        self.assertIn(
            "ir.config_parameter cannot be used by AI Agents",
            self._get_tool_result(session, blocked_read_group[0]['call_id'])['result'][0]['text'],
        )

    def test_restrict_to_sources_option(self):
        session = self._create_ai_session(self.agent_with_sources)
        config = {
            "enable_web_search": False,
            "enable_resources_only": True
        }

        with (
            self.mock_callback_completions([
                self.mock_text_response("1"),
                self.mock_text_response("2"),
            ]) as request,
            self.mock_embedding_request(),
        ):
            self._post_user_message_on_session(session, "3", ai_session_config=config)
            config["enable_resources_only"] = False
            self._post_user_message_on_session(session, "4", ai_session_config=config)

        self.assertIn(dedent(RESTRICT_TO_SOURCES), request.call_args_list[0].args[2]['instructions'])
        self.assertNotIn(dedent(RESTRICT_TO_SOURCES), request.call_args_list[1].args[2]['instructions'])

    def test_think_longer_option(self):
        session = self._create_ai_session(self.agent)

        with (
            self.mock_callback_completions([
                self.mock_text_response("1"),
                self.mock_text_response("2"),
            ]) as request,
            self.mock_embedding_request(),
        ):
            self._post_user_message_on_session(session, "3", ai_session_config={"enable_think_longer": True})
            self._post_user_message_on_session(session, "4", ai_session_config={"enable_think_longer": False})

        self.assertTrue(request.call_args_list[0].args[2]['boost_reasoning'])
        self.assertFalse(request.call_args_list[1].args[2]['boost_reasoning'])

    def test_websearch_option(self):
        session = self._create_ai_session(self.agent)
        search_tool = self.env.ref("ai.ir_actions_server_ai_web_search")

        def post_message_and_get_tool_names(enable_web_search):
            with (
                self.mock_callback_completions([self.mock_text_response("1")]) as request,
                self.mock_embedding_request(),
            ):
                self._post_user_message_on_session(
                    session, "3", ai_session_config={"enable_web_search": enable_web_search}
                )

            return [tool["name"] for tool in request.call_args_list[0].args[2]["tools"]]

        tool_names = post_message_and_get_tool_names(True)
        self.assertIn(search_tool.ai_tool_name, tool_names)

        tool_names = post_message_and_get_tool_names(False)
        self.assertNotIn(search_tool.ai_tool_name, tool_names)
