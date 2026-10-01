# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.documents_hr.tests.test_documents_hr_common import TransactionCaseDocumentsHr
from odoo.tests.common import RecordCapturer, tagged
from datetime import date


@tagged('test_document_bridge')
class TestCaseDocumentsBridgeHR(TransactionCaseDocumentsHr):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Employee (related to doc_user)',
            'user_id': cls.doc_user.id,
            'work_contact_id': cls.doc_user.partner_id.id
        })
        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Sick',
            'code': 'Sick',
            'requires_allocation': False,
            'unit_of_measure': 'day',
        })
        cls.leave = cls.env['hr.leave'].create({
            'employee_id': cls.employee.id,
            'work_entry_type_id': cls.work_entry_type.id,
            'request_date_from': date(2021, 11, 24),
            'request_date_to': date(2021, 11, 24),
        })

    def test_leave_document_creation(self):
        attachment = self.env['ir.attachment'].create({
            'raw': self.TEXT_RAW,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': self.leave._name,
            'res_id': self.leave.id,
        })

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document.exists(), "There should be a new document created from the attachment")
        self.assertFalse(document.owner_id)
        self.assertEqual(document.access_via_link, "none")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)

    def test_leave_creation_with_attachment(self):
        with RecordCapturer(self.env['documents.document'], []) as capture:
            leave_id = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'work_entry_type_id': self.work_entry_type.id,
                'request_date_from': date(2026, 6, 1),
                'request_date_to': date(2026, 6, 1),
                'attachment_ids': [Command.create({
                    'raw': self.TEXT_RAW,
                    'name': 'fileText_test.txt',
                    'mimetype': 'text/plain',
                    'res_model': 'hr.leave',
                })],
            })
        document = capture.records.ensure_one()
        self.assertEqual(document.attachment_id.res_model, 'hr.leave')
        self.assertEqual(document.attachment_id.res_id, leave_id.id)
        self.assertEqual(document.res_model, 'hr.leave')
        self.assertEqual(document.res_id, leave_id.id)

    def test_leave_creation_with_existing_attachment(self):
        """This test simulates what happens when creating a leave in the calendar UI
        The attachment is created prior to the leave when adding one."""
        attachment_id = self.env['ir.attachment'].create({
            'raw': self.TEXT_RAW,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': 'hr.leave',
            'res_id': 0,
        })
        with RecordCapturer(self.env['documents.document'], []) as capture:
            leave_id = self.env['hr.leave'].create({
                'employee_id': self.employee.id,
                'work_entry_type_id': self.work_entry_type.id,
                'request_date_from': date(2026, 6, 1),
                'request_date_to': date(2026, 6, 1),
                'attachment_ids': [Command.set(attachment_id.ids)],
            })
        document = capture.records.ensure_one()
        self.assertEqual(document.attachment_id.res_model, 'hr.leave')
        self.assertEqual(document.attachment_id.res_id, leave_id.id)
        self.assertEqual(document.res_model, 'hr.leave')
        self.assertEqual(document.res_id, leave_id.id)

    def test_hr_leave_document_creation_permission_employee_only(self):
        """ Test that created hr.leave documents are only viewable by the employee and editable by hr managers. """
        self.check_document_creation_permission(self.leave)
