# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.l10n_be_hr_payroll.models.utils import xml_str_to_dict
from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestDmfaUnexperiencedReduction(TestPayrollCommon):
    """Tests for the ONSS reduction for unexperienced employees (code 6340, Flanders)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.belgian_company.current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00000').id,
            'onss_registration_number': '125482497',
            'onss_importance_code': '3',
        })
        fl_address = cls.env['res.partner'].create({
            'name': 'FL Work Address',
            'street': 'Main Street 1',
            'zip': '1000',
            'city': 'Brussels',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.fl_employee = cls.create_employee({
            'name': 'Employee',
            'niss': '85073003328',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2000.0,
            'address_id': fl_address.id,
            'l10n_be_worker_code_id': cls.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
            'l10n_be_onss_reduction_unexperienced_employees_flander': True,
        })

        cls.env['hr.work.location'].create({
            'address_id': cls.fl_employee.address_id.id,
            'bce_code': '8888888852',
            'location_type': 'dmfa_unit',
            'competence': 'fl',
            'company_id': cls.belgian_company.id,
        })

        wa_address = cls.env['res.partner'].create({
            'name': 'WA Work Address',
            'street': 'Main Street 2',
            'zip': '4000',
            'city': 'Liège',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.wa_employee = cls.create_employee({
            'name': 'Employee',
            'niss': '85073003328',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 2500.0,
            'address_id': wa_address.id,
            'l10n_be_worker_code_id': cls.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
            'l10n_be_onss_reduction_unexperienced_employees_flander': False,
        })

        cls.env['hr.work.location'].create({
            'address_id': cls.wa_employee.address_id.id,
            'bce_code': '8888888890',
            'location_type': 'dmfa_unit',
            'competence': 'wa',
            'company_id': cls.belgian_company.id,
        })

    def _generate_dmfa_declaration(self, environment='S', declaration_type='original', year='2025', quarter='1', parent=None, return_declaration=False, skip_signature=True):
        dmfa = self.env['l10n_be.dmfa'].with_user(self.env.user).create({
            'name': 'TESTDMFA',
            'company_id': self.belgian_company.id,
            'year': year,
            'quarter': quarter,
            'declaration_method': 'batch',
            'declaration_type': declaration_type,
            'environment': environment,
            'parent_id': parent.id if parent else False,
        })
        with patch('time.strftime', return_value='10:00:00.000'):
            dmfa.with_context(onss_skip_signature=skip_signature).generate_declaration_xml_report()
        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.state, 'ready')
        if return_declaration:
            return dmfa
        return xml_str_to_dict(dmfa.xml_file.content)

    def _create_and_validate_payslip(self, employee, date_from, date_to):
        slip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'version_id': employee.version_id.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        slip.compute_sheet()
        slip.action_payslip_done()
        return slip

    def _create_dmfa(self, year, quarter):
        return self.env['l10n_be.dmfa'].create({
            'year': str(year),
            'quarter': str(quarter),
            'company_id': self.belgian_company.id,
            'environment': 'S',
        })

    def test_standard_eligible_employee(self):
        """Flag=True, FL address, salary below ceiling → code 6340 deduction present."""
        self._create_and_validate_payslip(self.fl_employee, date(2025, 1, 1), date(2025, 1, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 2, 1), date(2025, 2, 28))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 3, 1), date(2025, 3, 31))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='1', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        self.assertAlmostEqual(unexperienced_line.amount, 1000.0)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' and d.get('DeductionAmount') == '00000100000' for d in occupation_deductions))

    def test_non_flanders_address(self):
        """Flag=True but work address is Wallonia → no 6340 deduction."""
        self._create_and_validate_payslip(self.wa_employee, date(2025, 1, 1), date(2025, 1, 31))
        self._create_and_validate_payslip(self.wa_employee, date(2025, 2, 1), date(2025, 2, 28))
        self._create_and_validate_payslip(self.wa_employee, date(2025, 3, 1), date(2025, 3, 31))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='1', return_declaration=True)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertFalse(unexperienced_line)

    def test_flag_not_set(self):
        """Work address is FL but flag is False → no 6340 deduction."""
        self.fl_employee.version_id.l10n_be_onss_reduction_unexperienced_employees_flander = False
        self._create_and_validate_payslip(self.fl_employee, date(2025, 1, 1), date(2025, 1, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 2, 1), date(2025, 2, 28))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 3, 1), date(2025, 3, 31))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='1', return_declaration=True)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertFalse(unexperienced_line)

    def test_resume_counter_after_leaving_company(self):
        """Entry Q1 2025, Quit Q2 2025, Back Q4 2025 → Will have 6340 deduction in Q4 2025, Q1 2026 (resume count) and no deduction in Q2 2026"""

        # Create payslips in Q1 2025
        self._create_and_validate_payslip(self.fl_employee, date(2025, 1, 1), date(2025, 1, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 2, 1), date(2025, 2, 28))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 3, 1), date(2025, 3, 31))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='1', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q2 2025
        self._create_and_validate_payslip(self.fl_employee, date(2025, 4, 1), date(2025, 4, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 5, 1), date(2025, 5, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 6, 1), date(2025, 6, 30))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='2', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        self.fl_employee.version_id.contract_date_end = date(2025, 6, 30)
        self.fl_employee.create_version({
            'date_version': date(2025, 10, 1),
            'contract_date_start': date(2025, 10, 1),
            'contract_date_end': False,
        })

        # Create payslips in Q4 2025
        self._create_and_validate_payslip(self.fl_employee, date(2025, 10, 1), date(2025, 10, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 11, 1), date(2025, 11, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 12, 1), date(2025, 12, 31))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='4', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q1 2026
        self._create_and_validate_payslip(self.fl_employee, date(2026, 1, 1), date(2026, 1, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 2, 1), date(2026, 2, 28))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 3, 1), date(2026, 3, 31))

        dmfa = self._generate_dmfa_declaration(year=2026, quarter='1', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q2 2026
        self._create_and_validate_payslip(self.fl_employee, date(2026, 4, 1), date(2026, 4, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 5, 1), date(2026, 5, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 6, 1), date(2026, 6, 30))

        dmfa = self._generate_dmfa_declaration(year=2026, quarter='2', return_declaration=True)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertFalse(unexperienced_line)

    def test_reduction_not_applied_after_4_active_quarters(self):
        """Entry Q1 2025, current Q2 2026 not eligible → 4 active quarters have passed since entry"""

        self._create_and_validate_payslip(self.fl_employee, date(2026, 4, 1), date(2026, 4, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 5, 1), date(2026, 5, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 6, 1), date(2026, 6, 30))

        dmfa = self._generate_dmfa_declaration(year=2026, quarter='2', return_declaration=True)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertFalse(unexperienced_line)

    def test_reduction_applied_after_leaving_and_reentering_after_more_than_4_quarters(self):
        """Entry Q1 2025, Quit Q1 2025, Back Q2 2026 → Will have 6340 deduction in Q2 2026, Q3 2026, Q4 2026, and Q1 2027 (reset count)"""

        # Create payslips in Q1 2025
        self._create_and_validate_payslip(self.fl_employee, date(2025, 1, 1), date(2025, 1, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 2, 1), date(2025, 2, 28))
        self._create_and_validate_payslip(self.fl_employee, date(2025, 3, 1), date(2025, 3, 31))

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='1', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Leave the company Q1 2025, and back Q2 2026
        self.fl_employee.version_id.contract_date_end = date(2025, 3, 31)
        self.fl_employee.create_version({
            'date_version': date(2026, 4, 1),
            'contract_date_start': date(2026, 4, 1),
            'contract_date_end': False,
        })

        # Create payslips in Q2 2026
        self._create_and_validate_payslip(self.fl_employee, date(2026, 4, 1), date(2026, 4, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 5, 1), date(2026, 5, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 6, 1), date(2026, 6, 30))
        dmfa = self._generate_dmfa_declaration(year=2026, quarter='2', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q3 2026
        self._create_and_validate_payslip(self.fl_employee, date(2026, 7, 1), date(2026, 7, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 8, 1), date(2026, 8, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 9, 1), date(2026, 9, 30))
        dmfa = self._generate_dmfa_declaration(year=2026, quarter='3', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q4 2026
        self._create_and_validate_payslip(self.fl_employee, date(2026, 10, 1), date(2026, 10, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 11, 1), date(2026, 11, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2026, 12, 1), date(2026, 12, 31))
        dmfa = self._generate_dmfa_declaration(year=2026, quarter='4', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q1 2027
        self._create_and_validate_payslip(self.fl_employee, date(2027, 1, 1), date(2027, 1, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2027, 2, 1), date(2027, 2, 28))
        self._create_and_validate_payslip(self.fl_employee, date(2027, 3, 1), date(2027, 3, 31))
        dmfa = self._generate_dmfa_declaration(year=2027, quarter='1', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertTrue(unexperienced_line)
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d.get('DeductionCode') == '6340' for d in occupation_deductions))

        # Create payslips in Q2 2027
        self._create_and_validate_payslip(self.fl_employee, date(2027, 4, 1), date(2027, 4, 30))
        self._create_and_validate_payslip(self.fl_employee, date(2027, 5, 1), date(2027, 5, 31))
        self._create_and_validate_payslip(self.fl_employee, date(2027, 6, 1), date(2027, 6, 30))
        dmfa = self._generate_dmfa_declaration(year=2027, quarter='2', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        unexperienced_line = dmfa.unexperienced_reduction_line_ids.filtered(lambda l: l.employee_id == self.fl_employee)
        self.assertFalse(unexperienced_line)
