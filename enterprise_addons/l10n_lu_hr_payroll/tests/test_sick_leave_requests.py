from datetime import date
from odoo.tests import tagged
from .common import TestLuPayrollCommon


@tagged("post_install", "post_install_l10n", "-at_install")
class TestSickLeaveRequests(TestLuPayrollCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_cns_compensation(self):

        self.env["hr.leave"].create(
            {
                "employee_id": self.employee_david.id,
                "work_entry_type_id": self.env.ref(
                    "hr_work_entry.lu_work_entry_type_sick_leave"
                ).id,
                "request_date_from": date(2026, 1, 1),
                "request_date_to": date(2026, 4, 3),
            }
        )
        all_leaves = (
            self.env["hr.leave"]
            .search([("employee_id", "=", self.employee_david.id)])
            .sorted("request_date_from")
        )

        # The 77th day of the sick leave happens in March. For Jan, Feb, and March, the employee receives a full basic salary
        # Therefore, the sick leave will be splitted into 2 leaves.
        # Starting from April, the sick days for the employee will be transformed to "Sick Time Off (CNS)", which will be unpaid by company and paid by the CNS.

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 1, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 31))
        self.assertEqual(all_leaves[0].work_entry_type_id.code, "013.00")

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 4, 1))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 4, 3))
        self.assertEqual(all_leaves[1].work_entry_type_id.code, "SL_CNS")
