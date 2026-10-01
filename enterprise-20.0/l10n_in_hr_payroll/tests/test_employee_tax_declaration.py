from datetime import date
from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEmployeeTaxDeclarationCompute(TestPayrollCommon):

    def setUp(self):
        super().setUp()
        self._setup_common(
            country=self.env.ref('base.in'),
            structure=self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend'),
            structure_type=self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern'),
        )
        self.version = self.jethalal_emp.create_version({
            'date_version': '2025-01-01',
            'contract_date_start': '2025-01-01',
            'wage': 200000,
            'structure_type_id': self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern').id,
        })
        self.stipend_structure = self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend')
        self.env['hr.salary.rule'].create({
            'code': 'TDS',
            'name': 'Tax Deducted at Source',
            'category_ids': [Command.link(self.env.ref('hr_payroll.DED').id)],
            'condition_select': 'python',
            'condition_python': "result = payslip.env.context.get('calculate_tds', True) and payslip._l10n_in_is_tds_deduction_month()",
            'amount_select': 'code',
            'amount_python_compute': """
expected_tds = payslip.employee_id.l10n_in_compute_tax_declaration(version, payslip.ids, payslip.date_from)
result = -expected_tds['expected_tds']
            """,
            'sequence': 140,
            'struct_ids': [(4, self.stipend_structure.id)],
        })

    def _compute_declaration(self, employee, financial_year, version):
        fy_date_start, fy_date_end = self.env['hr.employee']._l10n_in_get_financial_year_bounds(financial_year)
        declarations, _ = employee._l10n_in_build_tax_declaration(fy_date_start, fy_date_end)
        self.assertTrue(declarations, "Expected declaration data from payload.")
        declaration = None
        for candidate in declarations:
            if candidate['version_id'] == version:
                declaration = candidate
                break
        self.assertIsNotNone(declaration, f"Expected declaration for version {version.display_name}.")
        return declaration, version

    def _close_version_at_may_end(self, version):
        version.write({
            'contract_date_end': '2025-05-31',
            'date_end': '2025-05-31',
        })

    @freeze_time('2025-05-10')
    def test_compute_tax_declaration_with_payslip(self):
        payslip = self._generate_payslip(
            date(2025, 4, 1),
            date(2025, 4, 30),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip.action_payslip_done()
        payslip_results = {'GROSS': 200000.0, 'TDS': -24375.0, 'NET': 175625.0}
        self._validate_payslip(payslip, payslip_results)

        financial_year = '2025-2026'
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            self.version,
        )
        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, delta=0.1)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 24375.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 24375.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 268125.0, places=2)
        # We already have one payslip in May, so the remaining Months are 11
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 11, places=2)

    @freeze_time('2025-05-10')
    def test_compute_tax_declaration_with_payslip_past_financial_year(self):
        self.version.write({
            'wage': 500000,
        })
        payslip = self._generate_payslip(
            date(2025, 1, 1),
            date(2025, 1, 30),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip.action_payslip_done()
        self._validate_payslip(payslip, {'GROSS': 500000.0, 'TDS': -48533.33, 'NET': 451466.67})

    @freeze_time('2025-06-10')
    def test_compute_tax_declaration_without_payslip(self):
        financial_year = '2025-2026'
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            self.version,
        )
        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 292500.0, places=2)
        # as we don't have any payslips in current FY, monthly TDS is calculated over 12 months
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 12, places=2)

    @freeze_time('2025-06-10')
    def test_compute_tax_declaration_multi_contract_with_payslip(self):
        payslip_april = self._generate_payslip(
            date(2025, 4, 1),
            date(2025, 4, 30),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_april.action_payslip_done()
        payslip_may = self._generate_payslip(
            date(2025, 5, 1),
            date(2025, 5, 31),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_may.action_payslip_done()
        self._validate_payslip(payslip_april, {'GROSS': 200000.0, 'TDS': -24375.0, 'NET': 175625.0})
        self._validate_payslip(payslip_may, {'GROSS': 200000.0, 'TDS': -24375.0, 'NET': 175625.0})

        self._close_version_at_may_end(self.version)
        new_version = self.jethalal_emp.create_version({
            'date_version': '2025-06-01',
            'contract_date_start': '2025-06-01',
            'contract_date_end': '2026-01-01',
            'wage': 300000,
            'structure_type_id': self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern').id,
        })
        financial_year = '2025-2026'
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            new_version,
        )
        self.assertEqual(version, new_version)
        self.assertAlmostEqual(declaration['total_income'], 3400000.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 48750.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 551850.0, places=2)
        # we have payslips in April and May, so the remaining Months are 10
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 10, places=2)

    @freeze_time('2025-07-10')
    def test_compute_tax_declaration_multi_contract_multi_payslips_outside_financial_year(self):
        financial_year = '2025-2026'
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            self.version,
        )
        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 292500.0, places=2)
        # as we don't have any payslips in current FY, monthly TDS is calculated over 12 months
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 12, places=2)

        payslip_march = self._generate_payslip(
            date(2025, 3, 1),
            date(2025, 3, 31),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_march.action_payslip_done()
        self._validate_payslip(payslip_march, {'GROSS': 200000.0, 'TDS': 0.0, 'NET': 200000.0})
        payslip_april = self._generate_payslip(
            date(2025, 4, 1),
            date(2025, 4, 30),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_april.action_payslip_done()
        payslip_may = self._generate_payslip(
            date(2025, 5, 1),
            date(2025, 5, 31),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_may.action_payslip_done()
        stipend_results = {'GROSS': 200000.0, 'TDS': -24375.0, 'NET': 175625.0}
        self._validate_payslip(payslip_april, stipend_results)
        self._validate_payslip(payslip_may, stipend_results)

        self._close_version_at_may_end(self.version)
        new_version = self.jethalal_emp.create_version({
            'date_version': '2025-07-01',
            'contract_date_start': '2025-07-01',
            'wage': 300000,
            'structure_type_id': self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern').id,
        })
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            new_version,
        )
        self.assertEqual(version, new_version)
        self.assertAlmostEqual(declaration['total_income'], 3100000.0, places=2)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 48750.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 458250.0, places=2)
        # we have payslips in March, April and May and the new version start from july so the remaining Months are 9
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 9, places=2)

    @freeze_time('2025-07-10')
    def test_compute_tax_declaration_with_multi_versions(self):
        financial_year = '2025-2026'
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            self.version,
        )
        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 292500.0, places=2)
        self.assertAlmostEqual(declaration['expected_tds'], 24375.0, places=2)

        self._close_version_at_may_end(self.version)
        new_version = self.jethalal_emp.create_version({
            'date_version': '2025-06-01',
            'contract_date_start': '2025-06-01',
            'contract_date_end': '2026-01-01',
            'wage': 300000,
            'structure_type_id': self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern').id,
        })
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            new_version,
        )
        self.assertEqual(version, new_version)
        self.assertAlmostEqual(declaration['total_income'], 3000000.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 475800.0, places=2)
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 10, places=2)

    @freeze_time('2025-08-10')
    def test_compute_tax_declaration_with_multiple_payslips(self):
        financial_year = '2025-2026'
        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            self.version,
        )
        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 292500.0, places=2)
        self.assertAlmostEqual(declaration['expected_tds'], 24375.0, places=2)

        payslip_may = self._generate_payslip(
            date(2025, 5, 1),
            date(2025, 5, 31),
            employee_id=self.jethalal_emp.id,
            version_id=self.version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_may.action_payslip_done()
        stipend_results = {'GROSS': 200000.0, 'TDS': -21863.64, 'NET': 178136.36}
        self._validate_payslip(payslip_may, stipend_results)

        self._close_version_at_may_end(self.version)
        new_version = self.jethalal_emp.create_version({
            'date_version': '2025-06-01',
            'contract_date_start': '2025-06-01',
            'wage': 300000,
            'structure_type_id': self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern').id,
        })
        payslip_june = self._generate_payslip(
            date(2025, 6, 1),
            date(2025, 6, 30),
            employee_id=self.jethalal_emp.id,
            version_id=new_version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_june.action_payslip_done()
        payslip_july = self._generate_payslip(
            date(2025, 7, 1),
            date(2025, 7, 31),
            employee_id=self.jethalal_emp.id,
            version_id=new_version.id,
            struct_id=self.stipend_structure.id,
        )
        payslip_july.action_payslip_done()
        upgraded_results = {'GROSS': 300000.0, 'TDS': -51633.64, 'NET': 248366.36}
        self._validate_payslip(payslip_june, upgraded_results)
        self._validate_payslip(payslip_july, upgraded_results)

        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            new_version,
        )
        self.assertEqual(version, new_version)
        self.assertAlmostEqual(declaration['total_income'], 3200000.0, places=2)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 103267.28, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 125130.92, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 413069.08, places=2)
        # we have payslips in May, June and July, so the remaining Months are 8
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 8, places=2)

    def test_compute_tax_declaration_without_current_contract(self):
        financial_year = '2025-2026'
        reference_date = date(2025, 6, 10)
        fy_date_start, fy_date_end = self.env['hr.employee']._l10n_in_get_financial_year_bounds(financial_year)
        with freeze_time(reference_date):
            declarations, _ = self.rahul_emp._l10n_in_build_tax_declaration(fy_date_start, fy_date_end)
        self.assertEqual(declarations, [], "Expected no declarations for employee without a current contract.")

    def test_tax_declaration_access_is_limited_to_self_or_payroll_user(self):
        employee_user = new_test_user(
            self.env,
            login='employee_tax_declaration_user',
            company_id=self.company_in.id,
        )
        self.jethalal_emp.user_id = employee_user

        own_declaration = self.jethalal_emp.with_user(employee_user).l10n_in_get_tax_declaration_view_data('2025-2026')
        self.assertTrue(
            own_declaration['declarations'],
            "A self-linked employee should keep access to their own declaration.",
        )

        with self.assertRaises(AccessError):
            self.rahul_emp.with_user(employee_user).l10n_in_get_tax_declaration_view_data('2025-2026')

    @freeze_time('2026-04-01')
    def test_tds_quarterly_missing_june_full_year(self):
        self.version.l10n_in_tds_deduction_cycle = 'quarterly'

        for start, end in [
            (date(2025, 4, 1), date(2025, 4, 30)), (date(2025, 5, 1), date(2025, 5, 31)),
            (date(2025, 7, 1), date(2025, 7, 31)), (date(2025, 8, 1), date(2025, 8, 31)),
        ]:
            self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            ).action_payslip_done()

        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            '2025-2026',
            self.version,
        )

        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2200000.0, delta=0.1)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 240500.0, places=2)
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 3, places=2)

        payslip = self._generate_payslip(
            date(2025, 9, 1), date(2025, 9, 30),
            employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
        )
        payslip.action_payslip_done()
        self._validate_payslip(payslip, {'GROSS': 200000.0, 'TDS': -80166.67, 'NET': 119833.33})

        for start, end in [
            (date(2025, 10, 1), date(2025, 10, 31)), (date(2025, 11, 1), date(2025, 11, 30)),
        ]:
            self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            ).action_payslip_done()

        payslip = self._generate_payslip(
            date(2025, 12, 1), date(2025, 12, 31),
            employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
        )
        payslip.action_payslip_done()
        self._validate_payslip(payslip, {'GROSS': 200000.0, 'TDS': -80166.67, 'NET': 119833.33})

        for start, end in [
            (date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28)),
        ]:
            self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            ).action_payslip_done()

        payslip = self._generate_payslip(
            date(2026, 3, 1), date(2026, 3, 31),
            employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
        )
        payslip.action_payslip_done()
        self._validate_payslip(payslip, {'GROSS': 200000.0, 'TDS': -80166.66, 'NET': 119833.34})

    @freeze_time('2026-04-01')
    def test_tds_half_yearly_full_year(self):
        self.version.l10n_in_tds_deduction_cycle = 'half_yearly'

        for start, end in [
            (date(2025, 4, 1), date(2025, 4, 30)), (date(2025, 5, 1), date(2025, 5, 31)),
            (date(2025, 6, 1), date(2025, 6, 30)), (date(2025, 7, 1), date(2025, 7, 31)),
            (date(2025, 8, 1), date(2025, 8, 31)),
        ]:
            self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            ).action_payslip_done()

        payslip = self._generate_payslip(
            date(2025, 9, 1), date(2025, 9, 30),
            employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
        )
        payslip.action_payslip_done()
        self._validate_payslip(payslip, {'GROSS': 200000.0, 'TDS': -146250.0, 'NET': 53750.0})

        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            '2025-2026',
            self.version,
        )

        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, delta=0.1)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 146250.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 146250.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 146250.0, places=2)
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 1, places=2)

    @freeze_time('2026-04-01')
    def test_tds_last_three_months_full_year(self):
        self.version.l10n_in_tds_deduction_cycle = 'last_three_months'

        for start, end in [
            (date(2025, 4, 1), date(2025, 4, 30)), (date(2025, 5, 1), date(2025, 5, 31)),
            (date(2025, 6, 1), date(2025, 6, 30)), (date(2025, 7, 1), date(2025, 7, 31)),
            (date(2025, 8, 1), date(2025, 8, 31)), (date(2025, 9, 1), date(2025, 9, 30)),
            (date(2025, 10, 1), date(2025, 10, 31)), (date(2025, 11, 1), date(2025, 11, 30)),
            (date(2025, 12, 1), date(2025, 12, 31)),
        ]:
            self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            ).action_payslip_done()

        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            '2025-2026',
            self.version,
        )

        self.assertEqual(version, self.version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, delta=0.1)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 292500.0, places=2)
        self.assertAlmostEqual(declaration['expected_tds'], declaration['remaining_tds'] / 3, places=2)

        for start, end in [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
            (date(2026, 3, 1), date(2026, 3, 31)),
        ]:
            payslip = self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            )
            payslip.action_payslip_done()
            self._validate_payslip(payslip, {'GROSS': 200000.0, 'TDS': -97500.0, 'NET': 102500.0})

    @freeze_time('2025-10-10')
    def test_tds_quarterly_schedule_mid_year_version_change(self):
        for start, end in [
            (date(2025, 4, 1), date(2025, 4, 30)),
            (date(2025, 5, 1), date(2025, 5, 31)),
            (date(2025, 6, 1), date(2025, 6, 30)),
        ]:
            payslip = self._generate_payslip(
                start, end,
                employee_id=self.jethalal_emp.id, version_id=self.version.id, struct_id=self.stipend_structure.id,
            )
            payslip.action_payslip_done()
            self._validate_payslip(payslip, {'GROSS': 200000.0, 'TDS': -24375.0, 'NET': 175625.0})

        self.version.write({
            'contract_date_end': '2025-06-30',
            'date_end': '2025-06-30',
        })
        new_version = self.jethalal_emp.create_version({
            'date_version': '2025-07-01',
            'contract_date_start': '2025-07-01',
            'wage': 200000,
            'l10n_in_tds_deduction_cycle': 'quarterly',
            'structure_type_id': self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_intern').id,
        })

        declaration, version = self._compute_declaration(
            self.jethalal_emp,
            '2025-2026',
            new_version,
        )

        self.assertEqual(version, new_version)
        self.assertAlmostEqual(declaration['total_income'], 2400000.0, delta=0.1)
        self.assertAlmostEqual(declaration['current_version_paid_tds'], 0.0, places=2)
        self.assertAlmostEqual(declaration['already_paid_tds'], 73125.0, places=2)
        self.assertAlmostEqual(declaration['remaining_tds'], 219375.0, places=2)

        # Jul, Aug: No deduction
        self._generate_payslip(
            date(2025, 7, 1), date(2025, 7, 31),
            employee_id=self.jethalal_emp.id, version_id=new_version.id, struct_id=self.stipend_structure.id,
        ).action_payslip_done()
        self._generate_payslip(
            date(2025, 8, 1), date(2025, 8, 31),
            employee_id=self.jethalal_emp.id, version_id=new_version.id, struct_id=self.stipend_structure.id,
        ).action_payslip_done()

        payslip_sep = self._generate_payslip(
            date(2025, 9, 1), date(2025, 9, 30),
            employee_id=self.jethalal_emp.id, version_id=new_version.id, struct_id=self.stipend_structure.id,
        )
        payslip_sep.action_payslip_done()
        self._validate_payslip(payslip_sep, {'GROSS': 200000.0, 'TDS': -73125.0, 'NET': 126875.0})

    def test_let_out_property_30_percent_tax_deduction(self):
        self.version.l10n_in_income_let_out_property = 200000
        financial_year = '2025-2026'
        date_start, _ = self.jethalal_emp._l10n_in_get_financial_year_bounds(financial_year)
        std_deduction = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_in_house_property_std_deduction',
            date=date_start
        )
        declaration, _ = self._compute_declaration(
            self.jethalal_emp,
            financial_year,
            self.version,
        )
        self.assertEqual(declaration['income_let_out_property'], 200000 * (1 - std_deduction))
