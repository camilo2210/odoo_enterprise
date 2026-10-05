import json
import psycopg2
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger
from odoo.addons.ai.tests.common import TestAICommon
from odoo.addons.ai.models.ai_session import _logger as tool_logger


@tagged('post_install', '-at_install')
class TestAiServerActions(TestAICommon):
    def test_ai_server_action_access(self):
        """Test that the group check is skipped on the tool, but not on the AI action."""
        user = new_test_user(
            self.env, "internal_user_ai", "base.group_user,base.group_partner_manager",
        )
        partner = self.env["res.partner"].create({"name": "Partner"})
        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "ai",
                "name": "Test",
                "ai_tool_ids": [Command.create({
                    "model_id": self.env["ir.model"]._get_id("res.partner"),
                    "state": "code",
                    "name": "Write Name",
                    "ai_tool_name": "write_name",
                    "use_in_ai": True,
                    "code": "record.write({'name': value})",
                    "group_ids": self.env.ref("base.group_system").ids,
                })],
                "ai_action_prompt": "Main Prompt",
            },
        )

        # Check that we skip the group check on the tools
        with self.mock_completion_request([self.mock_text_response("done")]) as mock_request:
            action.with_user(user).with_context(active_id=partner.id, active_model='res.partner').run()
        self.assertEqual(mock_request.call_count, 1)

        # But not on the AI action
        action.group_ids = self.env.ref("base.group_system").ids

        with self.mock_completion_request([self.mock_text_response("done")]) as mock_request, self.assertRaises(AccessError):
            action.with_user(user).with_context(active_id=partner.id, active_model='res.partner').run()
        self.assertEqual(mock_request.call_count, 0)

    def test_ai_server_action_user_access(self):
        user = self.user_internal
        partner = self.env["res.partner"].create({"name": "Partner"})

        # Remove res.partner read access from the user
        access_records = self.env['ir.access'].search([
            ('model_id.model', '=', 'res.partner'),
            ('group_id', 'in', user.all_group_ids.ids)
        ])
        for access_record in access_records:
            if access_record.operation == 'r':
                access_record.for_create = True  # operation cannot be empty
            access_record.for_read = False
        search_tool = self.env.ref('ai.ir_actions_server_search').with_user(user).sudo()

        # openAI format for now, change to test_model?
        mocked_responses = [
            self.mock_tool_response(search_tool, {"model_name": "res.partner", "domain": json.dumps([["id", "=", partner.id]]), "fields": ["name"]}),
            self.mock_text_response("Unable to fetch partner details due to access rights"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request, \
            self.assertLogs(tool_logger, level='WARNING') as mock_tool_logger:
            message_parts = [{'type': 'text', 'content': {'data': 'message'}}]
            self.env['ai.session'].with_user(user)._get_direct_response('instructions', message_parts, tools=search_tool)
        self.assertEqual(mock_request.call_count, 2)

        # Single error log stating the user cannot access the records
        (error_log_record,) = mock_tool_logger.records
        self.assertIn(
            "The model 'res.partner' doesn't exist or is inaccessible to the current user",
            error_log_record.msg,
        )

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_ai_server_action_ai_tool(self):

        partner = self.env["res.partner"].create({"name": "Partner"})
        tools = self.env["ir.actions.server"].create([{
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Return Value",
            "ai_tool_name": "return_value",
            "use_in_ai": True,
            "code": "ai['result'] = 133333337",
        }, {
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Write Name",
            "ai_tool_name": "write_name",
            "use_in_ai": True,
            "code": "record.write({'name': value})",
            # Ensure schema validation is triggered during _ai_tool_run
            "ai_tool_schema": json.dumps({
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }),
        }])
        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "ai",
                "name": "Test",
                "ai_tool_ids": tools.ids,
                "ai_action_prompt": "Main Prompt",
            },
        )

        mocked_responses = [
            self.mock_tool_response(tools[0], {}),
            self.mock_tool_response(tools[1], {'value': 'new name'}),
            self.mock_text_response("Done"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(mock_request.call_count, 3)
        self.assertEqual(partner.name, "new name")

        # Simulate the LLM answering a forbidden action (not in the tools)
        bad_tool = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Bad Action",
            "ai_tool_name": "bad_action",
            "use_in_ai": True,
            "code": "record.write({'name': 'bad'})",
        })

        mocked_responses = [
            self.mock_tool_response(bad_tool),
            self.mock_text_response("Failed"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(partner.name, "new name", "Should not execute the action because it's not listed in the tools")

        def _patched_can_execute_action_on_records(*__):
            raise AccessError("")

        with (
            patch.object(
                self.env.registry["ir.actions.server"],
                "_can_execute_action_on_records",
                _patched_can_execute_action_on_records,
            ),
            self.assertRaises(AccessError),
        ):
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        # Check that if we mark a tool as "not used with AI" we don't send it
        # to the LLM even if the m2m relation still exist
        tools[1].use_in_ai = False
        partner.name = 'name'

        mocked_responses = [
            self.mock_tool_response(tools[1], {'value': 'new name'}),
            self.mock_text_response("Done"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(partner.name, "name", "The action is disabled and should not be executed")

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_ai_server_action_ai_interactive_tool(self):
        """Check that we raise an error for interactive tools."""

        partner = self.env["res.partner"].create({"name": "Partner"})

        ir_action_tool = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "code",
                "name": "Return Value",
                "ai_tool_name": "return_value",
                "use_in_ai": True,
                # The action tries to open a window action
                "code": """action = {
                "type": "ir.actions.act_window",
                "res_model": "res.partner",
                "target": "new",
            }
            """,
            },
        )

        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "ai",
                "name": "Test",
                "ai_tool_ids": ir_action_tool.ids,
                "ai_action_prompt": "Main Prompt",
            },
        )

        mocked_responses = [
            self.mock_tool_response(ir_action_tool),
            self.mock_text_response("Done")
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(mock_request.call_count, 2)
        self.assertIn(
            "This action is interactive and cannot be executed by the agent.",
            "".join(partner.message_ids.mapped("body")),
            "Should log the error on the partner",
        )

    def test_ai_create_activity(self):
        # check that activities can be created from an AI action
        create_activity_action = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'next_activity',
            'name': 'create activity',
            'ai_tool_name': 'create_activity',
            'use_in_ai': True,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'activity_note': 'created by AI',
        })
        ai_action = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'ai',
            'name': 'call create activity',
            'ai_action_prompt': 'create an activity',
            'ai_tool_ids': create_activity_action.ids,
        })

        mocked_responses = [
            self.mock_tool_response(create_activity_action),
            self.mock_text_response("Done")
        ]
        with self.mock_completion_request(mocked_responses):
            ai_action._ai_action_run(self.env.user.partner_id)
        self.assertIn('created by AI', self.env.user.partner_id.activity_ids[0].note)

    def test_ai_send_mail(self):
        partner_model_id = self.env['ir.model']._get_id('res.partner')
        send_mail_action = self.env['ir.actions.server'].create({
            'model_id': partner_model_id,
            'state': 'mail_post',
            'name': 'send mail',
            'ai_tool_name': 'send_mail',
            'use_in_ai': True,
            'template_id':  self.env['mail.template'].create({
                'name': 'Test template',
                'model_id': partner_model_id,
                'subject': 'mail sent by AI',
            }).id,
        })
        ai_action = self.env['ir.actions.server'].create({
            'model_id': partner_model_id,
            'state': 'ai',
            'name': 'send mail',
            'ai_action_prompt': 'send an email',
            'ai_tool_ids': send_mail_action.ids,
        })

        mocked_responses = [
            self.mock_tool_response(send_mail_action),
            self.mock_text_response("Done"),
        ]

        with self.mock_completion_request(mocked_responses):
            ai_action._ai_action_run(self.env.user.partner_id)

        # check that the mail has been created
        self.assertTrue(any(msg.subject == 'mail sent by AI' for msg in self.env.user.partner_id.message_ids))

    def test_ai_tool_name_required_with_use_in_ai(self):
        self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'code',
            'name': 'Test Tool',
            'use_in_ai': False,
            'code': "ai['result'] = True",
        })
        self.assertTrue(self.env['ir.actions.server'].search([('name', '=', 'Test Tool'), ('use_in_ai', '=', False)]))

        with self.assertRaises(ValidationError):
            self.env['ir.actions.server'].create({
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'code',
                'name': 'Test Tool',
                'use_in_ai': True,
                'code': "ai['result'] = True",
            })

    def test_ai_tool_name_invalid_format(self):
        with self.assertRaises(ValidationError):
            self.env['ir.actions.server'].create({
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'code',
                'name': 'Test Tool',
                'ai_tool_name': 'bad name!',
                'use_in_ai': True,
                'code': "ai['result'] = True",
            })

    @mute_logger('odoo.sql_db')
    def test_raise_on_duplicate_ai_tool_name(self):
        self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'code',
            'name': 'Test Tool',
            'use_in_ai': True,
            'ai_tool_name': 'my_unique_tool',
            'code': "ai['result'] = True",
        })
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.env['ir.actions.server'].create({
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'code',
                'name': 'Test Tool 2',
                'use_in_ai': True,
                'ai_tool_name': 'my_unique_tool',
                'code': "ai['result'] = True",
            })
