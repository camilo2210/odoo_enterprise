import datetime
from freezegun import freeze_time

from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests import Form, tagged


@tagged('at_install', '-post_install')
class TestPayrun(TestPayslipBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_pik = cls.env['hr.employee'].create({
            'name': 'Pik',
            'country_id': cls.env.ref('base.us').id,
            'date_version': '2025-01-01',
            'contract_date_start': '2025-01-01',
            'wage': 3000,
            'structure_type_id': cls.structure_type.id,
        })
        cls.employee_achu = cls.env['hr.employee'].create({
            'name': 'Achu',
            'country_id': cls.env.ref('base.us').id,
            'date_version': '2025-01-01',
            'contract_date_start': '2025-01-01',
            'wage': 3000,
            'structure_type_id': cls.structure_type.id,
            'review_state': '3_anomaly',
        })
        cls.payrun_pikachu = cls.env['hr.payslip.run'].create({
            'date_start': '2025-01-01',
            'date_end': '2025-01-01',
            'name': 'Pik&Achu',
            'version_ids': [(6, 0, [cls.employee_pik.version_id.id, cls.employee_achu.version_id.id])],
            'structure_id': cls.developer_pay_structure.id,
        })

    def test_pay_run_general_flow(self):
        employees = self.env['hr.employee'].create([
            {
                'name': 'Employee A',
                'date_version': datetime.date(2024, 1, 1),
                'contract_date_start': datetime.date(2024, 1, 1),
                'structure_type_id': self.structure_type.id,
            },
            {
                'name': 'Employee B',
                'date_version': datetime.date(2025, 1, 1),
                'contract_date_start': datetime.date(2025, 1, 1),
                'structure_type_id': self.structure_type.id,
            }
        ])
        pay_run = self.env['hr.payslip.run'].create({
            'name': 'January 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'structure_id': self.developer_pay_structure.id,
        })

        self.assertEqual(len(pay_run.version_ids), 5, "Payrun should initialize with current versions (Richard, Pik, Achu, Employee_a, Employee_b).")
        self.assertEqual(len(pay_run.slip_ids), 0, "Payrun should initialize with no payslips.")

        pay_run._generate_payslips()

        self.assertEqual(len(pay_run.slip_ids), 5, "Pay run should generate payslips for corresponding versions.")

        slip_b = pay_run.slip_ids.filtered(lambda p: p.employee_id == employees[1])
        slip_b.unlink()

        self.assertEqual(len(pay_run.slip_ids), 4, "Should have 4 payslips.")
        self.assertNotIn(employees[1].version_id, pay_run.version_ids, "Version of Employee B should be removed after its payslip is unlinked.")

    def test_add_payslip_to_payrun(self):
        self.env['hr.employee'].create([
            {
                'name': 'Employee A',
                'date_version': datetime.date(2024, 1, 1),
                'contract_date_start': datetime.date(2024, 1, 1),
                'structure_type_id': self.structure_type.id,
            },
            {
                'name': 'Employee B',
                'date_version': datetime.date(2025, 1, 1),
                'contract_date_start': datetime.date(2025, 1, 1),
                'structure_type_id': self.structure_type.id,
            }
        ])
        pay_run = self.env['hr.payslip.run'].create({
            'name': 'January 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'structure_id': self.developer_pay_structure.id,
        })

        pay_run._generate_payslips()
        self.assertEqual(len(pay_run.version_ids), 5, "Payrun should initialize with current versions (Richard, Pik, Achu, Employee_a, Employee_b).")
        self.assertEqual(len(pay_run.slip_ids), 5, "Payrun should generate payslips for corresponding versions.")

        new_employee = self.env['hr.employee'].create({
            'name': 'New Employee',
            'date_version': datetime.date(2026, 1, 1),
            'contract_date_start': datetime.date(2026, 1, 1),
            'structure_type_id': self.structure_type.id,
        })
        new_employee_payslip = self.env['hr.payslip'].create({
            'employee_id': new_employee.id,
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
            'payslip_run_id': pay_run.id
        })

        self.assertIn(new_employee.version_id, pay_run.version_ids, "Version of the New Employee is added to the Payrun versions.")
        self.assertIn(new_employee_payslip, pay_run.slip_ids, "Payslip of the New Employee is added to the Payrun payslips.")

    def test_payslip_creation_with_onfly_payrun(self):
        payslip_vals = {
            'employee_id': self.richard_emp.id,
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
            'payslip_run_id': self.env['hr.payslip.run'].create({
                'name': 'On-fly Payrun',
                'date_start': '2026-01-01',
                'date_end': '2026-01-31',
                'structure_id': self.developer_pay_structure.id,
            }).id
        }

        new_payslip = self.env['hr.payslip'].create(payslip_vals)
        new_payrun = new_payslip.payslip_run_id

        self.assertTrue(new_payrun, "Pay Run should have been created and linked.")

        self.assertEqual(len(new_payrun.version_ids), 1, "Should have 1 version.")
        self.assertIn(new_payslip.version_id, new_payrun.version_ids, "The employee version linked to the Pay Run versions.")

        self.assertEqual(len(new_payrun.slip_ids), 1, "Should have 1 payslip.")
        self.assertIn(new_payslip, new_payrun.slip_ids, "The payslip linked to the Pay Run slips.")

    def test_payrun_name_compute(self):
        pay_run = self.env['hr.payslip.run'].create({
            'date_start': '2026-02-01',
            'date_end': '2026-02-28',
            'structure_id': self.developer_pay_structure.id,
        })
        self.assertTrue(pay_run.name, "Name should be auto-generated from dates.")

        new_name = "Custom Name"
        pay_run_manual = self.env['hr.payslip.run'].create({
            'name': new_name,
            'date_start': '2026-02-01',
            'date_end': '2026-02-28',
            'structure_id': self.developer_pay_structure.id,
        })
        self.assertEqual(pay_run_manual.name, new_name, "New name should not be overwritten by the existed computed one.")

    def test_payrun_archived_employee(self):
        """
        When creating a payrun, it should filter to keep only versions of active employees.
        """
        emp_active = self.env['hr.employee'].create({
            'name': 'Active',
            'active': True,
            'company_id': self.company_us.id,
            'contract_date_start': '2026-03-01',
            'structure_type_id': self.structure_type.id,
        })
        emp_archived = self.env['hr.employee'].create({
            'name': 'Archived',
            'active': False,
            'company_id': self.company_us.id,
            'contract_date_start': '2026-03-01',
            'structure_type_id': self.structure_type.id,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2026-03-01',
            'date_end': '2026-03-31',
            'structure_id': self.developer_pay_structure.id,
            'name': 'Payrun'
        })
        versions = payslip_run._get_valid_versions()
        self.assertIn(emp_active.version_id, versions)
        self.assertNotIn(emp_archived.version_id, versions)

    def test_add_versions_to_existing_payrun(self):
        self.env['hr.employee'].create([
            {
                'name': 'Employee A',
                'date_version': datetime.date(2024, 1, 1),
                'contract_date_start': datetime.date(2024, 1, 1),
                'structure_type_id': self.structure_type.id,
            },
            {
                'name': 'Employee B',
                'date_version': datetime.date(2025, 1, 1),
                'contract_date_start': datetime.date(2025, 1, 1),
                'structure_type_id': self.structure_type.id,
            }
        ])

        pay_run = self.env['hr.payslip.run'].create({
            'name': 'January 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'structure_id': self.developer_pay_structure.id,
        })
        pay_run._generate_payslips()
        version_count = len(pay_run.version_ids)
        slip_count = len(pay_run.slip_ids)
        self.assertTrue(version_count > 0, "Payrun should be initialized with existing versions.")

        new_employee = self.env['hr.employee'].create({
            'name': 'New Employee',
            'date_version': datetime.date(2026, 1, 1),
            'contract_date_start': datetime.date(2026, 1, 1),
            'structure_type_id': self.structure_type.id,
        })

        pay_run.action_add_versions([new_employee.id])
        pay_run._generate_payslips()

        self.assertEqual(
            len(pay_run.version_ids),
            version_count + 1,
            "Payrun should have one more version after adding the new employee."
        )
        self.assertIn(
            new_employee.version_id,
            pay_run.version_ids,
            "New employee version should be present in the payrun."
        )

        # Check if the payslip is generated for the new employee
        self.assertEqual(
            len(pay_run.slip_ids),
            slip_count + 1,
            "Payrun should have one more payslip after generating for the new employee."
        )
        self.assertIn(
            new_employee.version_id,
            pay_run.slip_ids.version_id,
            "Payslip should be generated for the new employee version."
        )

    def test_payrun_rerun_recomputes_salary_adjustment(self):
        rule = self.attach_salary_rule
        pay_run = self.env['hr.payslip.run'].create({
            'name': 'January 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'structure_id': self.developer_pay_structure.id,
            'version_ids': [(6, 0, [self.employee_pik.version_id.id])],
        })

        payslip = pay_run._generate_payslips()
        self.assertEqual(len(payslip), 1)
        self.assertEqual(payslip.employee_id, self.employee_pik)

        pay_run.action_validate()
        self.assertEqual(payslip.state, 'validated')

        self.env['hr.salary.attachment'].create({
            'employee_id': self.employee_pik.id,
            'description': 'Test Attachment',
            'salary_rule_id': rule.id,
            'date_start': datetime.date(2026, 1, 15),
            'amount': 200,
        })

        pay_run.action_draft()
        self.assertEqual(payslip.state, 'draft')

        pay_run.action_validate()

        input_lines = payslip.input_line_ids.filtered(lambda line: line.salary_rule_id == rule)
        self.assertRecordValues(input_lines, [{
            'code': rule.code,
            'amount': 200.0,
            'name': 'Test Attachment',
        }])
        self.assertEqual(payslip._get_input_line_amount(rule.code), 200.0)

        salary_line = payslip.line_ids.filtered(lambda line: line.code == rule.code)
        self.assertEqual(salary_line.total, -200.0)

    def test_delete_payslip_from_draft_payrun(self):
        pay_run = self.env['hr.payslip.run'].create({
            'name': 'May 2026',
            'date_start': '2026-05-01',
            'date_end': '2026-05-31',
            'structure_id': self.developer_pay_structure.id,
            'version_ids': [(6, 0, [self.employee_pik.version_id.id, self.employee_achu.version_id.id])],
        })

        empl_a = self.env['hr.employee'].create({
            'name': 'Employee A',
            'date_version': datetime.date(2024, 1, 1),
            'contract_date_start': datetime.date(2024, 1, 1),
            'structure_type_id': self.structure_type.id,
        })

        payslip_empl_a = self.env['hr.payslip'].create({
            'employee_id': empl_a.id,
            'date_from': '2026-05-01',
            'date_to': '2026-05-31',
            'payslip_run_id': pay_run.id
        })
        self.assertEqual(len(pay_run.slip_ids), 1)
        self.assertEqual(len(pay_run.version_ids), 3)

        # 1. removing version by removing payslip_run_id in payslip\
        payslip_empl_a.payslip_run_id = False
        self.assertEqual(len(pay_run.slip_ids), 0, "The payslip was not removed from payrun")
        self.assertEqual(len(pay_run.version_ids), 2, "The version was not removed from payrun")

        pay_run.version_ids = [(6, 0, [self.employee_pik.version_id.id, self.employee_achu.version_id.id])]
        payslip_empl_a.payslip_run_id = pay_run.id
        self.assertEqual(len(pay_run.slip_ids), 1)
        self.assertEqual(len(pay_run.version_ids), 3)

        # 2. removing version in payrun
        pay_run.off_cycle_version(empl_a.version_id.id)
        self.assertEqual(len(pay_run.slip_ids), 0, "The payslip was not removed from payrun")
        self.assertEqual(len(pay_run.version_ids), 2, "The version was not removed from payrun")

        payslip_empl_a.payslip_run_id = pay_run.id
        self.assertEqual(len(pay_run.slip_ids), 1)
        self.assertEqual(len(pay_run.version_ids), 3)

        # 3. removing payslip
        payslip_empl_a.unlink()
        self.assertEqual(len(pay_run.slip_ids), 0, "The payslip was not removed from payrun")
        self.assertEqual(len(pay_run.version_ids), 2, "The version was not removed from payrun")

    @freeze_time("2026-02-15")
    def test_cron_generate_payrun_for_employee_types_with_auto_post(self):
        employee_type_1 = self.env['hr.employee.type'].create({
            'name': 'Type 1',
            'payroll_closing_date': 31,
            'payroll_auto_post': True,
        })
        employee_type_2 = self.env['hr.employee.type'].create({
            'name': 'Type 2',
            'payroll_closing_date': 5,
            'payroll_auto_post': True,
        })
        employee_type_3 = self.env['hr.employee.type'].create({
            'name': 'Type 3',
            'payroll_closing_date': 20,
            'payroll_auto_post': False,
        })
        default_struct = self.env['hr.version'].with_company(self.company_us)._default_salary_structure().default_struct_id
        emp1, emp2, emp3 = self.env['hr.employee'].create([
            {
                'name': 'Employee 1',
                'employee_type_id': employee_type_1.id,
                'company_id': self.company_us.id,
            },
            {
                'name': 'Employee 2',
                'employee_type_id': employee_type_2.id,
                'company_id': self.company_us.id,
            },
            {
                'name': 'Employee 3',
                'employee_type_id': employee_type_3.id,
                'company_id': self.company_us.id,
            },
        ])
        emp1.create_version({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'structure_type_id': default_struct.type_id.id,
        })
        emp2.create_version({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'structure_type_id': default_struct.type_id.id,
        })
        emp3.create_version({
            'date_version': datetime.date(2025, 1, 1),
            'contract_date_start': datetime.date(2025, 1, 1),
            'structure_type_id': default_struct.type_id.id,
        })

        self.env['hr.payslip.run']._cron_generate_payrun_for_employee_types_with_auto_post()

        payrun_type_1 = self.env['hr.payslip.run'].search([
            ('employee_type_ids', 'in', employee_type_1.id),
        ])
        self.assertEqual(len(payrun_type_1), 1, "A payrun should be generated for employee type 1")
        self.assertEqual(payrun_type_1.date_start, datetime.date(2026, 1, 1))
        self.assertEqual(payrun_type_1.date_end, datetime.date(2026, 1, 31))

        payrun_type_2 = self.env['hr.payslip.run'].search([
            ('employee_type_ids', 'in', employee_type_2.id),
        ])
        self.assertEqual(len(payrun_type_2), 1, "A payrun should be generated for employee type 2")
        self.assertEqual(payrun_type_2.date_start, datetime.date(2026, 1, 1))
        self.assertEqual(payrun_type_2.date_end, datetime.date(2026, 1, 31))

        payrun_type_3 = self.env['hr.payslip.run'].search([
            ('employee_type_ids', 'in', employee_type_3.id),
        ])
        self.assertEqual(len(payrun_type_3), 0, "No payrun should be generated for employee type 3 since auto_post is False")

        self.env['hr.payslip.run']._cron_generate_payrun_for_employee_types_with_auto_post()
        self.assertEqual(self.env['hr.payslip.run'].search_count([
            ('employee_type_ids', 'in', employee_type_1.id),
        ]), 1, "No new payrun should be generated for employee type 1 since a payrun already exists")
        self.assertEqual(self.env['hr.payslip.run'].search_count([
            ('employee_type_ids', 'in', employee_type_2.id),
        ]), 1, "No new payrun should be generated for employee type 2 since a payrun already exists")

        payrun_type_2.slip_ids.action_payslip_draft()
        payrun_type_2.action_draft()
        payrun_type_2.unlink()

        self.assertFalse(payrun_type_2.exists())
        self.env['hr.payslip.run']._cron_generate_payrun_for_employee_types_with_auto_post()
        self.assertEqual(self.env['hr.payslip.run'].search_count([
            ('employee_type_ids', 'in', employee_type_2.id),
        ]), 1, "A new payrun should be generated for employee type 2")

    def test_payslip_semi_monthly_dates(self):
        self.structure_type.default_schedule_pay = 'semi-monthly'
        with Form(self.env['hr.payslip.run']) as payrun_form:
            with freeze_time('2025-01-12'):
                payrun_form.structure_id = self.developer_pay_structure
                self.assertEqual(payrun_form.date_start, datetime.date(2025, 1, 1))
                self.assertEqual(payrun_form.date_end, datetime.date(2025, 1, 15))
            with freeze_time('2025-01-20'):
                payrun_form.structure_id = self.developer_pay_structure
                self.assertEqual(payrun_form.date_start, datetime.date(2025, 1, 16))
                self.assertEqual(payrun_form.date_end, datetime.date(2025, 1, 31))
