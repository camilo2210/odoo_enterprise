from datetime import date

from odoo.tests import Form, tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestExcludeOutDays(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure_type = cls.env["hr.payroll.structure.type"].create(
            {
                "name": "Test Type",
                "default_schedule_pay": "monthly",
            }
        )
        cls.structure = cls.env["hr.payroll.structure"].create(
            {
                "name": "Test Structure",
                "type_id": cls.structure_type.id,
            }
        )

        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Test Employee",
                "structure_type_id": cls.structure_type.id,
                "contract_date_start": date(2018, 1, 16),  # Mid month starting contract
                "date_version": date(2018, 1, 16),
                "wage": 1000.0,
            }
        )
        cls.contract = cls.employee.version_id

    def test_exclude_unpaid_days_from_totals(self):
        """
        Test that sum_worked_days and sum_worked_hours only calculate
        remunerated lines when a contract starts mid-month.
        """
        self.contract.generate_work_entries(date(2018, 1, 1), date(2018, 1, 31))

        payslip = self.env["hr.payslip"].create(
            {
                "name": "January Payslip",
                "employee_id": self.employee.id,
                "version_id": self.contract.id,
                "struct_id": self.structure.id,
                "date_from": date(2018, 1, 1),
                "date_to": date(2018, 1, 31),
            }
        )
        payslip.compute_sheet()

        out_line = payslip.worked_days_line_ids.filtered(lambda l: l.code == "000.00")
        self.assertTrue(out_line, "Odoo should automatically generate an '000.00' line.")
        self.assertFalse(out_line.is_paid, "The '000.00' line must not be paid.")

        self.assertTrue(payslip.worked_days_line_ids[0].is_paid)
        self.assertFalse(payslip.worked_days_line_ids[1].is_paid)

        self.assertAlmostEqual(payslip.worked_days_line_ids[0].fte, 0.522, places=3, msg="Full Time equivalent should not exclude unpaid time.")
        self.assertAlmostEqual(payslip.worked_days_line_ids[1].fte, 0.478, places=3, msg="Full Time equivalent should not exclude unpaid time.")

        self.assertEqual(payslip.sum_worked_paid_days, 12, "sum_worked_paid_days should only count paid days.")
        self.assertEqual(payslip.sum_worked_paid_hours, 96, "sum_worked_hours should only count paid hours.")
        self.assertEqual(payslip.sum_worked_days, 23, "sum_worked_days should count paid and unpaid days.")
        self.assertEqual(payslip.sum_worked_hours, 184, "sum_worked_hours should count paid and unpaid hours.")

    def test_manual_changes_worked_day_line_amount(self):
        """
        Checks that when a user manually changes the amount on a worked day lines, the change is persistent and isn't
        overwritten by the system.
        """
        payslip = self.env["hr.payslip"].create({
            "name": "January Payslip",
            "employee_id": self.employee.id,
            "version_id": self.contract.id,
            "struct_id": self.structure.id,
            "date_from": date(2018, 1, 1),
            "date_to": date(2018, 1, 31),
        })
        payslip.worked_days_line_ids.filtered(lambda l: l.name == 'Work').unlink()  # only keep one line for deterministic behavior
        with Form(payslip) as payslip_form:
            with payslip_form.worked_days_line_ids.edit(0) as line:
                line.amount = 3000
            payslip_form.save()
        self.assertEqual(payslip.worked_days_line_ids[0].amount, 3000)
