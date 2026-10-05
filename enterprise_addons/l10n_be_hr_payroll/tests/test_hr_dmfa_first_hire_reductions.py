from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_dmfa')
class TestDmfaFirstHiresReductions(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.belgian_company

    def _create_payroll_config_version(self, start_date, vals=None):
        config = self.company.create_payroll_config(date_version=start_date)
        if vals:
            config.write(vals)
        return config

    def _create_dmfa(self, year, quarter, vals=None):
        default_vals = {
            'name': f'DMFA {year} Q{quarter}',
            'year': year,
            'quarter': str(quarter),
            'declaration_method': 'batch',
        }
        if vals:
            default_vals.update(vals)
        return self.env['l10n_be.dmfa'].with_company(self.company).create(default_vals)

    def _generate_declaration(self, dmfa):
        dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()

    def test_first_hires_rank_date_recording_and_turnover_continuity(self):
        """
        Use Case:
        - Company enables first hires reduction in 01/2024.
        - Q1 2024 DMFA: Employee A (1st hire) and Employee B (2nd hire).
        - Employee B leaves; Employee C is hired in Q2 2024 for rank 2.
        - Employee C continues using the same 13-quarter entitlement based on the original 2024-01-01 eligibility date.
        """
        self._create_payroll_config_version(date(2024, 1, 1), {
            'l10n_be_reduction_for_first_hires': True,
        })

        emp_a = self.create_employee({
            'name': 'Employee A',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 3000.0,
        })
        emp_b = self.create_employee({
            'name': 'Employee B',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 2800.0,
        })

        self.create_and_validate_payslips(employees=emp_a | emp_b, year=2024, months=[1, 2, 3])

        dmfa_q1 = self._create_dmfa(2024, 1, {
            'first_hire': emp_a.id,
            'second_hire': emp_b.id,
        })

        # Generating report triggers recording of eligibility date
        self._generate_declaration(dmfa_q1)
        dmfa_q1.action_mark_done()

        self.assertTrue(dmfa_q1.xml_file, "XML file should be generated.")

        payroll_config_2024 = self.company._get_payroll_config(date(2024, 1, 1))
        self.assertEqual(
            payroll_config_2024.l10n_be_second_hire_reduction_eligibility_date,
            date(2024, 1, 1),
            "Rank 2 eligibility date must be registered as the start of the first quarter it was used.",
        )

        # --- Q2 2024: Employee B leaves, Employee C is hired ---
        emp_b.version_id.write({'contract_date_end': date(2024, 3, 31)})
        emp_c = self.create_employee({
            'name': 'Employee C',
            'contract_date_start': date(2024, 4, 1),
            'niss': self.generate_fake_niss(),
            'wage': 2900.0,
        })

        self.create_and_validate_payslips(employees=emp_a | emp_c, year=2024, months=[4, 5, 6])

        dmfa_q2 = self._create_dmfa(2024, 2, {
            'first_hire': emp_a.id,
            'second_hire': emp_c.id,
        })

        # Rank 2 message should reflect 1 quarter used and 12 quarters remaining
        dmfa_q2._compute_disabled_fields_and_messages()
        self.assertIn("12 quarters left", dmfa_q2.second_hire_message)

        # Generate report to verify calculations and XML node creation
        rendered_data = dmfa_q2._get_rendering_data()
        natural_persons = rendered_data['natural_persons']
        emp_c_np = next(np for np in natural_persons if np.employee.id == emp_c.id)

        reduction_nodes = [
            d for worker in emp_c_np.worker_records for d in worker.deductions
            if d.code == '3324'
        ]
        self.assertTrue(reduction_nodes, "Employee C should receive the second hire reduction deduction.")
        self.assertEqual(reduction_nodes[0].reduction_cap, 1550)

    def test_versioned_payroll_config_old_vs_new_regime(self):
        """
        Use Case:
        - Company created in 01/2023 (old regime).
        - Hires employee on 01/03/2023 -> first hire reduction True (cap €3,100).
        - Fires employee on 01/01/2024 -> new version with first hire reduction False.
        - Hires new employee on 01/01/2025 -> new version with first hire reduction True again.
          => Old regime applies: First hire reduction cap remains €3,100.
        - Hires new employee on 01/07/2026 -> new version created.
          => New 2026 regime applies: First hire reduction cap is €2,000.
        """
        # 1. Start in 01/03/2023
        self._create_payroll_config_version(date(2023, 3, 1), {
            'l10n_be_reduction_for_first_hires': True,
        })

        emp_2023 = self.create_employee({
            'name': 'Emp 2023',
            'contract_date_start': date(2023, 3, 1),
            'niss': self.generate_fake_niss(),
            'wage': 4000.0,
        })
        self.create_and_validate_payslips(employees=emp_2023, year=2023, months=[3])

        dmfa_2023 = self._create_dmfa(2023, 1, {
            'first_hire': emp_2023.id,
        })
        self._generate_declaration(dmfa_2023)
        dmfa_2023.action_mark_done()

        # 2. Employee leaves on 01/01/2024 -> new version with reduction = False
        emp_2023.version_id.write({'contract_date_end': date(2023, 12, 31)})
        self._create_payroll_config_version(date(2024, 1, 1), {
            'l10n_be_reduction_for_first_hires': False,
        })

        # 3. New employee hired on 01/01/2025 -> new version with reduction = True
        self._create_payroll_config_version(date(2025, 1, 1), {
            'l10n_be_reduction_for_first_hires': True,
        })
        emp_2025 = self.create_employee({
            'name': 'Emp 2025',
            'contract_date_start': date(2025, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 5000.0,
        })
        self.create_and_validate_payslips(employees=emp_2025, year=2025, months=[1, 2, 3])

        dmfa_2025 = self._create_dmfa(2025, 1, {
            'first_hire': emp_2025.id,
        })
        data_2025 = dmfa_2025._get_rendering_data()
        emp_2025_np = next(np for np in data_2025['natural_persons'] if np.employee.id == emp_2025.id)
        reduction_2025 = next(
            d for worker in emp_2025_np.worker_records for d in worker.deductions
            if d.code == '3315'
        )
        # In 2025 (pre-2026 reform), 1st hire cap is €3,100
        self.assertEqual(reduction_2025.reduction_cap, 3100, "1st hire reduction in 2025 must be capped at €3,100.")

        self._generate_declaration(dmfa_2025)
        dmfa_2025.action_mark_done()

        # 4. In 01/07/2026: New 2026 reform takes effect (cap is €2,000)
        self._create_payroll_config_version(date(2026, 7, 1), {
            'l10n_be_reduction_for_first_hires': True,
        })
        emp_2026 = self.create_employee({
            'name': 'Emp 2026',
            'contract_date_start': date(2026, 7, 1),
            'niss': self.generate_fake_niss(),
            'wage': 5000.0,
        })
        self.create_and_validate_payslips(employees=emp_2026, year=2026, months=[7, 8, 9])

        dmfa_2026 = self._create_dmfa(2026, 3, {
            'first_hire': emp_2026.id,
        })
        data_2026 = dmfa_2026._get_rendering_data()
        emp_2026_np = next(np for np in data_2026['natural_persons'] if np.employee.id == emp_2026.id)
        reduction_2026 = next(
            d for worker in emp_2026_np.worker_records for d in worker.deductions
            if d.code == '3315'
        )
        # From 01/07/2026 onwards, 1st hire cap is €2,000
        self.assertEqual(reduction_2026.reduction_cap, 2000, "1st hire reduction from July 2026 must be capped at €2,000.")

        self._generate_declaration(dmfa_2026)
        dmfa_2026.action_mark_done()

    def test_prefill_first_hires_and_skip_disabled_ranks(self):
        """
        Tests that prefill_first_hires:
        1. Selects employees with highest contribution base.
        2. Filters out employees with work-rate < 27.5%.
        3. Skips disabled ranks and fills the next available enabled rank.
        """
        self._create_payroll_config_version(date(2024, 1, 1), {
            'l10n_be_reduction_for_first_hires': True,
            'l10n_be_second_hire_reductions_used_outside_odoo': 13,  # Rank 2 exhausted
        })

        emp_high = self.create_employee({
            'name': 'High Earner',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 4500.0,
        })
        emp_mid = self.create_employee({
            'name': 'Mid Earner',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 3000.0,
        })
        emp_low_work_rate = self.create_employee({
            'name': 'Low Hours (10%)',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'resource_calendar_id': self.resource_calendar_mid_time.id,
            'wage': 400.0,
        })

        self.create_and_validate_payslips(
            employees=emp_high | emp_mid | emp_low_work_rate,
            year=2024,
            months=[1, 2, 3],
        )

        dmfa = self._create_dmfa(2024, 1)
        dmfa.prefill_first_hires()

        # High Earner -> rank 1
        self.assertEqual(dmfa.first_hire, emp_high)
        # Rank 2 is disabled (13 quarters used) -> stays False
        self.assertFalse(dmfa.second_hire)
        # Mid Earner -> moves to rank 3
        self.assertEqual(dmfa.third_hire, emp_mid)
        # Low work-rate employee (< 27.5%) is not assigned
        self.assertNotIn(emp_low_work_rate, [dmfa.first_hire, dmfa.second_hire, dmfa.third_hire])

    def test_pre_2024_eligibility_cutoff_for_fourth_to_sixth_hires(self):
        """
        Under transitional rules, 4th-6th hire reductions are only valid for contracts started <= 31/12/2023.
        """
        self._create_payroll_config_version(date(2023, 1, 1), {
            'l10n_be_reduction_for_first_hires': True,
            'l10n_be_fourth_hire_reduction_eligibility_date': date(2023, 1, 1),
        })

        emp_hired_2023 = self.create_employee({
            'name': 'Hired in 2023',
            'contract_date_start': date(2023, 10, 1),
            'niss': self.generate_fake_niss(),
            'wage': 3000.0,
        })
        emp_hired_2024 = self.create_employee({
            'name': 'Hired in 2024',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 3000.0,
        })

        self.create_and_validate_payslips(
            employees=emp_hired_2023 | emp_hired_2024,
            year=2024,
            months=[1, 2, 3],
        )

        dmfa = self._create_dmfa(2024, 1, {
            'fourth_hire': emp_hired_2024.id,
        })

        dmfa._compute_is_invalid()
        self.assertTrue(dmfa.is_invalid, "Assigning a post-2023 hire to 4th hire slot must mark the DMFA as invalid.")
        self.assertIn("not hired before 1/1/2024", dmfa.fourth_hire_warning)

        # Replace with employee hired in 2023
        dmfa.fourth_hire = emp_hired_2023.id
        dmfa._compute_is_invalid()
        self.assertFalse(dmfa.is_invalid, "Employee hired before 2024 is valid for 4th hire.")
        self.assertFalse(dmfa.fourth_hire_warning)

    def test_unique_employee_constraint(self):
        """Selecting the same employee across multiple ranks must raise a ValidationError."""
        self._create_payroll_config_version(date(2024, 1, 1), {
            'l10n_be_reduction_for_first_hires': True,
        })
        emp = self.create_employee({
            'name': 'Solo Employee',
            'contract_date_start': date(2024, 1, 1),
            'niss': self.generate_fake_niss(),
            'wage': 3000.0,
        })

        with self.assertRaises(ValidationError):
            self._create_dmfa(2024, 1, {
                'first_hire': emp.id,
                'second_hire': emp.id,
            })
