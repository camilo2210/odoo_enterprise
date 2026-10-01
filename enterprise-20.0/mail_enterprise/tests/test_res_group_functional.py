# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mail.tests.common import MailCommon
from odoo.exceptions import AccessError
from odoo.tests.common import tagged


@tagged("-at_install", "post_install")
class TestResGroupFunctional(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env["res.group.functional"].create({"name": "Test Group"})

    def test_res_group_functional_add_responsible_member(self):
        """Test that we add the responsible in the members list."""
        self.group.user_ids = self.user_employee
        self.group.responsible_ids = self.user_admin
        self.assertEqual(self.group.user_ids, self.user_employee | self.user_admin)

    def test_res_group_functional_access_read(self):
        """Test that any internal user can read the group."""
        self.env.invalidate_all()
        self.assertEqual(self.group.with_user(self.user_employee).name, "Test Group")

        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            self.assertEqual(self.group.with_user(self._create_portal_user()).name, "Test Group")

    def test_res_group_functional_access_write(self):
        """Test that only the responsibles and the admin can write on the group."""
        with self.assertRaises(AccessError):
            self.group.with_user(self.user_employee).name = "test 1"

        self.group.responsible_ids = self.user_employee
        self.group.with_user(self.user_employee).name = "test 2"
        self.group.with_user(self.user_admin).name = "test 3"
