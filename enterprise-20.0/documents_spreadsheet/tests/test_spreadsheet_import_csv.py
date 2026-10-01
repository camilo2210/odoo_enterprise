import json

from odoo.tests.common import tagged, HttpCase

from .common import SpreadsheetTestCommon
from odoo.tools import file_open, mute_logger


class SpreadsheetImportCSV(HttpCase, SpreadsheetTestCommon):
    def test_import_csv(self):
        folder = self.env["documents.document"].create({"name": "New folder", "type": "folder"})
        with file_open('documents_spreadsheet/tests/data/test.csv', 'rb') as f:
            document_csv = self.env['documents.document'].create({
                'raw': f.read(),
                'name': 'test.csv',
                'mimetype': 'text/csv',
                'folder_id': folder.id
            })
            with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
                spreadsheet = document_csv._import_to_spreadsheet()
            self.assertTrue(spreadsheet.exists())
            self.assertEqual(spreadsheet.name, "test")
            expected_data = {
                "sheets": [
                    {
                        "cells": {
                            "A1": "1",
                            "B1": "Pamella",
                            "C1": "Piercy",
                            "D1": "ppiercy0@slashdot.org",
                            "A2": "2",
                            "B2": "Crissie",
                            "C2": "Narrie",
                            "D2": "cnarrie1@godaddy.com",
                            "A3": "3",
                            "B3": "Ruby",
                            "C3": "Smallcombe",
                            "D3": "rsmallcombe2@google.it",
                        },
                        "comments": {}
                    }
                ]
            }
            self.assertEqual(json.loads(spreadsheet.raw.content), expected_data)

    def test_import_csv_custom_separator(self):
        self.env = self.env(user=self.spreadsheet_user)
        folder = self.env["documents.document"].create({"name": "Test folder", "type": "folder"})
        csv_data = b"Name$Age$City\nAlice$30$New York\nBob$25$Los Angeles"
        csv_document = self.env['documents.document'].create({
            'raw': csv_data,
            'name': 'text.csv',
            'mimetype': 'text/csv',
            'folder_id': folder.id
        })
        wizard = self.env['documents.import.to.spreadsheet'].create({
            'document_id': csv_document.id,
            'csv_separator_type': 'custom',
            'csv_separator': '$',
        })
        action = wizard.import_to_spreadsheet()
        spreadsheet = self.env['documents.document'].browse(action['params']['spreadsheet_id'])
        expected_data = {
            "sheets": [
                {
                    "cells": {
                        "A1": "Name",
                        "B1": "Age",
                        "C1": "City",
                        "A2": "Alice",
                        "B2": "30",
                        "C2": "New York",
                        "A3": "Bob",
                        "B3": "25",
                        "C3": "Los Angeles",
                    },
                    "comments": {}
                }
            ]
        }
        self.assertEqual(json.loads(spreadsheet.raw.content), expected_data)

    def test_import_csv_forced_separator(self):
        self.env = self.env(user=self.spreadsheet_user)
        folder = self.env["documents.document"].create({"name": "Test folder", "type": "folder"})

        csv_data = b"Name;Age\nAlice\nBob;25"  # auto-detect fails to detect this pattern
        csv_document = self.env['documents.document'].create({
            'raw': csv_data,
            'name': 'text.csv',
            'mimetype': 'text/csv',
            'folder_id': folder.id
        })
        wizard = self.env['documents.import.to.spreadsheet'].create({
            'document_id': csv_document.id,
            'csv_separator_type': 'auto_detect',
            'archive_document': False,
        })
        action = wizard.import_to_spreadsheet()
        spreadsheet = self.env['documents.document'].browse(action['params']['spreadsheet_id'])
        expected_data = {
            "sheets": [
                {
                    "cells": {
                        "A1": "Name;Age",  # auto-detect fails
                        "A2": "Alice",
                        "A3": "Bob;25",
                    },
                    "comments": {}
                }
            ]
        }
        self.assertEqual(json.loads(spreadsheet.raw.content), expected_data)
        # Now force separator to ;
        wizard.csv_separator_type = 'semicolon'
        self.assertEqual(wizard.csv_separator, ';')
        action = wizard.import_to_spreadsheet()
        spreadsheet = self.env['documents.document'].browse(action['params']['spreadsheet_id'])
        expected_data = {
            "sheets": [
                {
                    "cells": {
                        "A1": "Name",
                        "B1": "Age",
                        "A2": "Alice",
                        "A3": "Bob",
                        "B3": "25",
                    },
                    "comments": {}
                }
            ]
        }
        self.assertEqual(json.loads(spreadsheet.raw.content), expected_data)

    def test_import_csv_keeps_linked_record(self):
        folder = self.env["documents.document"].create({"name": "New folder", "type": "folder"})
        partner = self.env["res.partner"].create({"name": "Linked partner"})
        with file_open('documents_spreadsheet/tests/data/test.csv', 'rb') as f:
            document_csv = self.env['documents.document'].create({
                'raw': f.read(),
                'name': 'test.csv',
                'mimetype': 'text/csv',
                'folder_id': folder.id,
                'res_model': 'res.partner',
                'res_id': partner.id,
            })
            with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
                spreadsheet = document_csv._import_to_spreadsheet()
        self.assertEqual(spreadsheet.res_model, 'res.partner')
        self.assertEqual(spreadsheet.res_id, partner.id)
        self.assertEqual(spreadsheet.attachment_id.res_model, 'res.partner')
        self.assertEqual(spreadsheet.attachment_id.res_id, partner.id)
