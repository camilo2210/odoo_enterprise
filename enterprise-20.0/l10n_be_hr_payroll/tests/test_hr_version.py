from datetime import date
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollHrVersion(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_company = cls.create_belgian_company()
        cls.test_200_structure = cls.env['hr.payroll.structure.type'].create({
            'name': 'CP200 BE',
        })
        cls.test_other_structure = cls.env['hr.payroll.structure.type'].create({
            'name': 'Employee',
        })

        cls.test_job = cls.env["hr.job"].create({"name": "Test Job"})

        cls.student_emp = cls.env['hr.employee'].create({
            'name': 'Student 19yo',
            'birthday': date(2026, 1, 1) - relativedelta(years=19),
            'company_id': cls.test_company.id,
            'job_id': cls.test_job.id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'l10n_be_dimona_category': 'stu',
            'wage': 1500.0,
            'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': cls.env.ref('l10n_be_hr_payroll.cp200_b').id,
        })

        cls.departure_reason = cls.env['hr.departure.reason'].create({
            'name': 'End of Contract'
        })

        cls.worker_code_495 = cls.env.ref("l10n_be_hr_payroll.l10n_be_worker_code_00495")

        cls.worker_code_other = cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015')

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee'
        })

        cls.dimona_open = cls.env['l10n.be.dimona.declaration'].create({
            'name': 'IN Declaration',
            'date_start': date.today(),
            'company_id': cls.test_company.id,
            'date_end': False  # Open declaration
        })
        cls.dimona_closed = cls.env['l10n.be.dimona.declaration'].create({
            'name': 'OUT Declaration',
            'date_start': '2026-01-01',
            'company_id': cls.test_company.id,
            'date_end': '2026-04-17'  # Closed declaration
        })

    def check_warnings(self, warning_ids, warning_name, expected_employee, assertion):
        applicable_warnings = []
        for warning_id in warning_ids:
            warnings = self.env['hr.payroll.warning'].with_company(self.test_company).get_payroll_dashboard_warning_cards([warning_id])
            for warning in warnings:
                if warning['name'] == warning_name:
                    applicable_warnings.append(warning)
        if not expected_employee:
            self.assertEqual(applicable_warnings, [])
        elif not applicable_warnings:
            self.assertFalse(assertion)
        else:
            self.assertEqual(expected_employee in applicable_warnings[0]['warning_records'], assertion)

    def test_compute_display_be_with_200_strucure(self):
        """
        Test an employee with CP200 salary structure, the scale display field should be true.
        """
        test_version_with_salary_scale = self.env['hr.version'].create({
            'name': "Emp1",
            'structure_type_id': self.test_200_structure.id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'company_id': self.test_company.id,
        })
        self.assertEqual(test_version_with_salary_scale.display_l10n_be_scale, True)

    def test_compute_display_be_without_joint_committee(self):
        """
        Test an employee with another salary structure, the scale display field should be false.
        """
        test_version_without_salary_scale = self.env['hr.version'].create({
            'name': "Emp1",
            'l10n_be_joint_committee_id': False,
            'company_id': self.test_company.id,
        })
        self.assertEqual(test_version_without_salary_scale.display_l10n_be_scale, False)

    @freeze_time('2026-01-01')
    def test_normal_employee_seniority_0_below_scale(self):
        """ Check warning triggers for a 0yrs employee with l10n_be_scale_category A minimum wage (2194.32) """
        normal_emp = self.env['hr.employee'].create({
            'name': 'Normal Employee',
            'company_id': self.test_company.id,
            'job_id': self.test_job.id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'wage': 1500.0,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_a').id,
        })
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', normal_emp, True)

    @freeze_time('2026-01-01')
    def test_normal_employee_seniority_5_above_scale(self):
        """ Check warning triggers for a 5yrs experienced employee with l10n_be_scale_category C minimum wage """
        emp_senior = self.env['hr.employee'].create({
            'name': 'Senior Employee',
            'company_id': self.test_company.id,
            'job_id': self.test_job.id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'wage': 2000.0,
            'l10n_be_scale_seniority': 5,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_c').id,
        })

        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', emp_senior, True)

    @freeze_time('2026-01-01')
    def test_student19_b_below_scale_warning(self):
        """ Check warning triggers for a student earning less than the 19yo with Salary Scale - Category B minimum wage """
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', self.student_emp, True)

    @freeze_time('2026-01-01')
    def test_student19_b_above_scale_no_warning(self):
        """ Check no warning triggers for a student earning more than the 19yo with Salary Scale - Category B minimum wage """
        self.student_emp.wage = 2100
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', self.student_emp, False)

    @freeze_time('2026-01-01')
    def test_student18_d_below_scale_warning(self):
        """ Check warning triggers for a student earning less than the 18yo with Salary Scale - Category D minimum wage (2262.47) """
        self.student_emp.birthday = date(2026, 1, 1) - relativedelta(years=18)
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', self.student_emp, True)

    @freeze_time('2026-01-01')
    def test_chairman_999_exclusion_no_warning(self):
        chairman_emp = self.env['hr.employee'].create({
            'name': 'The Chairman',
            'company_id': self.test_company.id,
            'job_id': self.test_job.id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_999').id,
            'wage': 500.0,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_d').id,
        })
        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', chairman_emp, False)

    @freeze_time('2026-01-01')
    def test_sale_representative_exclusion_no_warning(self):
        sale_emp = self.env['hr.employee'].create({
            'name': 'Sale Representative',
            'company_id': self.test_company.id,
            'job_id': self.test_job.id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'wage': 500.0,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_d').id,
            'l10n_be_is_sale_representative': True,
        })

        dashboard_data = self.env['hr.payroll.warning'].get_payroll_dashboard_data()['warning_ids']
        self.check_warnings(dashboard_data, 'Employees Under Minimum Wage', sale_emp, False)

    def test_check_dimona_out_requirements_all_conditions_met_returns_true(self):
        """ Test: Code 495 + Open Dimona + Departure Reason Set = TRUE """
        dimona_emp = self.env["hr.employee"].create(
            {
                'name': "dimona employee",
                'company_id': self.test_company.id,
                'date_version': "2026-06-29",
                'contract_date_start': "2026-06-29",
                'l10n_be_worker_code_id': self.worker_code_495.id,
                'l10n_be_dimona_declaration_id': self.dimona_open.id,
            }
        )
        dimona_emp.departure_reason_id = self.departure_reason.id

        result = dimona_emp.version_id._check_dimona_out_requirements()
        self.assertTrue(result, "Should return True when all conditions are met.")

    def test_check_dimona_out_requirements_wrong_dmfa_code_returns_false(self):
        """ Test: Code 015 + Open Dimona + Departure Reason Set = FALSE """
        dimona_emp = self.env["hr.employee"].create(
            {
                'name': "dimona employee",
                'company_id': self.test_company.id,
                'date_version': "2026-06-29",
                'contract_date_start': "2026-06-29",
                'l10n_be_worker_code_id': self.worker_code_other.id,  # Wrong code
                'l10n_be_dimona_declaration_id': self.dimona_open.id,
            }
        )
        dimona_emp.departure_reason_id = self.departure_reason.id

        result = dimona_emp.version_id._check_dimona_out_requirements()
        self.assertFalse(result, "Should return False because DMFA code is not 495.")

    def test_check_dimona_out_requirements_no_departure_reason_returns_false(self):
        """ Test: Code 495 + Open Dimona + NO Departure Reason = FALSE """
        dimona_emp = self.env["hr.employee"].create(
            {
                'name': "dimona employee",
                'company_id': self.test_company.id,
                'date_version': "2026-06-29",
                'contract_date_start': "2026-06-29",
                'l10n_be_worker_code_id': self.worker_code_other.id,  # Wrong code
                'l10n_be_dimona_declaration_id': self.dimona_open.id,
            }
        )
        dimona_emp.departure_reason_id = False

        result = dimona_emp.version_id._check_dimona_out_requirements()
        self.assertFalse(result, "Should return False because employee has no departure reason set.")

    @freeze_time('2026-01-01')
    def test_computed_seniority_batch_cp200(self):
        employees = self.env['hr.employee'].create([{
            'name': 'CP200 Employee %s' % i,
            'company_id': self.test_company.id,
            'job_id': self.test_job.id,
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'wage': 2000.0,
            'l10n_be_scale_seniority': i,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_a').id,
        } for i in range(2)])

        # 2 years of company seniority (hired 2024-01-01, today 2026-01-01) + scale seniority (0 and 1).
        self.assertEqual(employees.version_id.mapped('l10n_be_computed_seniority_years'), [2, 3])

    def test_mobility_budget_too_low(self):
        self.employee.write({
            'wage': 3000.0,
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 200.0,
        })

        messages = [issue["message"] for issue in self.employee.version_id.issues.values()]
        self.assertTrue(any(
            "Mobility Budget amount is below the minimum allowed value" in msg for msg in messages
        ))
        self.assertFalse(any(
            "Mobility Budget amount exceeds the maximum allowed value" in msg for msg in messages
        ))
        self.assertFalse(any(
            "Mobility Budget amount exceeds 20% of the yearly wage" in msg for msg in messages
        ))

    def test_mobility_budget_too_high(self):
        self.employee.write({
            'wage': 3000.0,
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': 20000.0,
        })

        messages = [issue["message"] for issue in self.employee.version_id.issues.values()]
        self.assertTrue(any(
            "Mobility Budget amount exceeds 20% of the yearly wage" in msg for msg in messages
        ))
        self.assertTrue(any(
            "Mobility Budget amount exceeds the maximum allowed value" in msg for msg in messages
        ))
        self.assertFalse(any(
            "Mobility Budget amount is below the minimum allowed value" in msg for msg in messages
        ))

    def test_mobility_budget_within_limits(self):
        min_budget = self.env['hr.rule.parameter']._get_parameter_from_code('mobility_budget_min', raise_if_not_found=False) or 3233
        max_budget = self.env['hr.rule.parameter']._get_parameter_from_code('mobility_budget_max', raise_if_not_found=False) or 17244
        valid_amount = (min_budget + max_budget) / 2

        self.employee.write({
            'wage': 10000.0,
            'l10n_be_mobility_budget': True,
            'l10n_be_mobility_budget_amount': valid_amount,
        })

        messages = [issue["message"] for issue in (self.employee.version_id.issues or {}).values()]
        self.assertFalse(any("Mobility Budget amount is below the minimum allowed value" in msg for msg in messages))
        self.assertFalse(any("Mobility Budget amount exceeds the maximum allowed value" in msg for msg in messages))
        self.assertFalse(any("Mobility Budget amount exceeds 20% of the yearly wage" in msg for msg in messages))
