from datetime import date

from odoo.tests import Form, tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipBase


@tagged('-at_install', 'post_install')
class TestPayrunAccessFromEmployee(TestPayslipBase):

    def test_payrun_warning_action_uses_correct_kanban_view(self):
        """Ensure the payrun warning action always refers to the proper kanban view"""

        # neeed at least 2 payruns to trigger that warning
        self.payrun_1 = self.env["hr.payslip.run"].create({
            "name": "Pay Run A",
            "date_start": date(2018, 1, 1),
            "date_end": date(2018, 1, 31),
            "structure_id": self.developer_pay_structure.id,
            "version_ids": self.jules_emp.version_ids,
        })

        self.payrun_2 = self.env["hr.payslip.run"].create({
            "name": "Pay Run B",
            "date_start": date(2018, 1, 1),
            "date_end": date(2018, 1, 31),
            "structure_id": self.developer_pay_structure.id,
            "version_ids": self.jules_emp.version_ids,
        })

        Form(self.richard_emp)
        correct_view = self.env.ref("hr_payroll.hr_payrun_payslip_kanban_card_view")
        issues = self.richard_emp.issues.values()
        self.assertNotEqual(len(issues), 0, "Issue should be generated")

        for issue in issues:
            if issue.get("action_text", "") == self.env._("View Pay Runs"):
                action = issue.get("action", {})
                views = action.get("views", [])
                kanban_view = next((v for v in views if v[1] == "kanban"), None)
                self.assertIsNotNone(kanban_view, "No kanban view found in action")
                self.assertEqual(kanban_view[0], correct_view.id, "Kanban view should be hr_payrun_payslip_kanban_card_view")
