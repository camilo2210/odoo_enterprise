from odoo.tests import tagged
from odoo.addons.sign.tests.sign_request_common import SignRequestCommon
from odoo.addons.project.tests.test_project_base import TestProjectCommon


@tagged('post_install', '-at_install')
class TestDocumentsSignProject(TestProjectCommon, SignRequestCommon):
    def test_sign_attachment_uses_project_folder(self):
        project = self.project_pigs
        task = self.task_1

        task_sign_request = self.create_sign_request_1_role(self.partner_1, self.env["res.partner"])
        task_sign_request.reference_doc = f'project.task,{task.id}'

        project_sign_request = self.create_sign_request_1_role(self.partner_1, self.env["res.partner"])
        project_sign_request.reference_doc = f'project.project,{project.id}'

        task_attachment, project_attachment = self.env['ir.attachment'].create([
            {
                'name': 'signed_task.pdf',
                'raw': self.pdf_value,
                'res_model': 'sign.request',
                'res_id': task_sign_request.id,
            },
            {
                'name': 'signed_project.pdf',
                'raw': self.pdf_value,
                'res_model': 'sign.request',
                'res_id': project_sign_request.id,
            },
        ])

        for attachment in (task_attachment, project_attachment):
            self.assertEqual(
                attachment.get_documents_operation_add_destination(),
                {
                    'destination': str(project.documents_folder_id.id),
                    'display_name': project.documents_folder_id.display_name,
                }
            )
