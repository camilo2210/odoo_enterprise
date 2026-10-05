from odoo.addons.project.tests.test_project_base import TestProjectCommon


class TestDocumentsProject(TestProjectCommon):
    def test_renaming_projects_updates_document_folder_names(self):
        projects = self.project_pigs + self.project_goats
        projects.write({'name': 'sheeps'})
        self.assertEqual(projects.documents_folder_id.mapped('name'), ['sheeps', 'sheeps'])
