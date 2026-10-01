# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from .common import SpreadsheetTestCommon
from odoo.addons.base.tests.files import GIF_RAW
from odoo.exceptions import AccessError
from odoo.tests import tagged, Form
from odoo.tests.common import new_test_user
from odoo.tools import BinaryBytes, mute_logger

TEST_CONTENT = "{}"
GIF_VALUE = BinaryBytes(GIF_RAW)


class SpreadsheetDocuments(SpreadsheetTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["documents.document"].create({
            "name": "Test folder",
            "type": "folder",
            "access_internal": "edit",
        })

    def test_action_open_new_spreadsheet(self):
        action = self.env["documents.document"].action_open_new_spreadsheet()
        action_open = action
        spreadsheet_id = action_open["params"]["spreadsheet_id"]
        document = self.env["documents.document"].browse(spreadsheet_id)
        self.assertTrue(document.exists())
        self.assertEqual(document.handler, "spreadsheet")
        self.assertEqual(document.mimetype, "application/o-spreadsheet")
        self.assertEqual(document.name, "Untitled spreadsheet")
        self.assertEqual(document.raw.content, document._empty_spreadsheet_data_bin())
        self.assertEqual(action_open["type"], "ir.actions.client")
        self.assertEqual(action_open["tag"], "action_open_spreadsheet")

    def test_action_open_new_spreadsheet_with_locale(self):
        self.env["res.lang"].create(
            {
                "code": "en_FR",
                "name": "Custom Locale",
                "thousands_sep": " ",
                "decimal_point": ",",
                "date_format": "%d-%m-%Y",
                "time_format": "%H:%M:%S",
                "active": True,
                "week_start": "1",
            }
        )
        user = self.env['res.users'].create({
            "name": "Custom user",
            "login": "custom_user",
            "lang": "en_FR"
        })

        action = self.env["documents.document"].with_user(user).action_open_new_spreadsheet()
        spreadsheet_id = action["params"]["spreadsheet_id"]
        document = self.env["documents.document"].browse(spreadsheet_id)
        self.assertTrue(document.exists())

        expected_locale = {
            "code": "en_FR",
            "name": "Custom Locale",
            "thousandsSeparator": " ",
            "decimalSeparator": ",",
            "dateFormat": "dd-mm-yyyy",
            "timeFormat": "hh:mm:ss",
            "formulaArgSeparator": ";",
            "weekStart": 1,
            "digitGrouping": "[3,0]",
        }
        self.assertEqual(json.loads(document.spreadsheet_data)["settings"]["locale"], expected_locale)

    def test_action_open_new_spreadsheet_in_folder(self):
        action = self.env["documents.document"].action_open_new_spreadsheet({
            "folder_id": self.folder.id
        })
        spreadsheet_id = action["params"]["spreadsheet_id"]
        document = self.env["documents.document"].browse(spreadsheet_id)
        self.assertEqual(document.folder_id, self.folder)

    def test_action_update_access_rights(self):
        folder = self.env['documents.document'].create({'name': 'Folder', 'type': 'folder'})
        frozen_folder, document = self.env['documents.document'].create([
            {'name': 'Frozen Folder', 'type': 'folder', 'handler': 'frozen_folder', 'folder_id': folder.id},
            {'name': 'Document', 'folder_id': folder.id, 'raw': 'test'},
        ])
        frozen_spreadsheet = self.env['documents.document'].create({'name': 'Spreadsheet', 'handler': 'frozen_spreadsheet'})
        partner = self.env['res.partner'].create({'name': 'Partner'})

        # The update does not propagate on the frozen folders / spreadsheets
        folder.action_update_access_rights(access_internal='edit', partners={partner: ('edit', None)})
        self.assertEqual(folder.access_internal, 'edit')
        self.assertEqual(folder.access_ids.role, 'edit')
        self.assertEqual(document.access_internal, 'edit')
        self.assertEqual(document.access_ids.role, 'edit')
        self.assertEqual(frozen_folder.access_internal, 'none')
        self.assertFalse(frozen_folder.access_ids.role)
        self.assertEqual(frozen_spreadsheet.access_internal, 'none')
        self.assertFalse(frozen_spreadsheet.access_ids.role)

        folder.action_update_access_rights(access_internal='view', partners={partner: ('view', None)})
        self.assertEqual(folder.access_internal, 'view')
        self.assertEqual(folder.access_ids.role, 'view')
        self.assertEqual(document.access_internal, 'view')
        self.assertEqual(document.access_ids.role, 'view')
        self.assertEqual(frozen_folder.access_internal, 'none')
        self.assertFalse(frozen_folder.access_ids.role)
        self.assertEqual(frozen_spreadsheet.access_internal, 'none')
        self.assertFalse(frozen_spreadsheet.access_ids.role)

        frozen_folder.action_update_access_rights(access_internal='view', partners={partner: ('view', None)})
        self.assertEqual(frozen_folder.access_internal, 'view')
        self.assertEqual(frozen_folder.access_ids.role, 'view')
        self.assertEqual(frozen_spreadsheet.access_internal, 'none')
        self.assertFalse(frozen_spreadsheet.access_ids.role)

        frozen_spreadsheet.action_update_access_rights(access_internal='view', partners={partner: ('view', None)})
        self.assertEqual(frozen_spreadsheet.access_internal, 'view')
        self.assertEqual(frozen_spreadsheet.access_ids.role, 'view')

    def test_action_create_shortcut(self):
        self.archive_existing_spreadsheet()
        document = self.create_spreadsheet()
        shortcut = document.action_create_shortcut()
        self.assertEqual(shortcut.handler, "spreadsheet")

    def archive_existing_spreadsheet(self):
        """Existing spreadsheet in the database can influence some test results"""
        self.env["documents.document"].search([("handler", "=", "spreadsheet")]).active = False

    def test_spreadsheet_my_drive_folder(self):
        user1 = new_test_user(self.env, login="Alice", groups="base.group_user")

        document = self.env["documents.document"].with_user(user1).create({
            "spreadsheet_data": "{}",
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
        })
        self.assertFalse(document.folder_id, "The spreadsheet is created in My Drive")
        # And only user1 have access to it
        self.assertEqual(document.owner_id, user1)
        self.assertEqual(document.access_internal, 'none')
        self.assertEqual(document.access_via_link, 'none')
        self.assertFalse(document.access_ids.filtered(lambda a: a.partner_id != user1.partner_id))

    def test_spreadsheet_no_default_folder(self):
        """Folder is not overwritten by the default spreadsheet folder"""
        document = self.env["documents.document"].create({
            "spreadsheet_data": "{}",
            "folder_id": self.folder.id,
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
        })
        self.assertEqual(document.folder_id, self.folder, "It should be in the specified folder")

    def test_access_rights_inherited_on_create_spreadsheet(self):
        user = new_test_user(
            self.env, login='Jean', groups='documents.group_documents_user',
        )
        document_1 = self.env['documents.document'].create({
            'spreadsheet_data': '{}',
            'handler': 'spreadsheet',
            'mimetype': 'application/o-spreadsheet',
        })
        document_2 = self.env['documents.document'].create({
            'spreadsheet_data': '{}',
            'handler': 'spreadsheet',
            'folder_id': False,
            'mimetype': 'application/o-spreadsheet',
        })
        self.folder.write({
            'access_via_link': 'none',
            'access_internal': 'view',
        })
        self.folder.action_update_access_rights(partners={user.partner_id.id: ('view', False)})
        document_3 = self.env['documents.document'].create({
            'spreadsheet_data': '{}',
            'handler': 'spreadsheet',
            'folder_id': self.folder.id,
            'mimetype': 'application/o-spreadsheet',
        })

        # inherit access from parent folder (My Drive)
        self.assertFalse(document_1.folder_id, False)
        self.assertEqual(document_1.access_internal, 'none')
        self.assertEqual(document_1.access_via_link, 'none')

        # inherit access from parent folder (My Drive)
        self.assertEqual(document_2.access_internal, 'none')
        self.assertEqual(document_2.access_via_link, 'none')

        # inherit access from parent folder (Test folder)
        self.assertEqual(document_3.access_internal, 'view')
        self.assertEqual(document_3.access_via_link, 'none')
        self.assertEqual(document_3.access_ids.partner_id, user.partner_id)

    def test_spreadsheet_to_display_with_domain(self):
        self.archive_existing_spreadsheet()

        with self.mock_datetime_and_now("2020-02-03"):
            spreadsheet1 = self.create_spreadsheet(name="My Spreadsheet")
        with self.mock_datetime_and_now("2020-02-02"):
            spreadsheet2 = self.create_spreadsheet(name="Untitled Spreadsheet")
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([("name", "ilike", "My")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id])
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([("name", "ilike", "Untitled")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet2.id])
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([("name", "ilike", "Spreadsheet")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id, spreadsheet2.id])

    def test_spreadsheet_to_display_with_offset_limit(self):
        self.archive_existing_spreadsheet()
        user = new_test_user(self.env, login="Jean", groups="base.group_user")
        with self.mock_datetime_and_now("2020-02-02"):
            spreadsheet1 = self.create_spreadsheet(user=user, name="My Spreadsheet 1")
        with self.mock_datetime_and_now("2020-02-03"):
            spreadsheet2 = self.create_spreadsheet(user=user, name="My Spreadsheet 2")
        with self.mock_datetime_and_now("2020-02-04"):
            spreadsheet3 = self.create_spreadsheet(name="My Spreadsheet 3")
        with self.mock_datetime_and_now("2020-02-05"):
            spreadsheet4 = self.create_spreadsheet(user=user, name="SP 4")
        with self.mock_datetime_and_now("2020-02-06"):
            spreadsheet5 = self.create_spreadsheet(name="SP 5")
        with self.mock_datetime_and_now("2020-02-07"):
            spreadsheet6 = self.create_spreadsheet(name="SP 6")

        #########
        # ADMIN #
        #########

        # Only the last opened spreadsheet.
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([], offset=0, limit=1)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet6.id])

        # Two last opened spreadsheets.
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([], offset=0, limit=2)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet6.id, spreadsheet5.id])

        # Ordered first by last opened, and then by id.
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([], offset=2, limit=2)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet3.id, spreadsheet4.id])

        # Ordered first by last opened, and then by id without limit.
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([], offset=2)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet3.id, spreadsheet4.id, spreadsheet2.id, spreadsheet1.id])

        # Ordered first by last opened, and then by id without limit with a domain.
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([("name", "ilike", "My Spreadsheet")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet3.id, spreadsheet2.id, spreadsheet1.id])

        # Ordered first by last opened, and then by id without limit with a domain.
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([("name", "ilike", "SP ")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet6.id, spreadsheet5.id, spreadsheet4.id])

        ########
        # JEAN #
        ########

        # Only the last opened spreadsheet.
        spreadsheets = self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([], offset=0, limit=1)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet4.id])

        # Two last opened spreadsheets.
        spreadsheets = self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([], offset=0, limit=2)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet4.id, spreadsheet2.id])

        # Ordered first by last opened, and then by id.
        spreadsheets = self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([], offset=2, limit=2)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id, spreadsheet6.id])

        # Ordered first by last opened, and then by id without limit.
        spreadsheets = self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([], offset=2)
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id, spreadsheet6.id, spreadsheet5.id, spreadsheet3.id])

        # Ordered first by last opened, and then by id without limit with a domain.
        spreadsheets = self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([("name", "ilike", "My Spreadsheet")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet2.id, spreadsheet1.id, spreadsheet3.id])

        # Ordered first by last opened, and then by id without limit with a domain.
        spreadsheets = self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([("name", "ilike", "SP ")])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet4.id, spreadsheet6.id, spreadsheet5.id])

    def test_spreadsheet_to_display(self):
        self.archive_existing_spreadsheet()
        document = self.create_spreadsheet()
        archived_document = self.env["documents.document"].create(
            {
                "spreadsheet_data": r"{}",
                "folder_id": self.folder.id,
                "active": False,
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertTrue(
            document.id in spreadsheet_ids, "It should contain the new document"
        )
        self.assertFalse(
            archived_document.id in spreadsheet_ids,
            "It should not contain the archived document",
        )

    def test_spreadsheet_to_display_create_order(self):
        self.archive_existing_spreadsheet()
        with self.mock_datetime_and_now("2020-02-02 18:00"):
            spreadsheet1 = self.create_spreadsheet()
        with self.mock_datetime_and_now("2020-02-15 18:00"):
            spreadsheet2 = self.create_spreadsheet()
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet2.id, spreadsheet1.id])

    def test_spreadsheet_to_display_write_order(self):
        self.archive_existing_spreadsheet()
        with self.mock_datetime_and_now("2020-02-02 18:00"):
            spreadsheet1 = self.create_spreadsheet()
        with self.mock_datetime_and_now("2020-02-15 18:00"):
            spreadsheet2 = self.create_spreadsheet()
        spreadsheet1.spreadsheet_data = r"{}"
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id, spreadsheet2.id])

    def test_spreadsheet_to_display_join_session(self):
        self.archive_existing_spreadsheet()
        with self.mock_datetime_and_now("2020-02-02 18:00"):
            spreadsheet1 = self.create_spreadsheet()
        with self.mock_datetime_and_now("2020-02-15 18:00"):
            spreadsheet2 = self.create_spreadsheet()
        spreadsheet1._get_serialized_spreadsheet_data_body()
        spreadsheets = self.env["documents.document"]._get_spreadsheets_to_display([])
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id, spreadsheet2.id])

    def test_spreadsheet_to_display_without_contrib(self):
        self.archive_existing_spreadsheet()
        user = new_test_user(
            self.env, login="Jean", groups="documents.group_documents_user"
        )
        with self.mock_datetime_and_now("2020-02-02 18:00"):
            spreadsheet1 = self.create_spreadsheet(user=user)
        with self.mock_datetime_and_now("2020-02-15 18:00"):
            spreadsheet2 = self.create_spreadsheet()
        spreadsheets = (
            self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([])
        )
        spreadsheet_ids = [s["id"] for s in spreadsheets]
        self.assertEqual(spreadsheet_ids, [spreadsheet1.id, spreadsheet2.id])

    def test_spreadsheet_to_display_access_portal(self):
        portal = new_test_user(self.env, "Test user", groups="base.group_portal")
        with self.assertRaises(
            AccessError, msg="A portal user should not be able to read spreadsheet"
        ):
            self.env["documents.document"].with_user(
                portal
            )._get_spreadsheets_to_display([])

    def test_spreadsheet_to_display_access_ir_rule(self):
        user = new_test_user(
            self.env, "Test user", groups="documents.group_documents_manager"
        )

        model = self.env.ref("documents.model_documents_document")
        group = self.env.ref("documents.group_documents_manager")

        manager_doc = self.create_spreadsheet(user=user)
        visible_doc = self.create_spreadsheet(user=user)
        # archive existing record rules which might allow access (disjunction between record rules)
        self.env["ir.access"].search([("model_id", "=", model.id)]).active = False
        self.env["ir.access"].create({
            "name": "test record rule",
            "model_id": model.id,
            "group_id": group.id,
            "operation": "crud",
            "domain": f"[('id', '=', {visible_doc.id})]",  # always rejects
        })

        spreadsheets = (
            self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([])
        )
        self.assertEqual(
            [s["id"] for s in spreadsheets], [visible_doc.id], "filtering issue"
        )

        with self.assertRaises(AccessError, msg="record rule should have raised"):
            manager_doc.with_user(user).spreadsheet_data = "{}"

    def test_spreadsheet_to_display_access_field_groups(self):
        existing_groups = self.env["documents.document"]._fields["display_name"].groups
        self.env["documents.document"]._fields["display_name"].groups = "base.group_system"
        user = new_test_user(
            self.env, "Test user", groups="documents.group_documents_manager"
        )

        with self.assertRaises(AccessError, msg="field should be protected"):
            self.env["documents.document"].with_user(user)._get_spreadsheets_to_display([])
        self.env["documents.document"]._fields["display_name"].groups = existing_groups

    def test_save_template(self):
        context = {
            "default_spreadshee_name": "Spreadsheet test",
            "default_template_name": "Spreadsheet test - Template",
            "default_spreadsheet_data": TEST_CONTENT,
            "default_thumbnail": GIF_VALUE,
        }
        wizard = Form(
            self.env["save.spreadsheet.template"].with_context(context)
        ).save()
        wizard.save_template()
        template = self.env["spreadsheet.template"].search(
            [["name", "=", "Spreadsheet test - Template"]]
        )
        self.assertTrue(template, "It should have created a template")
        self.assertEqual(template.name, "Spreadsheet test - Template")
        self.assertEqual(template.spreadsheet_data, TEST_CONTENT)
        self.assertEqual(template.thumbnail.content, GIF_VALUE.content)

    def test_save_template_purges_comments(self):
        base_data = {
            "sheets": [{
                "comments": [
                    {"A1": {"threadId": 1, "isResolved": False}}
                ]
            }],
        }
        context = {
            "default_spreadshee_name": "Spreadsheet test",
            "default_template_name": "Spreadsheet test - Template",
            "default_spreadsheet_data": json.dumps(base_data),
            "default_thumbnail": GIF_VALUE,
        }
        wizard = Form(
            self.env["save.spreadsheet.template"].with_context(context)
        ).save()

        wizard.save_template()
        template = self.env["spreadsheet.template"].search(
            [["name", "=", "Spreadsheet test - Template"]]
        )
        template_data = json.loads(template.spreadsheet_data)
        self.assertEqual(template_data["sheets"][0]["comments"], {})

    def test_user_right_own_template(self):
        user = new_test_user(
            self.env, "Test user", groups="documents.group_documents_user"
        )
        template = (
            self.env["spreadsheet.template"]
            .with_user(user)
            .create(
                {
                    "name": "hello",
                    "spreadsheet_data": TEST_CONTENT,
                }
            )
        )
        template.write(
            {
                "name": "bye",
            }
        )
        template.unlink()

    def test_user_right_not_own_template(self):
        manager = new_test_user(
            self.env, "Test manager", groups="documents.group_documents_manager"
        )
        user = new_test_user(
            self.env, "Test user", groups="documents.group_documents_user"
        )
        template = (
            self.env["spreadsheet.template"]
            .with_user(manager)
            .create(
                {
                    "name": "hello",
                    "spreadsheet_data": TEST_CONTENT,
                }
            )
        )
        with self.assertRaises(
            AccessError, msg="cannot write on template of your friend"
        ):
            template.with_user(user).write(
                {
                    "name": "bye",
                }
            )
        with self.assertRaises(
            AccessError, msg="cannot delete template of your friend"
        ):
            template.with_user(user).unlink()
        template.name = "bye"
        template.unlink()

    def test_contributor_write_spreadsheet_data(self):
        document = self.create_spreadsheet()
        document.access_internal = "edit"
        user = new_test_user(
            self.env, "Test Manager", groups="documents.group_documents_manager"
        )
        document.with_user(user).write({"spreadsheet_data": r"{}"})
        contributor = self.env["spreadsheet.contributor"].search(
            [("user_id", "=", user.id), ("document_id", "=", document.id)]
        )
        self.assertEqual(len(contributor), 1, "The contribution should be registered")

    def test_contributor_move_folder(self):
        document = self.create_spreadsheet()
        new_folder = self.env["documents.document"].create({
            "name": "New folder",
            "type": "folder",
            "folder_id": self.folder.id,
            "access_internal": "edit",
        })
        user = new_test_user(
            self.env, "Test Manager", groups="documents.group_documents_manager"
        )
        document.access_internal = "edit"
        document.with_user(user).write({"folder_id": new_folder.id})
        contributor = self.env["spreadsheet.contributor"].search(
            [("user_id", "=", user.id), ("document_id", "=", document.id)]
        )
        self.assertEqual(
            len(contributor), 0, "The contribution should not be registered"
        )

    def test_document_replacement_with_handler(self):
        document = self.env["documents.document"].create({
            "spreadsheet_data": r"{}",
            "folder_id": self.folder.id,
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
        })
        vals = {
            "name": "file",
            "folder_id": self.folder.id,
            "spreadsheet_data": r"{}",
            "handler": "spreadsheet"
        }
        document.write(vals)
        self.assertEqual(document.handler, "spreadsheet", "The handler must contain the value of the handler mentioned in vals")

    def test_document_replacement_data_only(self):
        document = self.env["documents.document"].create({
            "name": "file",
            "spreadsheet_data": r"{}",
            "folder_id": self.folder.id,
            "handler": "spreadsheet",
        })
        vals = {
            "spreadsheet_data": r"{}",
        }
        document.write(vals)
        self.assertEqual(document.handler, "spreadsheet", "The handler should not have changed")

    def test_document_replacement_with_other_mimetype(self):

        document = self.env["documents.document"].create({
            "spreadsheet_data": r"{}",
            "folder_id": self.folder.id,
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
        })
        vals = {
            "name": "test.txt",
            "raw": b'hello!\n',
            "folder_id": self.folder.id,
            "mimetype": "text/plain",
        }
        document.write(vals)
        self.assertEqual(document.handler, False, "The handler should have been reset")

    def test_document_replacement_with_spreadsheet_mimetype(self):
        document = self.env["documents.document"].create({
            "raw": b'some text',
            "folder_id": self.folder.id,
            "mimetype": "text/plain",
        })
        vals = {
            "spreadsheet_data": r"{}",
            "mimetype": "application/o-spreadsheet",
        }
        document.write(vals)
        self.assertEqual(document.handler, False, "the file should not be recognized as a spreadsheet")

    def test_document_replacement_with_handler_and_other_mimetype(self):
        document = self.env["documents.document"].create({
            "spreadsheet_data": r"{}",
            "folder_id": self.folder.id,
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
        })
        vals = {
            "name": "spreadsheet_file",
            "folder_id": self.folder.id,
            "spreadsheet_data": r"{}",
            "mimetype": "application/json",
            "handler": "spreadsheet"
        }
        document.write(vals)
        self.assertEqual(document.handler, "spreadsheet", "the handler must contain the value of the handler mentioned in vals")

    def test_create_document_with_spreadsheet_mimetype(self):
        document = self.env["documents.document"].create({
            "spreadsheet_data": r"{}",
            "folder_id": self.folder.id,
            "mimetype": "application/o-spreadsheet",
        })
        self.assertEqual(document.handler, False, "the file should not be recognized as a spreadsheet")

    def test_read_spreadsheet_data(self):
        document = self.env["documents.document"].create({
            "name": "test.txt",
            "raw": b'{ "sheets": [] }',
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
            "folder_id": self.folder.id,
        })
        self.assertEqual(document.spreadsheet_data, '{ "sheets": [] }')

    def test_read_non_spreadsheet_data(self):
        document = self.env["documents.document"].create({
            "name": "test.txt",
            "raw": b"{}",
            "mimetype": "text/plain",
            "folder_id": self.folder.id,
        })
        self.assertFalse(document.spreadsheet_data)

    def test_write_spreadsheet_data(self):
        document = self.env["documents.document"].create({
            "name": "test.txt",
            "raw": b"{}",
            "handler": "spreadsheet",
            "mimetype": "application/o-spreadsheet",
            "folder_id": self.folder.id,
        })
        data = b'{ "sheets": [] }'
        document.spreadsheet_binary_data = BinaryBytes(data)
        self.assertEqual(document.raw.content, data)

    def test_copy_spreadsheet_revisions(self):
        spreadsheet = self.create_spreadsheet()
        user = new_test_user(self.env, login="Jean", groups="base.group_user")
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))

        #########
        # ADMIN #
        #########
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            copy_admin = spreadsheet.copy()
        self.assertEqual(
            len(copy_admin.spreadsheet_revision_ids),
            1,
            "The revision should be copied with admin access right",
        )

        #############
        # NON-ADMIN #
        #############
        spreadsheet.invalidate_recordset()
        copy_non_admin = spreadsheet.with_user(user).copy()
        self.assertEqual(
            len(copy_non_admin.sudo().spreadsheet_revision_ids),
            1,
            "The revision should be copied with non-admin access right",
        )

    def test_copy_spreadsheet_snapshot(self):
        spreadsheet = self.create_spreadsheet()
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid, "snapshot-revision-id", {"sheets": [], "revisionId": "snapshot-revision-id"},
        )
        with mute_logger('odoo.addons.documents.models.documents_document'):
            copy = spreadsheet.copy()
        self.assertEqual(
            copy.spreadsheet_snapshot.content,
            spreadsheet.spreadsheet_snapshot.content,
            "Copy should have the same snapshot data",
        )

    def test_copy_sheet_name(self):
        spreadsheet = self.create_spreadsheet({"name": "spreadsheet"})
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            copy = spreadsheet.copy()
        self.assertEqual(copy.name, 'spreadsheet (copy)')

    def test_copy_default_sheet_name(self):
        spreadsheet = self.create_spreadsheet({"name": "spreadsheet"})
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            copy = spreadsheet.copy({'name': 'sheet'})
        self.assertEqual(copy.name, 'sheet')

    def test_spreadsheet_thumbnail_checksum(self):
        spreadsheet = self.create_spreadsheet()
        self.assertFalse(spreadsheet.spreadsheet_thumbnail_checksum)
        spreadsheet.display_thumbnail = GIF_VALUE
        thumbnail_attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "documents.document"),
            ("res_field", "=", "thumbnail"),
            ("res_id", "=", spreadsheet.id),
        ])
        self.assertTrue(
            spreadsheet.spreadsheet_thumbnail_checksum,
            thumbnail_attachment.checksum
        )

    def test_spreadsheet_thumbnail_checksum_other_document(self):
        document = self.env["documents.document"].create({
            "raw": GIF_VALUE,
            "thumbnail": GIF_VALUE,
            "folder_id": self.folder.id,
        })
        self.assertFalse(document.spreadsheet_thumbnail_checksum)

    def test_get_only_spreadsheet_documents(self):
        self.env["documents.document"].search([("handler", "=", "spreadsheet")]).unlink()

        # a spreadsheet
        spreadsheet = self.create_spreadsheet()

        # a regular document
        self.env["documents.document"].create({
            "raw": GIF_VALUE,
            "thumbnail": GIF_VALUE,
            "folder_id": self.folder.id,
        })

        # a frozen spreadsheet
        frozen_spreadsheet = self.create_spreadsheet()
        frozen_spreadsheet.access_internal = "view"
        frozen_spreadsheet.handler = "frozen_spreadsheet"

        result = self.env["documents.document"].get_spreadsheets()
        self.assertEqual(result, {
            "records": [{
                "id": spreadsheet.id,
                "display_name": spreadsheet.name,
                "display_thumbnail": False
            }],
            "total": 1,
        })

    def test_spreadsheet_prevent_portal_owner(self):
        portal = new_test_user(self.env, "Test user", groups="base.group_portal")
        spreadsheet = self.create_spreadsheet()
        with self.assertRaises(
            AccessError, msg="Portal users cannot be the owner of a spreadsheet."
        ):
            spreadsheet.owner_id = portal
