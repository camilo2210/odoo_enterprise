# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEmiratizationReport(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ae_company = cls.env['res.company'].create({
            'name': 'AE Test Co',
            'city': 'Dubai',
            'country_id': cls.env.ref('base.ae').id,
        })

        cls.job_skill_3 = cls.env['hr.job'].create({
            'name': 'Technician',
            'company_id': cls.ae_company.id,
            'l10n_ae_mohre_skill_level': '3',
        })
        cls.job_skill_5 = cls.env['hr.job'].create({
            'name': 'Sales Worker',
            'company_id': cls.ae_company.id,
            'l10n_ae_mohre_skill_level': '5',
        })
        cls.job_skill_7 = cls.env['hr.job'].create({
            'name': 'Craft Worker',
            'company_id': cls.ae_company.id,
            'l10n_ae_mohre_skill_level': '7',
        })

        cls.structure_type = cls.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').type_id.id
        cls.ae = cls.env.ref('base.ae')

        cls.target = cls.env['l10n_ae.emiratization.target'].create({
            'effective_date': date(2025, 1, 1),
            'target_percentage': 0.5,
        })

    def _create_employee(self, name, contract_date_start, date_version, job_id,
                         wage=5000.0, contract_date_end=False):
        vals = {
            'name': name,
            'company_id': self.ae_company.id,
            'country_id': self.ae.id,
            'contract_date_start': contract_date_start,
            'date_version': date_version,
            'job_id': job_id,
            'wage': wage,
            'structure_type_id': self.structure_type,
        }
        if contract_date_end:
            vals['contract_date_end'] = contract_date_end
        return self.env['hr.employee'].create(vals)

    def _create_version(self, employee, contract_date_start, date_version, job_id,
                        wage=5000.0):
        return self.env['hr.version'].create({
            'employee_id': employee.id,
            'company_id': self.ae_company.id,
            'country_id': self.ae.id,
            'contract_date_start': contract_date_start,
            'date_version': date_version,
            'job_id': job_id,
            'wage': wage,
            'structure_type_id': self.structure_type,
        })

    def _create_report(self, date_from=date(2025, 1, 1), date_to=date(2025, 7, 1)):
        return self.env['l10n_ae.emiratization.report'].create({
            'company_id': self.ae_company.id,
            'date_from': date_from,
            'date_to': date_to,
        })

    def test_skill_level_transition(self):
        """
        Case: Employee transitions into a different job with a lower MOHRE skill level.

        Employee starts with Version A on 2025-01-01 with skill level 7.
        At the report start date (2025-01-01) they are excluded because
        skill level 7 exceeds the threshold of 5.

        Employee gets a new Version B on 2025-04-01 with skill level 3.
        At the report end date (2025-07-01) they are included because the
        effective version now has skill level 3 <= 5.

        The employee should appear in line_ids as a new addition."""
        employee = self._create_employee(
            'Skill Transition', date(2025, 1, 1), date(2025, 1, 1), self.job_skill_7.id,
        )
        self._create_version(
            employee, date(2025, 1, 1), date(2025, 4, 1), self.job_skill_3.id,
        )
        report = self._create_report()

        report.action_populate()
        self.assertIn(employee, report.line_ids.employee_id)
        self.assertEqual(len(report.line_ids), 1)
        self.assertEqual(report.growth_percentage, 1.0)

    def test_new_hire_appears_as_new(self):
        """
        New employee hired after the report start date appears as new.

        A baseline employee exists since 2024-06-01 with skill level 5,
        present in both periods.

        A new hire starts on 2025-05-01 with skill level 3.
        At the report start date (2025-01-01) the new hire does not exist.

        At the report end date (2025-07-01) they are present.

        Only the new hire should appear in line_ids because they were not part
        of the workforce at the start of the reporting period."""
        self._create_employee(
            'Baseline', date(2024, 6, 1), date(2024, 6, 1), self.job_skill_5.id,
        )
        new_hire = self._create_employee(
            'New Hire', date(2025, 5, 1), date(2025, 5, 1), self.job_skill_3.id,
        )
        report = self._create_report()

        report.action_populate()
        self.assertIn(new_hire, report.line_ids.employee_id)
        self.assertEqual(len(report.line_ids), 1)
        self.assertEqual(report.growth_percentage, 1.0)

    def test_existing_employee_not_new(self):
        """
        Employee present in both periods with a version change stays existing.

        Employee starts with Version A on 2024-06-01 with skill level 5.
        At the report start date (2025-01-01) they are included (skill 5 <= 5).

        Employee gets a new Version B on 2025-05-01 with skill level 3.
        At the report end date (2025-07-01) they are still included (skill 3 <= 5).

        The employee should NOT appear in line_ids because they were already
        counted at the start — changing version within the eligible skill
        range does not make them a new hire."""
        employee = self._create_employee(
            'Version Change', date(2024, 6, 1), date(2024, 6, 1), self.job_skill_5.id,
        )
        self._create_version(
            employee, date(2024, 6, 1), date(2025, 5, 1), self.job_skill_3.id,
        )
        report = self._create_report()

        report.action_populate()
        self.assertNotIn(employee, report.line_ids.employee_id)
        self.assertEqual(len(report.line_ids), 0)
        self.assertEqual(report.growth_percentage, 0.0)

    def test_new_employees_count_matches_lines(self):
        """
        Multiple new hires with extra versions produce exactly one line each.

        One baseline employee hired 2024-06-01 (skill 5) is present in both
        periods. Two new hires join on 2025-03-01 (skill 3) and 2025-05-01
        (skill 5). New Hire 1 also gets a second version on 2025-06-01
        (skill 5), so they have two versions in the end-date set.

        After populating, there should be exactly 2 report lines (one per
        new hire) and new_employees_count should equal 2. The extra version
        on New Hire 1 must not produce a duplicate line."""
        self._create_employee(
            'Baseline', date(2024, 6, 1), date(2024, 6, 1), self.job_skill_5.id,
        )
        new_hire_1 = self._create_employee(
            'New Hire 1', date(2025, 3, 1), date(2025, 3, 1), self.job_skill_3.id,
        )
        self._create_version(
            new_hire_1, date(2025, 3, 1), date(2025, 6, 1), self.job_skill_5.id,
        )
        self._create_employee(
            'New Hire 2', date(2025, 5, 1), date(2025, 5, 1), self.job_skill_5.id,
        )
        report = self._create_report()

        report.action_populate()
        self.assertEqual(report.new_employees_count, 2)
        self.assertEqual(len(report.line_ids), 2)
        self.assertEqual(report.growth_percentage, 2.0)

    def test_contract_gap_not_new(self):
        """
        Employee with a contract gap and renewal is not counted as new.

        Employee starts with Version A on 2024-01-01 with skill level 5,
        contract ending 2025-03-15.
        At the report start date (2025-01-01) the first contract is still
        active, so the employee is counted.

        Employee gets a new Version B (new contract) on 2025-04-01 with
        skill level 5.
        At the report end date (2025-07-01) the second contract is active.

        The employee should NOT appear in line_ids because they were already
        in the workforce at the start — a contract gap and renewal does not
        make an existing employee new."""
        employee = self._create_employee(
            'Contract Gap', date(2024, 1, 1), date(2024, 1, 1), self.job_skill_5.id,
            contract_date_end=date(2025, 3, 15),
        )
        self._create_version(
            employee, date(2025, 4, 1), date(2025, 4, 1), self.job_skill_5.id,
        )
        report = self._create_report()

        report.action_populate()
        self.assertNotIn(employee, report.line_ids.employee_id)
        self.assertEqual(report.growth_percentage, 0.0)

    def test_prehire_version_excluded(self):
        """
        Pre-hire version setup does not count the employee before their
        contract actually starts.

        Employee has a version created on 2025-01-01 (date_version=Jan 1)
        with skill level 3, but contract_date_start is 2025-06-01.
        At the report start date (2025-01-01) the version exists but the
        contract has not started yet, so the employee is excluded.

        At the report end date (2025-07-01) the contract has started, so
        the employee is now included.

        The employee should appear in line_ids as a genuine new hire
        whose employment began during the reporting period."""
        employee = self._create_employee(
            'Pre-hire', date(2025, 6, 1), date(2025, 1, 1), self.job_skill_3.id,
        )
        report = self._create_report()

        report.action_populate()
        self.assertIn(employee, report.line_ids.employee_id)
        self.assertEqual(report.growth_percentage, 1.0)
