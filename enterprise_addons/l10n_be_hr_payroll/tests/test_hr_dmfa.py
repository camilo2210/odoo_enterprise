
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests import Form, tagged
from odoo.exceptions import UserError, ValidationError
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_dmfa')
class TestPayrollDmfa(TestPayrollCommon):

    """
    Other dmfa tests there :
        test_l10n_be_hr_payroll_account/tests/test_dmfa.py
    """

    """
    Prerequisites for a dmfa report:
       Companies need following properties to be set:
            - employer_category_id.dmfa_code
            - onss_registration_number
            - l10n_be_company_number
       Employees need:
            - niss
            - address_id (that matches a l10n_be.dmfa.local.unit)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_report_can_only_be_generated_from_root_company(self):
        companies = self.multibranch_company
        with self.assertRaises(UserError):
            self.env['l10n_be.dmfa'].with_company(companies[1]).create({})

    def test_include_child_branches_in_report(self):
        companies = self.belgian_company | self.multibranch_company
        # company 0 -> root / no child
        # company 1 (is parent of) company 2 (is parent of) company 3
        target_company = companies[1]

        self.env['hr.work.location'].search([('company_id', 'in', companies.ids), ('location_type', '=', 'dmfa_unit')]).bce_code = '8888888883'

        employees = self.create_employee(
            [{
                'name': f'Employee {company.name}',
                'company_id': company.id,
                'contract_date_start': date(2026, 1, 1),
                'niss': self.generate_fake_niss(),
                'address_id': company.partner_id.id,
            }
            for company in companies])

        self.create_and_validate_payslips(employees=employees, year=2026, months=[1])

        dmfa = self.env['l10n_be.dmfa'].with_company(target_company).create({
            'year': 2026,
            'quarter': '1',
        })
        rendered_data = dmfa._get_rendering_data()

        reported_companies = rendered_data['data']['branch_ids']
        expected_branches = companies[1:]
        self.assertEqual(reported_companies, expected_branches, "DMFA report should include 3 companies 1-2-3")

        reported_employees = rendered_data['natural_persons']
        self.assertEqual(len(reported_employees), 3, "Expected 3 natural persons, one per company")

    @freeze_time('2026-07-01')
    def test_dmfa_warnings(self):
        """
        We have 11 warnings, the conditions for 2 of which are already
        satisfied for Employee Test. These are the following:

        - Missing NISS for employee
        - Missing DIMONA for period

        The rest need to be activated:
        - Invalid DMFA work address
        - Missing company employer class
        - Missing ONSS company ID
        - Invalid work entry type dmfa code
        - Invalid vehicle license plate
        - Quarter working days incompatibility
        - Quarter working schedule incompatibility
        - Missing termination dates
        - Missing employee worker code
        """
        # Change the employee address to a work address that is not linked to a location unit
        self.employee_test.address_id = self.env['res.partner'].create({'name': 'Invalid Work Address'})
        # Remove employer category from company
        self.env.company.current_payroll_config_id.l10n_be_employer_category_id = False
        # Remove ONSS company Id
        self.env.company.current_payroll_config_id.l10n_be_company_number = False
        # For some reason there is no record of res.config.settings for the company
        self.env['res.config.settings'].create({'company_id': self.env.company.id})
        # Pick a random employee, i.e. Employee Test and make a paid payslip for it to be eligible for DMFA.
        # The payslip needs to be paid because cars are only considered in that case, not validated
        emp_id = self.employee_test.id
        payslip = self.env['hr.payslip'].create({'employee_id': emp_id, 'name': 'test payslip 1'})
        payslip.state = 'paid'
        # Remove the DMFA code on the Attendance work entry type
        payslip.worked_days_line_ids.work_entry_type_id.dmfa_code = False
        # Take a car, assign it to our company, make the license plate too long and assign it to the employee
        brand = self.env["fleet.vehicle.model.brand"].create({
            "name": "Ferrari",
        })
        model = self.env["fleet.vehicle.model"].create({
            "brand_id": brand.id,
            "name": "A good one",
        })
        car = self.env["fleet.vehicle"].create({'model_id': model.id, 'license_plate': '2-ASD-345'})
        car.company_id = self.env.company.id
        car.license_plate += '0000000000'
        self.employee_test.car_id = car
        # Make 4 more payslips for the quarter (1 has already been created) to make the amount of worked days
        # higher than the amount of days present in the quarter
        payslips = self.env['hr.payslip'].create([
            {
                'employee_id': emp_id,
                'name': 'test payslip 2',
                'date_from': datetime.now() + relativedelta(months=1),
            },
            {
                'employee_id': emp_id,
                'name': 'test payslip 3',
                'date_from': datetime.now() + relativedelta(months=2),
            },
            {
                'employee_id': emp_id,
                'name': 'test payslip 4',
                'date_from': datetime.now() + relativedelta(months=1),
            },
            {
                'employee_id': emp_id,
                'name': 'test payslip 5',
                'date_from': datetime.now() + relativedelta(months=2),
            },
        ])
        payslips.state = 'paid'
        # Make a payslip with Termination Fees pay structure
        termination_fees_struct_id = self.env['hr.payroll.structure'].search([('name', '=', 'Termination Fees (BE)')]).id
        term_payslip = self.env['hr.payslip'].create(
            {
                'employee_id': emp_id,
                'name': 'termination test payslip',
                'date_from': datetime.now(),
                'struct_id': termination_fees_struct_id,
            }
        )
        term_payslip.state = 'paid'
        # Remove the worker code from the employee
        self.employee_test.l10n_be_worker_code_id = False

        # Create DMFA and compute issues
        dmfa = self.env['l10n_be.dmfa'].create({'company_id': self.env.company.id})
        dmfa._compute_issues()
        messages = [issue['message'] for issue in dmfa.issues.values()]
        self.assertEqual(len(messages), 10)
        expected_messages = [
            'Employees with work address missing ONSS code',
            'Missing NISS for employees',
            'Employees missing DMFA worker code',
            'Missing employer class for company',
            'Missing ONSS company ID for company',
            'Termination payslips missing notice period dates',
            'Employees exceeding quarterly occupation days',
            'Occupation days mismatch working schedule',
            'Time types missing DMFA code',
            'DMFA employees missing DIMONA',
        ]
        for expected_message in expected_messages:
            self.assertTrue(any(msg.startswith(expected_message) for msg in messages), f"Expected warning starting with '{expected_message}' not found in messages.")

    def test_dmfa_establishment_unit_code_format(self):
        """
        Test that checks if a validation error is raised when trying to write an invalid code on an establishment unit.
        """
        with self.assertRaises(ValidationError) as error:
            self.env['hr.work.location'].create({
                "company_id": self.belgian_company.id,
                "bce_code": 1234567890,
                "address_id": self.belgian_company.partner_id.id,
            })
        self.assertIn('The DMFA establishment unit code must be 10 digits long. The first digit must be between 2 and 8.', str(error.exception))

        with self.assertRaises(ValidationError) as error:
            self.env['hr.work.location'].create({
                "company_id": self.belgian_company.id,
                "bce_code": 888888888,
                "address_id": self.belgian_company.partner_id.id,
            })
        self.assertIn('The DMFA establishment unit code must be 10 digits long. The first digit must be between 2 and 8.', str(error.exception))

        establishment_unit = self.env['hr.work.location'].create({
            "company_id": self.belgian_company.id,
            "bce_code": 8888888888,
            "address_id": self.belgian_company.partner_id.id,
        })
        with self.assertRaises(ValidationError) as error:
            establishment_unit.write({'bce_code': 123})
        self.assertIn('The DMFA establishment unit code must be 10 digits long. The first digit must be between 2 and 8.', str(error.exception))

    def test_dmfa_establishment_unit_valid_location_dates(self):
        """
        Checks that a validation error is raised when:
        1. Trying to change the location date after the contract start date of an employee working in the related EU.
        2. Trying to change the contract start date of an employee working in an EU before its location date.
        """
        self.employee_a.write({'work_location_id': self.env['hr.work.location'].search([
            ('company_id', '=', self.belgian_company.id),
        ], limit=1).id})
        establishment_unit = self.env['hr.work.location'].create({
            "company_id": self.belgian_company.id,
            "bce_code": 8234567890,
            "address_id": self.belgian_company.partner_id.id,
            "date_start": "2016-12-05"
        })
        establishment_unit.write({"date_start": datetime.now()})
        with self.assertRaises(ValidationError):
            self.employee_a.write({'work_location_id': establishment_unit.id})
        self.employee_a.version_id.work_location_id.write({'date_start': self.employee_a.version_id.date_start})
        with self.assertRaises(ValidationError):
            self.employee_a.version_id.write({'contract_date_start': "2019-12-05"})

    def test_dmfa_establishment_unit_competence_computation(self):
        """
        Checks that the correct competence and payslip language are set on an establishment unit when setting its
        address.
        """
        nl_partner = self.env['res.partner'].create({
            'name': 'NL partner',
            'city': 'Machelen',
            'zip': 1830
        })
        de_partner = self.env['res.partner'].create({
            'name': 'DE partner',
            'city': 'Eupen',
            'zip': 4700
        })
        with Form(self.env['hr.work.location']) as eu:
            eu.bce_code = 8234567890
            eu.address_id = self.belgian_company.partner_id
        self.assertEqual(eu.competence, 'wa')
        with Form(self.env['hr.work.location']) as eu:
            eu.bce_code = 8234567890
            eu.address_id = nl_partner
        self.assertEqual(eu.competence, 'fl')
        with Form(self.env['hr.work.location']) as eu:
            eu.bce_code = 8234567890
            eu.address_id = de_partner
        self.assertEqual(eu.competence, 'cg')
