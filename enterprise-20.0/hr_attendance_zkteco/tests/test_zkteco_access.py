from datetime import datetime

from odoo.exceptions import AccessError, RedirectWarning
from odoo.tests.common import tagged

from .common import ZktecoCommon


@tagged("post_install", "-at_install")
class TestZktecoAccess(ZktecoCommon):
    def test_fetch_requires_manager(self):
        with self.assertRaises(AccessError):
            self.env["zkteco.transactions"].with_user(self.basic_user).action_fetch_transactions()

    def test_refetch_requires_manager(self):
        tx = self.env["zkteco.transactions"].create(
            {
                "zkteco_transaction_id": "acc-1",
                "punch_datetime": datetime(2024, 1, 15, 9, 0),
                "punch_type": "check_in",
                "employee_id": self.employee.id,
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(AccessError):
            tx.with_user(self.basic_user).action_refetch_transaction()

    def test_views_blocked_until_initial_sync(self):
        self.company.zkteco_initial_sync_done = False
        for model in ("zkteco.transactions", "zkteco.terminal"):
            with self.assertRaises(RedirectWarning):
                self.env[model]._get_view()

    def test_views_available_after_initial_sync(self):
        self.company.zkteco_initial_sync_done = True
        for model in ("zkteco.transactions", "zkteco.terminal"):
            self.assertIsNotNone(self.env[model]._get_view())

    def test_menus_hidden_until_initial_sync(self):
        menu_tx = self.env.ref("hr_attendance_zkteco.zkteco_transactions_menu")
        menu_terminal = self.env.ref("hr_attendance_zkteco.zkteco_terminal_menu")
        IrUiMenu = self.env["ir.ui.menu"].with_user(self.basic_user)

        self.company.zkteco_initial_sync_done = False
        blacklist = IrUiMenu._load_menus_blacklist()
        self.assertIn(menu_tx.id, blacklist)
        self.assertIn(menu_terminal.id, blacklist)

        self.company.zkteco_initial_sync_done = True
        blacklist = IrUiMenu._load_menus_blacklist()
        self.assertNotIn(menu_tx.id, blacklist)
        self.assertNotIn(menu_terminal.id, blacklist)
