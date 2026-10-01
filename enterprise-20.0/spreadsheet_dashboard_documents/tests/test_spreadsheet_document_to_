import json

from odoo.tests.common import tagged, TransactionCase


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestSpreadsheetDocumentToDashboard(TransactionCase):
    def test_create_wizard(self):
        group = self.env["spreadsheet.dashboard.group"].create(
            {"name": "a group"}
        )
        document = self.env["documents.document"].create(
            {
                "name": "a document",
                "spreadsheet_data": r'{"sheets": []}',
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        wizard = self.env["spreadsheet.document.to.dashboard"].create(
            {
                "name": "a dashboard",
                "document_id": document.id,
                "dashboard_group_id": group.id,
                "group_ids": self.env.ref("documents.group_documents_user"),
                "spreadsheet_data": document.spreadsheet_data,
            }
        )
        next_action = wizard.create_dashboard()
        dashboard_id = next_action["params"]["dashboard_id"]
        dashboard = self.env["spreadsheet.dashboard"].browse(dashboard_id)
        self.assertEqual(dashboard.name, "a dashboard")
        self.assertEqual(dashboard.group_ids, self.env.ref("documents.group_documents_user"))
        self.assertEqual(dashboard.dashboard_group_id, group)
        self.assertEqual(
            dashboard.spreadsheet_data,
            '{"sheets": []}',
        )
        self.assertEqual(
            next_action,
            {
                "type": "ir.actions.client",
                "tag": "action_spreadsheet_dashboard",
                "name": "a dashboard",
                "target": "main",
                "params": {
                    "dashboard_id": dashboard_id,
                },
            },
        )

    def test_create_wizard_with_default_values(self):
        group = self.env["spreadsheet.dashboard.group"].create(
            {"name": "a group"}
        )
        document = self.env["documents.document"].create(
            {
                "name": "a document",
                "spreadsheet_data": r'{"sheets": []}',
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        wizard = self.env["spreadsheet.document.to.dashboard"].create(
            {
                "document_id": document.id,
                "dashboard_group_id": group.id,
                "spreadsheet_data": document.spreadsheet_data,
            }
        )
        next_action = wizard.create_dashboard()
        dashboard_id = next_action["params"]["dashboard_id"]
        dashboard = self.env["spreadsheet.dashboard"].browse(dashboard_id)
        self.assertEqual(dashboard.name, "a document")
        self.assertEqual(dashboard.group_ids, self.env.ref("base.group_user"))
        self.assertEqual(dashboard.dashboard_group_id, group)
        self.assertEqual(
            dashboard.spreadsheet_data,
            '{"sheets": []}',
        )
        self.assertEqual(
            next_action,
            {
                "type": "ir.actions.client",
                "tag": "action_spreadsheet_dashboard",
                "name": "a document",
                "target": "main",
                "params": {
                    "dashboard_id": dashboard_id,
                },
            },
        )

    def test_create_dashboard_and_archive_document(self):
        group = self.env["spreadsheet.dashboard.group"].create(
            {"name": "a group"}
        )
        document = self.env["documents.document"].create(
            {
                "name": "a document",
                "spreadsheet_data": r'{"sheets": []}',
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        wizard = self.env["spreadsheet.document.to.dashboard"].create(
            {
                "name": "a dashboard",
                "document_id": document.id,
                "dashboard_group_id": group.id,
                "group_ids": self.env.ref("documents.group_documents_user"),
                "spreadsheet_data": document.spreadsheet_data,
            }
        )
        wizard.create_dashboard()
        self.assertFalse(document.active, "The original document should be archived")

    def test_create_dashboard_uses_spreadsheet_data(self):
        group = self.env["spreadsheet.dashboard.group"].create(
            {"name": "a group"}
        )
        document = self.env["documents.document"].create(
            {
                "name": "a document",
                "spreadsheet_data": r'{"sheets": []}',
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        spreadsheet_data = json.dumps(
            {
                "sheets": [
                    {
                        "id": "sheet1",
                        "name": "Sheet1",
                        "cells": {"A1": "updated from wizard"},
                    }
                ]
            }
        )
        wizard = self.env["spreadsheet.document.to.dashboard"].create(
            {
                "name": "a dashboard",
                "document_id": document.id,
                "dashboard_group_id": group.id,
                "spreadsheet_data": spreadsheet_data,
            }
        )

        next_action = wizard.create_dashboard()
        dashboard = self.env["spreadsheet.dashboard"].browse(next_action["params"]["dashboard_id"])

        self.assertEqual(dashboard.spreadsheet_data, spreadsheet_data)

    def test_create_dashboard_wizard_moves_comments(self):
        group = self.env["spreadsheet.dashboard.group"].create(
            {"name": "a group"}
        )
        data = {
            "sheets": [{
                "comments": [
                    {"A1": {"threadId": 1, "isResolved": False}}
                ]
            }],
        }
        document = self.env["documents.document"].create(
            {
                "name": "a document",
                "spreadsheet_data": json.dumps(data),
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        thread = self.env["spreadsheet.cell.thread"].create([{"document_id": document.id}])
        wizard = self.env["spreadsheet.document.to.dashboard"].create(
            {
                "name": "a dashboard",
                "document_id": document.id,
                "dashboard_group_id": group.id,
                "group_ids": self.env.ref("documents.group_documents_user"),
                "spreadsheet_data": document.spreadsheet_data,
            }
        )
        next_action = wizard.create_dashboard()
        dashboard_id = next_action["params"]["dashboard_id"]
        dashboard = self.env["spreadsheet.dashboard"].browse(dashboard_id)

        self.assertEqual(document.spreadsheet_data, '{"sheets": [{"comments": {}}]}')
        self.assertEqual(thread.document_id.id, False)

        self.assertDictEqual(json.loads(dashboard.spreadsheet_data), data)
        self.assertEqual(thread.dashboard_id, dashboard)
