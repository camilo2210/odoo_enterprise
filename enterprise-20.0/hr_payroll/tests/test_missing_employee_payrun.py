# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests import Form
from odoo.tests.common import freeze_time


class TestEmployeePayrunIssues(TestPayslipBase):
    """
    Test suite for the 'issues' field computation on hr.employee.
    This test inherits from TestPayslipBase to reuse the common
    payroll setup (employees, structures, etc.).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Use data from TestPayslipBase ---
        # We'll use 'richard_emp' as our primary test employee.
        # His contract_date_start is set to 2018-01-01 in the base class.
        cls.employee = cls.richard_emp
        # --- Define Dates ---
        # We set our test period to be *within* richard_emp's contract
        cls.start_of_month = date(2018, 2, 1)
        cls.end_of_month = date(2018, 2, 28)
        cls.prev_start = date(2018, 1, 1)
        cls.prev_end = date(2018, 1, 31)

    def test_01_issue_and_action_add_payslip(self):
        """
        Test Case 1: Employee has no payslip.
        - Verify the 'issues' field generates an 'action_add_payslip_to_payrun' warning.
        - Verify executing the action creates a new payslip and links it to the payrun.
        - Verify the warning disappears after the action.
        """
        # Pre-check: No payslips exist
        payslip_count = self.env['hr.payslip'].search_count([('employee_id', '=', self.employee.id)])
        self.assertEqual(payslip_count, 0)

        payslip_run = self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
        }])

        # 1. Trigger the compute
        Form(self.employee)

        # 2. Assert the issue is correctly generated
        self.assertTrue(self.employee.issues, "Warning issue was not generated")
        self.assertIn('0', self.employee.issues)
        issue_data = self.employee.issues['0']
        self.assertEqual(issue_data['action']['name'], 'action_add_payslip_to_payrun')

        # 3. Execute the action
        action_result = self.employee.action_add_payslip_to_payrun(payslip_run.id)

        # 4. Assert the action's effects
        self.assertEqual(action_result['tag'], 'reload', "Action did not return a reload tag")
        new_payslip = self.env['hr.payslip'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(len(new_payslip), 1, "Payslip was created")
        self.assertEqual(new_payslip.payslip_run_id, payslip_run)
        self.assertEqual(new_payslip.date_from, self.start_of_month)
        self.assertEqual(new_payslip.date_to, self.end_of_month)
        self.assertEqual(new_payslip.struct_id, self.developer_pay_structure)

        # 5. Assert the issue is now resolved
        Form(self.employee)
        self.assertFalse(self.employee.issues, "Warning issue was cleared after adding payslip")

    def test_02_issue_and_action_link_payslip(self):
        """
        Test Case 2: Employee has an unlinked payslip in the correct period.
        - Verify the 'issues' field generates an 'action_add_payslip_to_payrun' warning.
        - Verify executing the action links the existing payslip to the payrun.
        - Verify the warning disappears after the action.
        """
        # 1. Create an unlinked payslip
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': self.start_of_month,
            'date_to': self.end_of_month,
            'struct_id': self.developer_pay_structure.id,
            'payslip_run_id': False,
        })
        self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
        }])

        # 2. Trigger the compute
        Form(self.employee)

        # 3. Assert the issue is not generated
        self.assertFalse(self.employee.issues, "Warning should not be generated")

    def test_03_issue_unlinked_payslip_wrong_period(self):
        """
        Test Case 3: Employee has an unlinked payslip but for a different period.
        - Verify the 'issues' field falls back to 'action_add_payslip_to_payrun'.
        """
        # 1. Create an unlinked payslip for the *previous* month
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': self.prev_start,
            'date_to': self.prev_end,
            'struct_id': self.developer_pay_structure.id,
            'payslip_run_id': False,
        })
        self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
        }])

        # 2. Trigger the compute
        Form(self.employee)

        # 3. Assert the issue is 'add', not 'link'
        self.assertTrue(self.employee.issues, "Warning issue was generated")
        issue_data = self.employee.issues['0']
        self.assertEqual(issue_data['action']['name'], 'action_add_payslip_to_payrun')

    def test_04_no_issue_payslip_in_batch(self):
        """
        Test Case 4: Employee already has a payslip in the batch.
        - Verify no 'issues' are generated.
        """
        # 1. Create a payslip *linked* to the payrun
        payslip_run = self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
        }])
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': self.start_of_month,
            'date_to': self.end_of_month,
            'struct_id': self.developer_pay_structure.id,
            'payslip_run_id': payslip_run.id,
        })

        # 2. Trigger the compute
        Form(self.employee)

        # 3. Assert no issue is generated
        self.assertFalse(self.employee.issues, "Issue shouldn't be generated")

    def test_05_no_issue_payrun_closed(self):
        """
        Test Case 5: The payrun exists but is not in the '01_ready' state.
        - Verify no 'issues' are generated.
        """
        # 1. Set the payrun to a different state
        payslip_run = self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
        }])
        payslip_run.state = '02_close'
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': self.start_of_month,
            'date_to': self.end_of_month,
            'struct_id': self.developer_pay_structure.id,
            'payslip_run_id': False,
        })

        # 2. Trigger the compute
        Form(self.employee)

        # 3. Assert no issue is generated
        self.assertFalse(self.employee.issues, "Issue shouldn't be generated")

    def test_06_no_issue_no_contract_date(self):
        """
        Test Case 6: The employee has no contract start date.
        - Verify no 'issues' are generated.

        (In TransactionCase, we create a new employee to avoid
         modifying the shared self.employee)
        """
        # 1. Create a minimal employee. They will have no version_id
        #    with a contract_date_start, so the related field will be False.
        emp_no_contract = self.env['hr.employee'].create({
            'name': 'No Contract Eric',
        })
        self.assertFalse(emp_no_contract.contract_date_start, "contract_date_start was not False")

        # 2. Trigger the compute
        Form(emp_no_contract)

        # 3. Assert no issue is generated (compute should have skipped)
        self.assertFalse(emp_no_contract.issues, "Issue shouldn't be generated for an employee with no contract date")

    def test_07_no_issue_payrun_wrong_structure(self):
        """
        Test Case 7: The payrun is for a different salary structure.
        - Verify no 'issues' are generated.
        """
        # 1. Create a different structure and structure type and assign it to the payrun
        other_struct_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Other Structure type',
        })
        other_struct = self.env['hr.payroll.structure'].create({
            'name': 'Other Structure',
            'type_id': other_struct_type.id,
        })
        self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': other_struct.id,
        }])

        # 2. Trigger the compute
        Form(self.employee)

        # 3. Assert no issue is generated
        self.assertFalse(self.employee.issues, "Issue shouldn't be generated")

    def test_08_multiple_issues_different_struct_same_type(self):
        """
        Test Case 8: Two payruns for different structures of the same type.
        - Verify that the employee gets one issue to view available payruns.
        """
        # 1. Setup: We need two structures that share a type with the employee
        struct_A = self.developer_pay_structure

        struct_B = self.env['hr.payroll.structure'].create({
            'name': 'Analyst Structure',
            'type_id': self.developer_pay_structure.type_id.id,
        })
        self.assertNotEqual(struct_A.id, struct_B.id, "Structures should be different")

        # 2. Create two payruns, one for each structure
        payslip_run_A = self.env['hr.payslip.run'].create([{
            'name': 'Developer Payrun Feb',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': struct_A.id,
            'state': '01_ready',
        }])
        payslip_run_B = self.env['hr.payslip.run'].create([{
            'name': 'Analyst Payrun Feb',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': struct_B.id,
            'state': '01_ready',
        }])

        # 3. Pre-check: No payslips exist
        payslip_count = self.env['hr.payslip'].search_count([('employee_id', '=', self.employee.id)])
        self.assertEqual(payslip_count, 0)

        # 4. Trigger the compute
        Form(self.employee)

        # 5. Assert one issue is generated
        self.assertTrue(self.employee.issues, "Issues were not generated")
        self.assertEqual(len(self.employee.issues), 1, "Expected one issue to view available payruns")
        issue_data = self.employee.issues['0']
        self.assertEqual(issue_data['action_text'], 'View Pay Runs')
        self.assertEqual(issue_data['action']['type'], 'ir.actions.act_window')
        self.assertEqual(issue_data['action']['res_model'], 'hr.payslip.run')
        domain_field, operator, values = issue_data['action']['domain'][0]
        self.assertEqual(domain_field, 'id')
        self.assertEqual(operator, 'in')
        self.assertCountEqual(values, [payslip_run_A.id, payslip_run_B.id])

    def test_09_no_issue_closing_date_not_due(self):
        """
        Test Case 9: Employee is missing from a payrun, but the payroll closing date
        for that period is not yet due.
        - Verify no 'issues' are generated.
        """
        # 1. Set a closing date on the company that is in the future relative to date_end
        #    date_end = 2018-02-28, so a closing date of day 5 (of next month)
        #    means the deadline is 2018-03-05, which is after date_end.
        #    We mock today to be before that closing date (e.g. 2018-03-01).
        self.employee.company_id.payroll_closing_date = 5  # 5th of the next month → 2018-03-05

        self.env['hr.payslip.run'].create({
            'name': 'Salary Slip Feb',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
            'state': '01_ready',
        })

        # 2. Assert no issue is generated since closing date (2018-03-05) is not yet due
        with freeze_time('2018-03-01'):
            self.assertFalse(self.employee.version_id.issues, "Issue shouldn't be generated before closing date is due")

    def test_10_no_new_issue_new_version(self):
        """
        Test Case 10:
        - Employee is missing from a payrun, verify if the related issue is generated.
        - Create a payslip linked to the payrun, verify if the issue disappears.
        - Create new employee version, verify if the issue does not reappear.
        """
        payslip_run = self.env['hr.payslip.run'].create([{
            'name': 'Salary Slip Jan',
            'date_start': self.start_of_month,
            'date_end': self.end_of_month,
            'company_id': self.employee.company_id.id,
            'structure_id': self.developer_pay_structure.id,
        }])
        Form(self.employee)

        self.assertTrue(self.employee.issues, "Warning issue was not generated")
        self.assertTrue(
            any(issue.get('message') == "The pay run %s is missing this employee" % payslip_run.name for issue in self.employee.issues.values()),
            "The related 'missing employee in payrun' issue was not generated",
        )

        self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': self.start_of_month,
            'date_to': self.end_of_month,
            'struct_id': self.developer_pay_structure.id,
            'payslip_run_id': payslip_run.id,
        })
        Form(self.employee)

        if self.employee.issues:
            self.assertFalse(
                any(issue.get('message') == "The pay run %s is missing this employee" % payslip_run.name for issue in self.employee.issues.values()),
                "The related 'missing employee in payrun' issue was generated",
            )

        self.employee.create_version({
            'date_version': date(2018, 4, 1),
        })
        Form(self.employee)

        if self.employee.issues:
            self.assertFalse(
                any(issue.get('message') == "The pay run %s is missing this employee" % payslip_run.name for issue in self.employee.issues.values()),
                "The related 'missing employee in payrun' issue was generated",
            )
