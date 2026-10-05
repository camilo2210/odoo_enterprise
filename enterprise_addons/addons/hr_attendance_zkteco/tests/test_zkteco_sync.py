from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import ZktecoCommon


@tagged("post_install", "-at_install")
class TestZktecoSync(ZktecoCommon):
    def _create_transaction(self, txid, **vals):
        vals.setdefault("punch_datetime", datetime(2024, 1, 15, 9, 0))
        vals.setdefault("punch_type", "check_in")
        vals.setdefault("employee_id", self.employee.id)
        vals.setdefault("company_id", self.company.id)
        return self.env["zkteco.transactions"].create({"zkteco_transaction_id": txid, **vals})

    def test_fetch_maps_and_creates_transactions(self):
        with self._mock_zkteco(
            transactions=[
                self._punch_payload(9001, punch_state="0"),
                self._punch_payload(9002, punch_state="1", punch_time="2024-01-15 17:00:00"),
            ]
        ):
            self.env["zkteco.transactions"].with_user(self.manager).action_fetch_transactions()

        created = self.env["zkteco.transactions"].search(
            [("zkteco_transaction_id", "in", ["9001", "9002"])],
            order="zkteco_transaction_id",
        )

        self.assertRecordValues(
            created,
            [
                {
                    "zkteco_transaction_id": "9001",
                    "employee_id": self.employee.id,
                    "terminal_id": self.terminal.id,
                    "punch_type": "check_in",
                    "is_processed": False,
                },
                {
                    "zkteco_transaction_id": "9002",
                    "employee_id": self.employee.id,
                    "terminal_id": self.terminal.id,
                    "punch_type": "check_out",
                    "is_processed": False,
                },
            ],
        )

    def test_fetch_skips_already_imported_transactions(self):
        self._create_transaction("9001")
        with self._mock_zkteco(
            transactions=[
                self._punch_payload(9001),
                self._punch_payload(9002),
            ]
        ):
            self.env["zkteco.transactions"].with_user(self.manager).action_fetch_transactions()

        self.assertEqual(
            self.env["zkteco.transactions"].search_count([("zkteco_transaction_id", "=", "9001")]),
            1,
            "The existing transaction must not be duplicated.",
        )
        self.assertTrue(self.env["zkteco.transactions"].search_count([("zkteco_transaction_id", "=", "9002")]))

    def test_fetch_requires_configuration(self):
        self.company.zkteco_server_url = False
        with self.assertRaises(UserError):
            self.env["zkteco.transactions"].with_user(self.manager).action_fetch_transactions()

    def test_cron_fetch_creates_transactions(self):
        with self._mock_zkteco(transactions=[self._punch_payload(9100)]):
            self.env["zkteco.transactions"]._cron_fetch_transactions()
        self.assertTrue(self.env["zkteco.transactions"].search_count([("zkteco_transaction_id", "=", "9100")]))

    def test_refetch_updates_transaction(self):
        tx = self._create_transaction("9200", punch_type="check_in", unmatched_checkout=True)
        with self._mock_zkteco(single=self._punch_payload(9200, punch_state="1", punch_time="2024-01-15 17:00:00")):
            tx.with_user(self.manager).action_refetch_transaction()

        self.assertRecordValues(tx, [{"punch_type": "check_out", "unmatched_checkout": False}])

    def test_refetch_blocked_when_linked_to_attendance(self):
        attendance = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": datetime(2024, 1, 15, 8, 0),
            }
        )
        tx = self._create_transaction("9300", is_processed=True, attendance_id=attendance.id)
        with self.assertRaises(UserError):
            tx.with_user(self.manager).action_refetch_transaction()

    def test_connection_initial_sync_unlocks_module(self):
        self.company.zkteco_initial_sync_done = False
        settings = self.env["res.config.settings"].with_user(self.manager).create({})
        with self._mock_zkteco(
            terminals=[{"sn": "SN-NEW", "alias": "Back Door"}],
            transactions=[self._punch_payload(9600)],
        ):
            result = settings.action_test_zkteco_connection()

        self.assertTrue(self.company.zkteco_initial_sync_done)
        self.assertTrue(self.env["zkteco.terminal"].search_count([("terminal_sn", "=", "SN-NEW")]))
        self.assertTrue(self.env["zkteco.transactions"].search_count([("zkteco_transaction_id", "=", "9600")]))
        self.assertEqual(result["params"]["next"]["tag"], "reload")
