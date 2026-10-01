from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from odoo.exceptions import UserError
from odoo.tests.common import freeze_time, tagged

from .common import ZktecoCommon


@tagged("post_install", "-at_install")
class TestZktecoTransactions(ZktecoCommon):
    def _create_transaction(self, **vals):
        vals.setdefault("zkteco_transaction_id", "tx-default")
        vals.setdefault("punch_datetime", datetime(2024, 1, 15, 9, 0, 0))
        vals.setdefault("company_id", self.company.id)
        return self.env["zkteco.transactions"].create(vals)

    def test_parse_converts_punch_time_to_utc(self):
        vals = self.env["zkteco.transactions"]._parse_transaction_vals(
            self._punch_payload(1001, punch_time="2024-01-15 09:00:00"),
            {"EMP-1": self.employee},
            self.terminal,
        )
        # Brussels is UTC+1 in January, so 09:00 local is stored as 08:00 UTC.
        expected = datetime(2024, 1, 15, 9, 0, 0).replace(tzinfo=ZoneInfo("Europe/Brussels")).astimezone(UTC).replace(tzinfo=None)
        self.assertEqual(vals["punch_datetime"], expected)
        self.assertEqual(vals["punch_datetime"], datetime(2024, 1, 15, 8, 0, 0))
        self.assertEqual(vals["employee_id"], self.employee.id)
        self.assertEqual(vals["terminal_id"], self.terminal.id)
        self.assertEqual(vals["punch_type"], "check_in")
        self.assertFalse(vals["manual_punch_type"])

    def test_parse_without_employee_keeps_naive_time(self):
        """With no linked employee there is no timezone to apply, so the time is kept as-is."""
        vals = self.env["zkteco.transactions"]._parse_transaction_vals(
            self._punch_payload(1002, emp_code="UNKNOWN", punch_time="2024-01-15 09:00:00"),
            {"EMP-1": self.employee},
            self.terminal,
        )
        self.assertEqual(vals["punch_datetime"], datetime(2024, 1, 15, 9, 0, 0))
        self.assertFalse(vals["employee_id"])

    def test_parse_unsupported_punch_state_flags_manual(self):
        """An unsupported punch state is imported with no type and flagged for manual fixing."""
        vals = self.env["zkteco.transactions"]._parse_transaction_vals(
            self._punch_payload(1003, punch_state="7"),
            {"EMP-1": self.employee},
            self.terminal,
        )
        self.assertFalse(vals["punch_type"])
        self.assertTrue(vals["manual_punch_type"])

    def test_note_flags_missing_employee(self):
        tx = self._create_transaction(punch_type="check_in")
        self.assertIn("Employee is not linked", tx.processing_note)

    def test_note_flags_unsupported_type(self):
        tx = self._create_transaction(employee_id=self.employee.id)
        self.assertIn("unsupported type", tx.processing_note)

    @freeze_time("2024-01-16 09:00:00")
    def test_process_pairs_checkin_and_checkout(self):
        checkin = self._create_transaction(
            zkteco_transaction_id="201",
            employee_id=self.employee.id,
            punch_type="check_in",
            punch_datetime=datetime(2024, 1, 15, 8, 0),
        )
        checkout = self._create_transaction(
            zkteco_transaction_id="202",
            employee_id=self.employee.id,
            punch_type="check_out",
            punch_datetime=datetime(2024, 1, 15, 17, 0),
        )

        (checkin | checkout).action_process_attendances()

        attendance = self.env["hr.attendance"].search([("employee_id", "=", self.employee.id)])
        self.assertRecordValues(
            attendance,
            [
                {
                    "check_in": datetime(2024, 1, 15, 8, 0),
                    "check_out": datetime(2024, 1, 15, 17, 0),
                    "in_mode": "biotime",
                    "out_mode": "biotime",
                }
            ],
        )

        self.assertRecordValues(
            (checkin | checkout),
            [
                {"is_processed": True, "attendance_id": attendance.id},
                {"is_processed": True, "attendance_id": attendance.id},
            ],
        )

    @freeze_time("2024-01-15 18:00:00")
    def test_process_matches_existing_open_attendance(self):
        attendance = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": datetime(2024, 1, 15, 8, 0),
            }
        )
        checkout = self._create_transaction(
            zkteco_transaction_id="301",
            employee_id=self.employee.id,
            punch_type="check_out",
            punch_datetime=datetime(2024, 1, 15, 17, 0),
        )

        checkout.action_process_attendances()

        self.assertRecordValues(
            attendance,
            [
                {
                    "check_out": datetime(2024, 1, 15, 17, 0),
                    "out_mode": "biotime",
                }
            ],
        )
        self.assertRecordValues(checkout, [{"is_processed": True, "attendance_id": attendance.id}])

    @freeze_time("2024-01-16 09:00:00")
    def test_process_flags_unmatched_checkout(self):
        checkout = self._create_transaction(
            zkteco_transaction_id="401",
            employee_id=self.employee.id,
            punch_type="check_out",
            punch_datetime=datetime(2024, 1, 15, 17, 0),
        )

        checkout.action_process_attendances()

        self.assertRecordValues(checkout, [{"is_processed": False, "unmatched_checkout": True}])
        self.assertIn("No matching Check-in", checkout.processing_note)
        self.assertTrue(checkout.activity_ids, "An activity should be scheduled for HR review.")

    @freeze_time("2024-01-16 09:00:00")
    def test_process_skips_unlinked_and_typeless(self):
        no_employee = self._create_transaction(
            zkteco_transaction_id="501", punch_type="check_in", punch_datetime=datetime(2024, 1, 15, 8, 0)
        )
        no_type = self._create_transaction(
            zkteco_transaction_id="502", employee_id=self.employee.id, punch_datetime=datetime(2024, 1, 15, 9, 0)
        )

        (no_employee | no_type).action_process_attendances()

        self.assertFalse(self.env["hr.attendance"].search_count([("employee_id", "=", self.employee.id)]))
        self.assertFalse(no_employee.is_processed)
        self.assertFalse(no_type.is_processed)

    @freeze_time("2024-01-16 09:00:00")
    def test_corrected_manual_type_can_be_processed(self):
        tx = self._create_transaction(
            zkteco_transaction_id="601",
            employee_id=self.employee.id,
            manual_punch_type=True,
            punch_datetime=datetime(2024, 1, 15, 8, 0),
        )
        self.assertIn("unsupported type", tx.processing_note)

        tx.punch_type = "check_in"
        self.assertFalse(tx.processing_note)

        tx.action_process_attendances()

        attendance = self.env["hr.attendance"].search([("employee_id", "=", self.employee.id)])
        self.assertRecordValues(tx, [{"is_processed": True, "attendance_id": attendance.id}])

    def test_cannot_delete_processed_linked_transaction(self):
        attendance = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": datetime(2024, 1, 15, 8, 0),
                "check_out": datetime(2024, 1, 15, 17, 0),
            }
        )
        tx = self._create_transaction(
            zkteco_transaction_id="701",
            employee_id=self.employee.id,
            punch_type="check_in",
            is_processed=True,
            attendance_id=attendance.id,
        )
        with self.assertRaises(UserError):
            tx.unlink()

    def test_can_delete_unprocessed_transaction(self):
        tx = self._create_transaction(zkteco_transaction_id="702", employee_id=self.employee.id, punch_type="check_in")
        tx.unlink()
        self.assertFalse(tx.exists())

    def test_can_delete_processed_transaction_without_attendance(self):
        tx = self._create_transaction(
            zkteco_transaction_id="703", employee_id=self.employee.id, punch_type="check_in", is_processed=True
        )
        tx.unlink()
        self.assertFalse(tx.exists())

    def test_deleting_attendance_resets_linked_transactions(self):
        attendance = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": datetime(2024, 1, 15, 8, 0),
                "check_out": datetime(2024, 1, 15, 17, 0),
            }
        )
        checkin = self._create_transaction(
            zkteco_transaction_id="801",
            employee_id=self.employee.id,
            punch_type="check_in",
            is_processed=True,
            attendance_id=attendance.id,
            punch_datetime=datetime(2024, 1, 15, 8, 0),
        )
        checkout = self._create_transaction(
            zkteco_transaction_id="802",
            employee_id=self.employee.id,
            punch_type="check_out",
            is_processed=True,
            attendance_id=attendance.id,
            punch_datetime=datetime(2024, 1, 15, 17, 0),
        )
        attendance.write(
            {
                "zkteco_checkin_transaction_id": checkin.id,
                "zkteco_checkout_transaction_id": checkout.id,
            }
        )

        attendance.unlink()

        self.assertRecordValues(
            (checkin | checkout),
            [
                {"is_processed": False, "attendance_unlinked": True, "attendance_id": False},
                {"is_processed": False, "attendance_unlinked": True, "attendance_id": False},
            ],
        )
