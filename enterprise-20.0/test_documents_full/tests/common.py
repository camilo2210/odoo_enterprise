from odoo.tests import TransactionCase, new_test_user

TEXT_DATA_ATTACHMENT_VALS = {
    "raw": b"documents_mixin",
    "name": "fileText_test.txt",
    "mimetype": "text/plain",
}


class TestDocumentsBridgeCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.user.company_id
        cls.company.documents_bridge_settings = True
        cls.bridge_folder = cls.env.ref("test_documents_full.documents_bridge_folder")
        cls.company.documents_bridge_folder_id = cls.bridge_folder
        cls.mixin_record = cls.env["documents.mixin.test.model"].create({
            "name": "Test Record",
            "company_id": cls.company.id,
        })
        cls.internal_user = new_test_user(cls.env, "internal_user")
        cls.MIXIN_RECORD_RES_VALS = {
            "res_model": "documents.mixin.test.model",
            "res_id": cls.mixin_record.id,
        }
