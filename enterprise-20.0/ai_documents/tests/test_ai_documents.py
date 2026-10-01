import base64

from odoo.exceptions import AccessError
from odoo.tests import tagged, Form, users
from odoo.tools import mute_logger

from odoo.addons.ai_documents.tests.test_common import TestAiDocumentsCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestAiDocuments(TestAiDocumentsCommon):
    def test_ai_documents_access(self):
        """Test that only an admin can change the prompt of a folder."""
        with self.assertRaises(AccessError):
            self.env['documents.document'].with_user(self.user_internal).create({'ai_sort_prompt': 'test', 'type': 'folder'})

        folder = self.env['documents.document'].with_user(self.user_internal).sudo().create({'ai_sort_prompt': 'test', 'type': 'folder'}).sudo(False)

        with self.assertRaises(AccessError):
            folder.ai_sort_prompt = 'test 2'

    @mute_logger("odoo.addons.ai.models.ai_session", "odoo.addons.ai.models.ir_actions_server", "odoo.addons.ai_documents.models.ir_actions_server")
    def test_ai_documents_sort(self):
        """Test the "Auto-sort" flow using tools."""
        Doc = self.env['documents.document']

        # Check that we write the prompt on the source folder
        self.assertIn('data-ai-record-id', self.folder.ai_sort_prompt)
        self.assertIn(str(self.target_folder.id), self.folder.ai_sort_prompt)
        self.assertIn('data-ai-field="name"', self.folder.ai_sort_prompt)
        self.assertFalse(self.target_folder.ai_sort_prompt)

        automation_rule = self.env["base.automation"].search([("ai_autosort_folder_id", "=", self.folder.id)])
        self.assertEqual(len(automation_rule), 1)
        self.assertEqual(len(automation_rule.action_server_ids), 1)

        # Should create an action of type `ai`, that will render the `ai_sort_prompt` of the source folder
        self.assertEqual(automation_rule.action_server_ids.state, "ai")
        self.assertEqual(automation_rule.filter_domain, repr([("folder_id", "=", self.folder.id), ("ai_sortable", "=", True)]))
        self.assertEqual(automation_rule.trigger, "on_create_or_write")
        self.assertIn("Here is a document called ", automation_rule.action_server_ids.ai_action_prompt)
        ai_tool_ids = automation_rule.action_server_ids.ai_tool_ids
        self.assertEqual(len(ai_tool_ids), 3, "Should have the `multi` type action, the `move in folder` action, and the `rename` file action.")

        # That `ai` action has the tools we set on the wizard
        move_in_folder = self.env.ref("ai_documents.ir_actions_server_move_in_folder")
        rename_file = self.env.ref("ai_documents.ir_actions_server_rename_file")
        self.assertEqual(self.ir_action_tool | move_in_folder | rename_file, ai_tool_ids)
        self.assertTrue(all(ai_tool_ids.mapped("use_in_ai")))

        mocked_responses = [
            self.mock_tool_response(self.ir_action_tool, {'new_name': 'new name'}),
            self.mock_tool_response(move_in_folder, {'folder_id': self.target_folder.id}),
            self.mock_tool_response(rename_file, {'name': "ai_document"}),
            self.mock_text_response("Done")
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "Document Name",
                "type": "binary",
                "raw": base64.b64decode("VGVzdCBmaWxl"),
            })

        # check that actions were done
        self.assertTrue(document.ai_sortable)
        self.assertTrue(Doc.search([("id", "=", document.id), ("ai_sortable", "=", True)]))
        self.assertEqual(document.name, "ai_document")
        self.assertEqual(document.folder_id, self.target_folder)
        self.assertEqual(mock_request.call_count, 4)

        # check values sent to the api
        request_args = mock_request.call_args.args
        self.assertEqual(len(request_args[2]), len(ai_tool_ids))
        user_message = request_args[0][0]['content'][0]['text']
        self.assertIn("Here is a document called", user_message)
        self.assertIn("Execute the action then move", user_message)
        self.assertIn("Document Name", user_message)
        # check document is sent too
        self.assertIn("Test file", request_args[0][0]['content'][-1]['text'])
        # check tool calls and responses are included
        self.assertEqual(len(request_args[0]), 7)
        self.assertEqual(request_args[0][1], {'role': 'assistant', 'content': mocked_responses[0], 'provider_metadata': {}})
        self.assertEqual(request_args[0][2], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_name': self.ir_action_tool.ai_tool_name,
                'tool_call_id': 1,
                'result': [{'type': 'text', 'text': 'action return value'}],
                'success': True,
            }]
        })
        self.assertEqual(request_args[0][3], {'role': 'assistant', 'content': mocked_responses[1], 'provider_metadata': {}})
        self.assertEqual(request_args[0][4], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_name': move_in_folder.ai_tool_name,
                'tool_call_id': 2,
                'result': [{'type': 'text', 'text': 'Moved to "Target Folder".'}],
                'success': True,
            }]
        })
        self.assertEqual(request_args[0][5], {'role': 'assistant', 'content': mocked_responses[2], 'provider_metadata': {}})
        self.assertEqual(request_args[0][6], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_name': rename_file.ai_tool_name,
                'tool_call_id': 3,
                'result': [{'type': 'text', 'text': 'Renamed "new name" to "ai_document".'}],
                'success': True,
            }]
        })

        # Check that we don't try to auto-sort non-sortable document

        with self.mock_completion_request([]) as mock_request:
            Doc.create({
                "folder_id": self.folder.id,
                "name": "test",
                "type": "folder",
            })
        self.assertEqual(mock_request.call_count, 0)

        # Try to create a loop between 2 folders (if the target folder is also "Sort With AI")
        mocked_responses = [
            self.mock_tool_response(move_in_folder, {'folder_id': self.target_folder.id}),
            self.mock_text_response("Done"),
            self.mock_tool_response(move_in_folder, {'folder_id': self.folder.id}),
            self.mock_text_response("Done"),
            self.mock_tool_response(move_in_folder, {'folder_id': self.target_folder.id}),
            self.mock_text_response("Done"),
        ]

        sort_wizard = Form(self.env['ai_documents.sort'].with_context(default_folder_id=self.target_folder.id))
        sort_wizard.ai_sort_prompt = f"Target folder prompt: move in {Doc._ai_folder_insert(self.folder.id)}"
        sort_wizard.ai_tool_ids.add(self.ir_action_tool)
        sort_wizard.save().action_setup_folder()
        self.env['base.automation']._unregister_hook()
        self.env['base.automation']._register_hook()

        with self.mock_completion_request(mocked_responses) as mock_request:
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "test",
                "type": "binary",
                "raw": base64.b64decode("VGVzdCBmaWxl"),
            })

        self.assertTrue(document.ai_sortable)
        self.assertTrue(Doc.search([("id", "=", document.id), ("ai_sortable", "=", True)]))
        self.assertEqual(mock_request.call_count, 4, "All automation rules can be executed once")
        self.assertEqual(document.folder_id, self.folder)
        self.assertEqual(document.name, "test")

        # Re-test the exact same flow, but this time the LLM return a folder not in the prompt for some reason
        mocked_responses = [
            self.mock_tool_response(move_in_folder, {'folder_id': self.other_folder.id}),
            self.mock_text_response("Tool unknown"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            doc = Doc.create({
                "folder_id": self.folder.id,
                "name": "Document Name",
                "type": "binary",
                "raw": base64.b64decode("VGVzdCBmaWxl"),
            })

        self.assertEqual(doc.folder_id, self.folder, "Silently ignore the error")
        self.assertIn(
            "This folder isn't specified in the prompt and cannot be used as target.",
            "".join(doc.message_ids.mapped("body")),
            "Should log the error on the document",
        )
        self.assertEqual(mock_request.call_count, 2)

        # Test that removing the prompt delete the automation rule
        # (we only left inserted records without instruction)
        self.env['ai_documents.sort'].create({
            'folder_id': self.folder.id,
            'ai_sort_prompt': Doc._ai_folder_insert(self.target_folder.id),
            'ai_tool_ids': self.ir_action_tool.ids,
        }).action_setup_folder()
        self.assertFalse(automation_rule.exists())
        self.assertFalse(automation_rule.action_server_ids.exists())

        shortcut = document.action_create_shortcut()
        self.assertFalse(shortcut.ai_sortable)
        self.assertFalse(Doc.search([("id", "=", shortcut.id), ("ai_sortable", "=", True)]))

        # Test the case where the LLM will execute a tool that will move the documents,
        # with any tools, and then try to move it with the "AI Move Document" tool (the second
        # folder won't have a prompt, and so it should take the folder linked to the action
        # and not to the document).
        ir_action_tool_first_move = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("documents.document"),
            "state": "code",
            "name": "Move",
            "code": "record.write({'folder_id': %i})" % self.other_folder.id,
        })

        mocked_responses = [
            self.mock_tool_response(ir_action_tool_first_move),
            self.mock_tool_response(move_in_folder, {'folder_id': self.target_folder.id}),
            self.mock_text_response("Done"),
        ]

        sort_wizard = Form(self.env['ai_documents.sort'].with_context(default_folder_id=self.folder.id))
        sort_wizard.ai_sort_prompt = f"Target folder prompt: move in {Doc._ai_folder_insert(self.target_folder.id)}"
        sort_wizard.ai_tool_ids.add(self.ir_action_tool)
        sort_wizard.ai_tool_ids.add(ir_action_tool_first_move)
        sort_wizard.save().action_setup_folder()
        self.env['base.automation']._unregister_hook()
        self.env['base.automation']._register_hook()

        with self.mock_completion_request(mocked_responses) as mock_request:
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "test",
                "type": "binary",
                "raw": base64.b64decode("VGVzdCBmaWxl"),
            })

        self.assertEqual(mock_request.call_count, 3)
        self.assertEqual(document.folder_id, self.target_folder)

        # Test document renaming with its name
        mocked_responses = [
            self.mock_tool_response(rename_file, {'name': 'document.txt'}),
            self.mock_tool_response(rename_file, {'name': ' '}),
            self.mock_tool_response(rename_file, {'name': 'new.pdf'}),
            self.mock_text_response("Done"),
        ]

        with self.mock_completion_request(mocked_responses) as mock_request:
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "document.txt",
                "type": "binary",
                "raw": base64.b64decode("VGVzdCBmaWxl"),
            })

        request_args = mock_request.call_args.args

        self.assertEqual(request_args[0][1], {'role': 'assistant', 'content': mocked_responses[0], 'provider_metadata': {}})
        self.assertEqual(request_args[0][2], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_name': rename_file.ai_tool_name,
                'tool_call_id': 10,
                'result': [{'type': 'text', 'text': 'File name already follows convention'}],
                'success': True,
            }]
        })
        self.assertEqual(request_args[0][3], {'role': 'assistant', 'content': mocked_responses[1], 'provider_metadata': {}})
        self.assertEqual(request_args[0][4], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_name': rename_file.ai_tool_name,
                'tool_call_id': 11,
                'result': [{'type': 'text', 'text': 'Error: Tool call failed: No name was provided'}],
                'success': False,
            }]
        })
        self.assertEqual(request_args[0][5], {'role': 'assistant', 'content': mocked_responses[2], 'provider_metadata': {}})
        self.assertEqual(request_args[0][6], {
            'role': 'user',
            'content': [{
                'type': 'tool_result',
                'tool_name': rename_file.ai_tool_name,
                'tool_call_id': 12,
                'result': [{'type': 'text', 'text': 'Renamed "document.txt" to "new.txt".'}],
                'success': True,
            }]
        })

        self.assertEqual(document.name, 'new.txt')

    @users('user_internal')
    def test_ai_documents_sort_manual_trigger(self):
        """Test that users can trigger auto-sort on their documents."""
        # disable the automation to be able to trigger it manually
        self.env["base.automation"].sudo().search([("ai_autosort_folder_id", "=", self.folder.id)]).active = False
        document = self.env['documents.document'].with_user(self.user_internal).sudo().create({
            "folder_id": self.folder.sudo().id,
            "name": "Document Name",
            "type": "binary",
            "raw": base64.b64decode("VGVzdCBmaWxl"),
        }).sudo(False)

        # The user cannot access the target folder,
        # but the name of the folder is still inserted in the prompt
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            self.target_folder.with_user(self.user_internal).name
        self.assertEqual(
            self.target_folder.with_user(self.user_internal).sudo().user_permission,
            'none',
        )
        self.assertEqual(
            self.target_folder.with_user(self.user_internal).sudo().display_name,
            'Restricted Folder',
        )
        move_in_folder = self.env.ref("ai_documents.ir_actions_server_move_in_folder")

        mocked_responses = [
            self.mock_tool_response(self.ir_action_tool, {'new_name': 'new name'}),
            self.mock_tool_response(move_in_folder, {'folder_id': self.target_folder.id}),
            self.mock_text_response("Done")
        ]
        with self.mock_completion_request(mocked_responses):
            document.action_ai_sort()
        self.assertEqual(document.folder_id, self.target_folder)
