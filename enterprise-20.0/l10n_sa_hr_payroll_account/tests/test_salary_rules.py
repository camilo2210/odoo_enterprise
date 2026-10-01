# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('sa')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls._setup_common(
            country=cls.env.ref('base.sa'),
            structure=cls.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure'),
            structure_type=cls.env.ref('l10n_sa_hr_payroll.ksa_employee_payroll_structure_type'),
            version_fields={
                'wage': 10000.0,
                'l10n_sa_housing_allowance': 400.0,
                'l10n_sa_transportation_allowance': 200.0,
                'l10n_sa_other_allowances': 150.0,
                'l10n_sa_number_of_days': 20.0,
            }
        )
        cls.env.user.group_ids |= cls.env.ref('hr_holidays.group_hr_holidays_manager')

        cls.saudi_work_contact = cls.env['res.partner'].create({
            'name': 'KSA Local Employee',
            'company_id': cls.env.company.id,
        })

        cls.saudi_employee = cls.env['hr.employee'].create({
            'name': 'KSA Local Employee',
            'address_id': cls.saudi_work_contact.id,
            'company_id': cls.env.company.id,
            'country_id': cls.env.ref('base.sa').id,
            'structure_type_id': cls.env.ref('l10n_sa_hr_payroll.ksa_employee_payroll_structure_type').id,
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 12000,
            'l10n_sa_housing_allowance': 1000,
            'l10n_sa_transportation_allowance': 200,
            'l10n_sa_other_allowances': 500,
            'l10n_sa_number_of_days': 21,
            'l10n_sa_company_social_insurance_percentage': 0.09,
            'l10n_sa_company_oh_insurance_percentage': 0.0075,
            'l10n_sa_company_unemployment_insurance_percentage': 0.02,
            'l10n_sa_employee_social_insurance_percentage': 0.09,
            'l10n_sa_employee_oh_insurance_percentage': 0.0025,
            'l10n_sa_employee_unemployment_insurance_percentage': 0.005,
            'l10n_sa_iqama_annual_amount': 6000.0,
            'l10n_sa_medical_insurance_annual_amount': 4800.0,
            'l10n_sa_work_permit_annual_amount': 3600.0,
        })
        cls.saudi_contract = cls.saudi_employee.version_id

        cls.compensable_timeoff_type = cls.env['hr.work.entry.type'].create({
            'name': "KSA Compensable Leaves",
            'code': "KSA Compensable Leaves",
            'unit_of_measure': 'day',
            'requires_allocation': False,
            'count_as': 'absence',
        })

        cls.env.company.write({
            "l10n_sa_annual_work_entry_type_id": cls.compensable_timeoff_type.id,
        })

        cls.env['hr.leave.allocation'].create({
            'employee_id': cls.saudi_employee.id,
            'date_from': date(2024, 1, 1),
            'work_entry_type_id': cls.compensable_timeoff_type.id,
            'number_of_days': 21,
            'state': 'confirm',
        }).action_approve()
        cls.work_entry_types = {
            entry_type.code: entry_type
            for entry_type in cls.env['hr.work.entry.type'].search([('country_id', '=', cls.env.ref('base.sa').id)])
        }
        (
        cls.env.ref("hr_work_entry.l10n_sa_work_entry_type_overtime")
        ).sudo().requires_allocation = False

    def test_saudi_payslip(self):
        self.saudi_contract.contract_date_end = '2026-4-27'
        paid_leave_allocation = self.env['hr.leave.allocation'].create({
            'employee_id': self.saudi_employee.id,
            'date_from': date(2026, 4, 1),
            'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_legal_leave').id,
            'number_of_days': 3,
            'state': 'confirm',
        })
        paid_leave_allocation.action_approve()
        self.env['hr.leave'].create({
                'name': 'Unpaid Leave',
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_unpaid_leave').id,
                'request_date_from': date(2026, 4, 1),
                'request_date_to': date(2026, 4, 2),
        })
        self.env['hr.leave'].create({
                'name': 'Paid Leave',
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_legal_leave').id,
                'request_date_from': date(2026, 4, 7),
                'request_date_to': date(2026, 4, 9),
        })
        self.env['hr.leave'].create({
                'name': 'Paid Leave',
                'employee_id': self.saudi_employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_sick_leave').id,
                'request_date_from': date(2026, 4, 13),
                'request_date_to': date(2026, 4, 15),
        })

        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'UNPAID': -3113.64, 'ALPPOUT': 1868.18, 'EOSP': 441.1, 'ANNUALP': 1089.77, 'GROSS': 13700.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 9318.86, 'NETCOST': 13313.86}
        self._validate_payslip(payslip, payslip_results)

    def test_saudi_payslip_laid_off(self):
        # Generate 2 prior payslips to accrue EOSP provisions
        payslip_jan = self._generate_payslip(
            date(2024, 1, 1), date(2024, 1, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_jan.compute_sheet()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'EOSP': 570.83, 'ANNUALP': 1042.39, 'GROSS': 13700.0, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 12432.5, 'NETCOST': 16427.5}
        self._validate_payslip(payslip_jan, payslip_results)
        payslip_jan.action_payslip_done()

        payslip_feb = self._generate_payslip(
            date(2024, 2, 1), date(2024, 2, 29),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_feb.compute_sheet()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'EOSP': 570.83, 'ANNUALP': 1141.67, 'GROSS': 13700.0, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 12432.5, 'NETCOST': 16427.5}
        self._validate_payslip(payslip_feb, payslip_results)
        payslip_feb.action_payslip_done()
        self.saudi_employee.write({
            'active': False,
            'departure_reason_id': self.env.ref('l10n_sa_hr_payroll.saudi_departure_company_article_77').id,
            'departure_date': date(2024, 3, 31),
        })
        self.saudi_contract.date_end = date(2024, 3, 31)
        payslip = self._generate_payslip(
            date(2024, 3, 1), date(2024, 3, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 12000.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'HOUALLOW': 1000.0, 'OTALLOW': 500.0, 'TRAALLOW': 200.0, 'EOSP': 570.83, 'EOSB': 27400.0, 'EOSPC': 26258.34, 'ANNUALP': 1141.67, 'ANNUALCOMP': 13700.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'GROSS': 54800.0, 'NET': 53532.5, 'NETCOST': 83785.84}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_overtime_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        ot_work_entry_type = self.env.ref('hr_work_entry.sa_work_entry_type_overtime')
        ot_work_entry_type.requires_allocation = False

        self.env['hr.leave'].create({
            'name': 'OT',
            'employee_id': payslip.employee_id.id,
            'request_date_from': date(2024, 1, 1),
            'request_date_to': date(2024, 1, 1),
            'request_hour_from': 8,
            'request_hour_to': 12,
            'number_of_hours': 4,
            'work_entry_type_id': ot_work_entry_type.id,
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 10000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 200.0, 'OTALLOW': 150.0, 'GOSI_COMP': 0.0, 'GOSI_EMP': 0.0, 'OT': 238.89, 'EOSP': 895.83, 'ANNUALP': 796.3, 'GROSS': 10988.89, 'NET': 10988.89, 'NETCOST': 10988.89}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_overtime_2(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        sa_ot_work_entry_type = self.env.ref('hr_work_entry.l10n_sa_work_entry_type_overtime')
        sa_ot_work_entry_type.write({'request_unit': 'day'})
        self.env['hr.leave'].create({
            'name': 'SA OT',
            'employee_id': payslip.employee_id.id,
            'request_date_from': date(2024, 1, 1),
            'request_date_to': date(2024, 1, 1),
            'work_entry_type_id': sa_ot_work_entry_type.id,
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 10000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 200.0, 'OTALLOW': 150.0, 'GOSI_COMP': 0.0, 'GOSI_EMP': 0.0, 'OT': 732.95, 'EOSP': 895.83, 'ANNUALP': 814.39, 'GROSS': 11482.95, 'NET': 11482.95, 'NETCOST': 11482.95}
        self._validate_payslip(payslip, payslip_results)

    def test_salary_advance_payslip(self):
        # Should not use `_generate_payslip` because we need to make sure that `ADV` property is created with 0.0 amount
        l10n_sa_salary_advance = self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan_Salary_advance')
        payslip = self.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])
        self.assertEqual(payslip._get_input_line_amount('ADV'), 0.0)
        for code, value in {
            l10n_sa_salary_advance.code: 2500.0,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()
        payslip_results = {'ADV': 2500.0, 'NET': 2500.0}
        self._validate_payslip(payslip, payslip_results)

    def test_saudi_payslip_after_salary_advance_payslip(self):
        l10n_sa_salary_advance = self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan_Salary_advance')
        adv_payslip = self.env['hr.payslip'].create([{
            'name': "Test Adv Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])

        for code, value in {
            l10n_sa_salary_advance.code: 2500.0,
        }.items():
            adv_payslip._set_input_value(code, value)
        adv_payslip.compute_sheet()
        adv_payslip.action_payslip_done()
        payslip = self.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id,
            'date_from': date(2024, 2, 1),
            'date_to': date(2024, 2, 29),
        }])
        payslip.compute_sheet()
        self.assertEqual(payslip._get_input_line_amount('ADVDED'), 2500.0)
        self.assertEqual(payslip._get_line_values(['ADVDED'])['ADVDED'][payslip.id]['total'], -2500.0)

    def test_salary_loan_payslip(self):
        loan_amount_rule = self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan_loan_amount')
        loan_payslip = self.env['hr.payslip'].create([{
            'title': "Test Loan Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
        }])
        for code, value in {
            loan_amount_rule.code: 5000.0,
        }.items():
            loan_payslip._set_input_value(code, value)
        loan_payslip.compute_sheet()
        loan_payslip.action_payslip_done()
        payslip = self.env['hr.payslip'].create([{
            'name': "Test Regular Payslip with Loan Deduction",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id,
            'date_from': date(2024, 2, 1),
            'date_to': date(2024, 2, 29),
        }])
        payslip.compute_sheet()
        self.assertEqual(payslip._get_input_line_amount('LOAN_DEDUCTION'), 5000.0)
        self.assertEqual(payslip._get_line_values(['LOAN_DEDUCTION'])['LOAN_DEDUCTION'][payslip.id]['total'], -5000.0)

    def test_disciplinary_action_warning(self):
        warning = self.env['l10n.sa.disciplinary.action'].create({
            'employee_id': self.saudi_employee.id,
            'action_type': 'warning',
        })
        self.assertFalse(warning.activity_type_id, 'Activity is created after approving the action')
        warning.action_approve()
        self.assertTrue(
            warning.activity_type_id.id == self.ref("l10n_sa_hr_payroll.mail_activity_data_l10n_sa_disciplinary_action_warning_mail"),
            'Activity is created after approving the action')

    def test_disciplinary_action_deduction(self):
        faulty_ded, perc_ded, custom_ded = self.env['l10n.sa.disciplinary.action'].create([
            {
                'employee_id': self.saudi_employee.id,
                'action_type': 'deduction',
                'amount_based_on': 'monthly_wage_percentage',
            },
            {
                # Deduction of 1300: (0.1 * (12000 + 1000))
                'employee_id': self.saudi_employee.id,
                'action_type': 'deduction',
                'amount_based_on': 'monthly_wage_percentage',
                'percentage': 0.1,
                'amount_base_basic': True,
                'amount_base_housing': True,
            },
            {
                # Deduction of fixed amount 300
                'employee_id': self.saudi_employee.id,
                'action_type': 'deduction',
                'amount_based_on': 'custom_amount',
                'amount': 300.0,
            },
        ])
        with self.assertRaises(UserError, msg='No categories were selected'):
            faulty_ded.action_approve()
        faulty_ded.amount_base_basic = True
        with self.assertRaises(UserError, msg='Percentage should be higher than 0%'):
            faulty_ded.action_approve()

        # Deduction of 2400: (0.2 * 12000)
        faulty_ded.percentage = 0.2
        faulty_ded.action_approve()
        self.assertFalse(faulty_ded.payslip_id, 'The disciplinary action will be linked to the first created payslip')

        payslip_1 = self.env['hr.payslip'].create({
            'employee_id': self.saudi_employee.id,
        })
        payslip_1.compute_sheet()
        self.assertTrue(faulty_ded.payslip_id == payslip_1, 'The disciplinary action should be linked to the created payslip')
        self.assertTrue(
            payslip_1.line_ids.filtered(lambda l: l.code == 'DISC_DED'),
            "Deduction line should appear in payslip lines",
        )
        payslip_results = {'BASIC': 12000.0, 'DISC_DED': -2400.0, 'NET': 10032.5}
        self._validate_payslip(payslip_1, payslip_results, skip_lines=True)

        perc_ded.action_approve()
        payslip_2 = self.env['hr.payslip'].create({
            'employee_id': self.saudi_employee.id,
        })
        payslip_2.compute_sheet()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'DISC_DED': -1300.0, 'NET': 11132.5}
        self._validate_payslip(payslip_2, payslip_results, skip_lines=True)

        custom_ded.action_approve()
        payslip_3 = self.env['hr.payslip'].create({
            'employee_id': self.saudi_employee.id,
        })
        payslip_3.compute_sheet()
        payslip_results = {'DISC_DED': -300.0, 'NET': 12132.5}
        self._validate_payslip(payslip_3, payslip_results, skip_lines=True)

    def test_saudi_payslip_with_attendance(self):
        if self.env["ir.module.module"]._get("hr_payroll_attendance").state != "installed":
            self.skipTest(
                "The test was skipped because the 'hr_payroll_attendance' module isn’t installed; therefore, attendance-based entries are unavailable."
            )
        self.saudi_employee.attendance_based = True
        payslip = self.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': self.saudi_employee.id,
            'version_id': self.saudi_employee.version_id.id,
            'company_id': self.env.company.id,
            'struct_id': self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
        }])
        payslip.compute_sheet()
        payslip_results = {
            'BASIC': 0.0,
        }
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_saudi_payslip_gosi_contribution(self):
        self.env['resource.calendar.leaves'].create([{
            'name': "Absence",
            'company_id': self.env.company.id,
            'resource_id': self.saudi_employee.resource_id.id,
            'date_from': datetime(2024, 1, 10, 6, 0, 0),
            'date_to': datetime(2024, 1, 11, 22, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_unpaid_leave').id
        }])

        payslip = self._generate_payslip(
            date(2024, 1, 1), date(2024, 1, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'UNPAID': -893.48, 'EOSP': 533.61, 'ANNUALP': 1042.39, 'GROSS': 13700.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 11539.02, 'NETCOST': 15534.02}
        self._validate_payslip(payslip, payslip_results)
