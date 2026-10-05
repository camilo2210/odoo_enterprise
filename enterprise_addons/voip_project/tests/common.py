from odoo.addons.project.tests.test_project_base import TestProjectCommon


class TestVoipProjectCommon(TestProjectCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_partner = cls.env["res.partner"].create({
            "name": "we are family",
            "phone": "+1233211234567",
        })
        (cls.task_1 | cls.task_2).partner_id = cls.partner_1
        (cls.partner_1 | cls.partner_2 | cls.partner_3).parent_id = cls.parent_partner
