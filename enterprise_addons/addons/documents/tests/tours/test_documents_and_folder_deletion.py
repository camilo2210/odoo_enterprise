from odoo.tests import tagged
from odoo.tests.common import HttpCase
from odoo.addons.base.tests.files import GIF_RAW


@tagged("post_install", "-at_install")
class TestDocumentDeletion(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["documents.document"].create({
            "type": "folder",
            "name": "Folder1",
            "owner_id": False,
            "access_internal": "edit",
        })
        cls.document = cls.env['documents.document'].create({
            'raw': GIF_RAW,
            'name': "Chouchou",
            'folder_id': cls.folder.id,
            'mimetype': 'image/gif',
            'owner_id': False,
        })

    def test_delete_folder_and_documents_tour(self):
        folder_copy = self.folder
        document_copy = self.document
        self.start_tour(f"/odoo/documents/{self.document.access_token}", 'document_delete_tour', login='admin')
        self.assertTrue(folder_copy.exists(), "The folder should still exist")
        self.assertFalse(document_copy.exists(), "The document should not exist anymore")

    def test_tour_default_action_view(self):
        # todo: move to a more appropriate place in master
        self.document.active = False
        self.start_tour(
            f"/odoo/documents.document/{self.document.id}", 'document_default_access_view',
            login='admin'
        )
