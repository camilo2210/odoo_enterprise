# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestSessionInfo(common.HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_password = "password"
        cls.user_no_right = common.new_test_user(
            cls.env,
            "user_no_right",
            email="user_no_right@example.com",
            password=cls.user_password,
            tz="UTC")

        cls.user_with_right = common.new_test_user(
            cls.env,
            "user_with_right",
            email="user_with_right@example.com",
            password=cls.user_password,
            tz="UTC",
            groups="sales_team.group_sale_manager")

    def test_session_info_can_insert_in_spreadsheet(self):
        cases = [
            (self.user_no_right, False),
            (self.user_with_right, True),
        ]
        for user, expected in cases:
            with self.subTest(user=user.login):
                self.authenticate(user.login, self.user_password)
                session_info = self.make_jsonrpc_request("/web/session/get_session_info")
                self.assertEqual(
                    session_info["can_insert_in_spreadsheet"],
                    expected,
                    f"The session_info['can_insert_in_spreadsheet'] should be {expected}",
                )
