# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged, freeze_time

from .common import TestLuPayrollCommon


@freeze_time('2022-12-31')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestLuMonthlyDeclaration(TestLuPayrollCommon):

    def setUp(self):
        super().setUp()

        self.payslip_run = self.env['hr.payslip.run'].create({
            'name': 'March 2022',
            'date_start': '2022-03-01',
            'date_end': '2022-03-31',
            'company_id': self.lux_company.id,
            'state': '01_ready',
            'structure_id': self.env.ref('l10n_lu_hr_payroll.hr_payroll_structure_lux_employee_salary').id,
        })
        self.payslip_run._generate_payslips()
        self.payslip_run.action_validate()

    def test_01_generate_missing_identification(self):
        report = self.env['l10n.lu.seculine.reports'].create({
            'month': '3',
            'year': '2022',
        })
        report.report_type = 'decsal'
        self.employee_david.identification_id = False
        with self.assertRaisesRegex(UserError, r'missing an identification number'):
            report.action_generate_report()

        self.employee_david.identification_id = 111111111
        report.action_generate_report()

        self.lux_company.l10n_lu_seculine = False
        with self.assertRaisesRegex(UserError, r'Missing (.+) SECUline numbers'):
            report.action_generate_report()

        self.lux_company.l10n_lu_seculine = 999999999

        self.lux_company.l10n_lu_official_social_security = False
        with self.assertRaisesRegex(UserError, r'Missing (.+) social security'):
            report.action_generate_report()

    def test_02_company_identification(self):
        report = self.env['l10n.lu.seculine.reports'].create({
            'month': '3',
            'year': '2022',
        })
        report.action_generate_report()

        declaration = report.report_file.decode('utf8')
        declaration_lines = declaration.split('\r\n')

        company_ssn = self.lux_company.l10n_lu_official_social_security
        company_seculine = self.lux_company.l10n_lu_seculine
        self.assertEqual(declaration_lines[0], f"0;{company_ssn};{company_seculine}")

    def test_03_multiple_contracts_decsal(self):
        self.payslip_run.action_draft()

        madison_employee = self.env['hr.employee'].create({
            'name': 'Madison',
            'company_id': self.lux_company.id,
            'identification_id': 987654321,
            'structure_type_id': self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux').id,
            'date_version': '2022-01-01',
            'contract_date_start': '2022-01-01',
            'contract_date_end': '2022-03-11',
            'wage': 4000.0,
        })
        madison_contract1 = madison_employee.version_id

        madison_contract1.copy({
            'date_version': '2022-03-21',
            'contract_date_start': '2022-03-21',
            'contract_date_end': False,
            'wage': 4400.0,
        })

        laura_employee = self.env['hr.employee'].create({
            'name': 'laura',
            'company_id': self.lux_company.id,
            'identification_id': 143111140,
            'structure_type_id': self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux').id,
            'date_version': '2022-03-04',
            'contract_date_start': '2022-03-04',
            'contract_date_end': '2022-03-15',
            'wage': 4000.0,
        })

        self.env['hr.leave'].create({
            'name': 'such bad weather no work',
            'employee_id': madison_employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_lu_work_entry_type_situational_unemployment').id,
            'request_date_from': '2022-03-09',
            'request_date_to': '2022-03-09',
        })
        batch = self.env['hr.payslip.run'].create({
            'name': 'March 2022',
            'date_start': '2022-03-01',
            'date_end': '2022-03-31',
            'company_id': self.lux_company.id,
            'state': '01_ready',
            'structure_id': self.env.ref('l10n_lu_hr_payroll.hr_payroll_structure_lux_employee_salary').id,
        })

        batch._generate_payslips()
        batch.action_validate()

        report = self.env['l10n.lu.seculine.reports'].create({
            'month': '3',
            'year': '2022',
        })

        with self.assertRaisesRegex(UserError, r'^Missing amounts'):
            report.report_type = 'decsal'
            report.action_generate_report()

        self.assertEqual(len(report.situational_unemployment_ids), 1)
        self.assertEqual(report.situational_unemployment_ids.employee_id, madison_employee)
        self.assertEqual(report.situational_unemployment_ids.hours, 8)

        report.situational_unemployment_ids.amount = 120
        report.action_generate_report()

        declaration = report.report_file.decode('utf8')
        declaration_lines = declaration.split('\r\n')

        self.assertEqual(len(declaration_lines), 4, "Should have 4 lines, 1 for company identification + 1 for each employee")

        employee_values = {
            laura_employee.identification_id: {
                1: self.lux_company.l10n_lu_official_social_security,
                3: 202203,  # period reference YYYYMM
                4: 142609,
                5: 64,  # 8 days * 8h
                13: '04',  # period start date - start of contract
                14: 15,  # period end date - end of contract
            },
            madison_employee.identification_id: {
                0: 1,
                1: self.lux_company.l10n_lu_official_social_security,
                4: 319087,
                5: 136,  # 17 days (9 days 1st contract + 9 days 2nd contract - 1 day unemployment) * 8h
                10: 12000,  # 120.00 encoded in the wizard
                11: 8,  # 1 day of situational unemployment
                13: '01',  # period start date - start of month
                14: 31,  # period end date - end of month
            },
            self.employee_david.identification_id: {
                1: self.lux_company.l10n_lu_official_social_security,
                2: self.employee_david.identification_id,
                4: 630368,
                5: 184,  # 23 days * 8h
                10: 0,
                11: 0,
                13: '01',  # period start date - start of month
                14: 31,  # period end date - end of month
            },
        }

        employees_done = []
        for line in declaration_lines[1:]:
            fields = line.split(';')
            self.assertEqual(len(fields), 20)

            employee_identification_id = fields[2]
            if employee_identification_id in employees_done:
                raise Exception('There should be only one line per employee')
            employees_done.append(employee_identification_id)

            for idx, val in employee_values[employee_identification_id].items():
                self.assertEqual(str(val), fields[idx], f"Error: expected {val} on field #{idx} found {fields[idx]} instead: \n{line}")

    def test_04_multiple_contracts_different_structures_decsal(self):
        structure_type = self.env['hr.payroll.structure.type'].create({'name': 'Lux: Test'})
        pay_structure = self.env['hr.payroll.structure'].create({
            'name': 'Lux Structure Test',
            'type_id': structure_type.id,
        })
        structure_type.default_struct_id = pay_structure

        jade_employee = self.env['hr.employee'].create({
            'name': 'Jade',
            'company_id': self.lux_company.id,
            'identification_id': 987654321,
            'structure_type_id': structure_type.id,
            'date_version': '2022-01-01',
            'contract_date_start': '2022-01-01',
            'contract_date_end': '2022-03-11',
            'wage': 3000.0,
        })
        jade_contract1 = jade_employee.version_id
        jade_contract2 = jade_contract1.copy({
            'name': 'Jade Contract 2',
            'date_version': '2022-03-21',
            'contract_date_start': '2022-03-21',
            'contract_date_end': False,
            'wage': 4400.0,
            'structure_type_id': self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux').id,
        })

        batch = self.env['hr.payslip.run'].create({
            'name': 'March 2022',
            'date_start': '2022-03-01',
            'date_end': '2022-03-31',
            'company_id': self.lux_company.id,
            'state': '01_ready',
            'structure_id': pay_structure.id,
        })
        batch._generate_payslips()
        batch.action_validate()

        batch = self.env['hr.payslip.run'].create({
            'name': 'March 2022',
            'date_start': '2022-03-01',
            'date_end': '2022-03-31',
            'company_id': self.lux_company.id,
            'state': '01_ready',
            'structure_id': self.env.ref('l10n_lu_hr_payroll.hr_payroll_structure_lux_employee_salary').id,
        })
        batch._generate_payslips()
        batch.action_validate()

        report = self.env['l10n.lu.seculine.reports'].create({
            'month': '3',
            'year': '2022',
        })
        report.report_type = 'decsal'
        report.action_generate_report()

        declaration = report.report_file.decode('utf8')
        declaration_lines = declaration.split('\r\n')

        self.assertNotEqual(jade_contract1.structure_type_id, jade_contract2.structure_type_id)
        self.assertEqual(len(declaration_lines), 4)  # 1 for company identification + 1 for David + 2 for Jade

        jade_entries = [
            line.split(';')
            for line in declaration_lines
            if line.split(';')[2] == jade_employee.identification_id
        ]
        self.assertEqual(len(jade_entries), 2)

        self.assertEqual(jade_entries[0][13], "01")
        self.assertEqual(jade_entries[0][14], "11")

        self.assertEqual(jade_entries[1][13], "21")
        self.assertEqual(jade_entries[1][14], "31")

    def test_05_hourly_worker(self):
        structure_type = self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux')
        structure_type.wage_type = 'hourly'
        hourly_employee = self.env['hr.employee'].create({
            'name': 'Alice Smith',
            'company_id': self.lux_company.id,
            'identification_id': '1234567890123',
            'structure_type_id': self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux').id,
            'hourly_wage': 25.0,
            'wage_type': 'hourly',
            'wage': 4000.0,
            'date_version': '2022-01-01',
            'contract_date_start': '2022-01-01',
        })

        hourly_contract = hourly_employee.version_id

        payslip = self.env['hr.payslip'].create({
            'employee_id': hourly_employee.id,
            'version_id': hourly_contract.id,
            'date_from': '2022-01-01',
            'date_to': '2022-01-31',
            'struct_id': self.env.ref('l10n_lu_hr_payroll.hr_payroll_structure_lux_employee_salary').id,
        })
        payslip.compute_sheet()

        index_ratio = hourly_contract.l10n_lu_current_index / hourly_contract.l10n_lu_index_on_contract_signature
        indexed_hourly = round(25 * index_ratio, 2)
        expected_salary = indexed_hourly * 168
        self.assertAlmostEqual(payslip.line_ids.filtered(lambda l: l.code == 'BASIC').total, expected_salary, 2)

    def test_06_declatation_of_incapacity_decmal(self):
        laura_employee, madison_employee = self.env['hr.employee'].create([
            {
                'name': 'laura',
                'private_country_id': self.env.ref('base.lu').id,
                'company_id': self.lux_company.id,
                'date_version': '2022-1-1',
                'contract_date_start': '2022-1-1',
                'structure_type_id': self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux').id,
                'wage': 6000,
                'identification_id': 222222222,
            },
            {
                'name': 'madison',
                'private_country_id': self.env.ref('base.lu').id,
                'company_id': self.lux_company.id,
                'date_version': '2022-1-1',
                'contract_date_start': '2022-1-1',
                'structure_type_id': self.env.ref('l10n_lu_hr_payroll.structure_type_employee_lux').id,
                'wage': 6000,
                'identification_id': 333333333,
            },
        ])
        laura_employee.tz = "Europe/Luxembourg"
        madison_employee.tz = "Europe/Luxembourg"
        family_reason_work_entry_type = self.env.ref('hr_work_entry.l10n_lu_work_entry_type_family_reason_leave')
        welcome_leave_work_entry_type = self.env.ref('hr_work_entry.l10n_lu_work_entry_type_welcome_leave')
        (family_reason_work_entry_type + welcome_leave_work_entry_type).with_context(install_mode=True).requires_allocation = False
        welcome_leave_work_entry_type.request_unit = 'hour'
        leaves = self.env['hr.leave'].create([
            {
                'name': 'Family Reason Leave',
                'employee_id': laura_employee.id,
                'work_entry_type_id': family_reason_work_entry_type.id,
                'request_date_from': date(2022, 4, 4),
                'request_date_to': date(2022, 4, 6),
            },
            {
                'name': 'Welcome Leave',
                'employee_id': laura_employee.id,
                'work_entry_type_id': welcome_leave_work_entry_type.id,
                'request_date_from': date(2022, 4, 25),
                'request_date_to': date(2022, 5, 5),
            },
            {
                'name': 'Welcome Leave specific hours',
                'employee_id': madison_employee.id,
                'work_entry_type_id': welcome_leave_work_entry_type.id,
                'work_entry_type_request_unit': 'hour',
                'request_date_from': date(2022, 4, 11),
                'request_date_to': date(2022, 4, 11),
                'request_hour_from': 13,
                'request_hour_to': 14,
            }
        ])
        leaves.action_approve()

        # monthly decmal information report
        report = self.env['l10n.lu.seculine.reports'].create({
            'report_type': 'decmal',
            'report_action': 'information',
            'month': '4',
            'year': '2022',
        })
        report.action_generate_report()
        report_file = report.report_file.decode('utf8')
        decmal_lines = report_file.split('\r\n')

        company_ssn = self.lux_company.l10n_lu_official_social_security
        company_seculine = self.lux_company.l10n_lu_seculine
        madison_ssn = madison_employee.identification_id
        laura_ssn = laura_employee.identification_id
        # Check company identification line
        self.assertEqual(decmal_lines[0], f"0;{company_ssn};{company_seculine}")

        # Check number of lines (1 header + 3 leave entries)
        assert len(decmal_lines) == 4, f"Expected 4 lines in report, got {len(decmal_lines)}"

        expected_lines = [
            f'1;{company_ssn};{laura_ssn};202204;{family_reason_work_entry_type.l10n_lu_seculine_code};20220404;20220406;24;',
            f'1;{company_ssn};{laura_ssn};202204;{welcome_leave_work_entry_type.l10n_lu_seculine_code};20220425;20220429;40;',
            f'1;{company_ssn};{madison_ssn};202204;{welcome_leave_work_entry_type.l10n_lu_seculine_code};20220411;20220411;1;',
        ]
        for line in expected_lines:
            assert line in decmal_lines, f"Expected line missing from report: {line}"

        # monthly decmal correction report
        report = self.env['l10n.lu.seculine.reports'].create({
            'month': '4',
            'year': '2022',
            'report_type': 'decmal',
            'report_action': 'correction',
            'employee_ids': [(6, 0, [madison_employee.id, laura_employee.id])],
        })
        report.action_generate_report()
        report_file = report.report_file.decode('utf8')
        decmal_lines = report_file.split('\r\n')

        expected_grouped_lines = {
            f'{laura_ssn}': [
                f'2;{company_ssn};{laura_ssn};202204;;;;;',
                f'1;{company_ssn};{laura_ssn};202204;{welcome_leave_work_entry_type.l10n_lu_seculine_code};20220425;20220429;40;',
                f'1;{company_ssn};{laura_ssn};202204;{family_reason_work_entry_type.l10n_lu_seculine_code};20220404;20220406;24;',
            ],
            f'{madison_ssn}': [
                f'2;{company_ssn};{madison_ssn};202204;;;;;',
                f'1;{company_ssn};{madison_ssn};202204;{welcome_leave_work_entry_type.l10n_lu_seculine_code};20220411;20220411;1;',
            ]
        }

        # Check the order and data of the lines
        actual_grouped_lines = defaultdict(list)
        current_identification = None
        for line in decmal_lines[1:]:
            line_data = line.split(';')
            line_type = line_data[0]
            if line_type == '2':
                current_identification = line_data[2]  # identification field
                self.assertEqual(line, expected_grouped_lines[current_identification][0],
                    f"Expected line {expected_grouped_lines[current_identification][0]} not found in report")
            elif line_type == '1':
                assert current_identification == line_data[2], \
                    f"Mismatched identification. Expected {current_identification}, got {line_data[2]}"
                actual_grouped_lines[current_identification].append(line)
            else:
                raise Exception('Wrong data in the decmal report')

        for identification, lines in expected_grouped_lines.items():
            assert (len(lines) - 1) == len(actual_grouped_lines[identification]), \
                f"Expected {len(lines)} lines for identification {identification}, got {len(actual_grouped_lines[identification])}"
            for line in lines[1:]:
                assert line in actual_grouped_lines[identification], \
                    f"Expected line {line} not found in report for identification {identification}"
