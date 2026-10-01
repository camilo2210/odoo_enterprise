# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
from datetime import date
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('ae')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('hr_payroll.group_hr_payroll_user')
        cls._setup_common(
            country=cls.env.ref('base.ae'),
            structure=cls.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure'),
            structure_type=cls.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure_type'),
            version_fields={
                'wage': 40000.0,
                'l10n_ae_housing_allowance': 400.0,
                'l10n_ae_transportation_allowance': 220.0,
                'l10n_ae_other_allowances': 100.0,
                'l10n_ae_airfare_allowance': 700.0,
                'l10n_ae_is_dews_applied': True,
            }
        )

        cls.work_entry_types = {
            entry_type.code: entry_type
            for entry_type in cls.env['hr.work.entry.type'].search([('country_id', '=', cls.env.ref('base.ae').id)])
        }
        (
            cls.env.ref('hr_work_entry.uae_work_entry_type_unpaid_leave') +
            cls.env.ref("hr_work_entry.uae_work_entry_type_sick_leave")
        ).sudo().requires_allocation = False

    def _get_payslip_property_amount(self, payslip, id):
        return payslip._get_input_line_amount(id)

    @classmethod
    def _create_worked_days(cls, name=False, code=False, number_of_days=0, number_of_hours=0, version_id=False):
        return Command.create({
            'name': name,
            'work_entry_type_id': cls.work_entry_types[code].id,
            'code': code,
            'number_of_days': number_of_days,
            'number_of_hours': number_of_hours,
            'version_id': version_id
        })

    def _test_eos_calculation(self, start_date, dismissal_date, payslip_start, payslip_end,
                            expected_eos, has_unpaid_leave=False, wage=15000.0, expected_eospc=None,
                            prior_months=0):
        """Helper method to test end of service salary rule calculations."""
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'structure_type_id': self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure_type').id,
            'country_id': self.env.ref('base.ae').id,
            'wage': wage,
            'date_version': start_date,
            'contract_date_start': start_date,
        })

        # Generate prior payslips to accrue EOSP provisions
        for i in range(1, prior_months + 1):
            prior_start = payslip_start.replace(day=1) - relativedelta(months=i)
            prior_end = prior_start + relativedelta(months=1, days=-1)

            prior_payslip = self._generate_payslip(prior_start, prior_end, employee_id=employee.id, version_id=employee.version_id.id)
            prior_payslip.compute_sheet()
            prior_payslip.action_payslip_done()

        if has_unpaid_leave:
            self.env['hr.leave'].create({
                'name': 'Unpaid Leave',
                'employee_id': employee.id,
                'work_entry_type_id': self.env.ref('hr_work_entry.uae_work_entry_type_unpaid_leave').id,
                'request_date_from': date(2025, 8, 4),
                'request_date_to': date(2025, 8, 8),
            })

        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': employee.id,
            'dismissal_date': dismissal_date,
            'departure_description': 'foo',
        })
        departure_notice.action_register()

        payslip = self._generate_payslip(payslip_start, payslip_end, employee_id=employee.id, version_id=employee.version_id.id)
        payslip.compute_sheet()
        self.assertEqual(
            payslip._get_line_values(['EOS'])['EOS'][payslip.id]['total'],
            expected_eos,
            "End of Service calculation is incorrect"
        )

        if expected_eospc is not None:
            self.assertEqual(
                payslip._get_line_values(['EOSPC'])['EOSPC'][payslip.id]['total'],
                expected_eospc,
                "End of Service Provision Correction calculation is incorrect"
            )

    def test_payslip_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_2(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        input_salary_arrears_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_salary_arrears_salary_rule')
        input_other_earnings_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_other_earnings_salary_rule')
        input_salary_deduction_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_salary_deduction_salary_rule')
        input_other_deduction_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_other_deduction_salary_rule')
        input_overtime_allowance_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_overtime_allowance')
        input_bonus_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_bonus_salary_rule')
        input_other_allowance_rule_id = self.env.ref('l10n_ae_hr_payroll.uae_salary_rule_other_allowance')

        payslip._set_input_values({
            input_salary_arrears_rule_id.code: 1000,
            input_other_earnings_rule_id.code: 2000,
            input_salary_deduction_rule_id.code: 500,
            input_other_deduction_rule_id.code: 200,
            input_overtime_allowance_rule_id.code: 300,
            input_bonus_rule_id.code: 400,
            input_other_allowance_rule_id.code: 600,
        })

        payslip.compute_sheet()

        payslip_results = {'BASIC': 40000.0, 'BONUS': 400.0, 'OTALLOWINP': 600.0, 'OTHER_DEDUCTIONS': -200.0, 'OTHER_EARNINGS': 2000.0, 'OVERTIMEALLOWINP': 300.0, 'SALARY_ARREARS': 1000.0, 'SALARY_DEDUCTIONS': -500.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3751.67, 'ALP': 4893.48, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 45020.0, 'NET': 39840.8, 'NETCOST': 53760.0}
        self._validate_payslip(payslip, payslip_results)

    def test_airfare_allowance(self):
        airfare_allowance_rule = self.env.ref('l10n_ae_hr_payroll.uae_airfare_allowance_salary_rule')
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip._set_input_value(airfare_allowance_rule.code, 2)
        payslip.compute_sheet()
        payslip_results = {'AIRFARE_ALLOWANCE': 1400.0, 'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3510.0, 'ALP': 4578.26, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 42120.0, 'NET': 37640.8, 'NETCOST': 51560.0}
        self._validate_payslip(payslip, payslip_results)

    def test_instant_pay_payslip_generation(self):
        instant_pay_structure = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay')
        payslip = self._generate_payslip(date(2023, 3, 1), date(2023, 3, 31), struct_id=instant_pay_structure.id)
        input_allowance_salary_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_allowance')
        input_commission_salary_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_commission')
        input_salary_advance_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_salary_advance')
        input_load_advance_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_loan_advance')
        input_deduction_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_deduction')
        payslip._set_input_values({
            input_allowance_salary_rule_id.code: 1000,
            input_commission_salary_rule_id.code: 800,
            input_salary_advance_rule_id.code: 1500,
            input_load_advance_rule_id.code: 1200,
            input_deduction_rule_id.code: 700,
        })
        payslip.compute_sheet()

        payslip_results = {'ALLOW': 1000.00, 'COMM': 800.00, 'ADV': 1500.00, 'LOAN': 1200.00, 'DED': -700.00, 'NET': 3800.00}
        self._validate_payslip(payslip, payslip_results)

    def test_salary_advance(self):
        instant_pay_structure = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay')
        uae_employee_structure = self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure')
        input_salary_advance_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_salary_advance')
        input_advance_recovery_rule_id = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_employee_payroll_structure_advance_recovery')
        # First salary advance payslip of 500 on 01/09/2024 and setting the advance amount to 500 and validate the payslip
        test_saladv_payslip1 = self._generate_payslip(
            date(2024, 9, 1), date(2024, 9, 30), struct_id=instant_pay_structure.id
        )
        test_saladv_payslip1._set_input_values({
            input_salary_advance_rule_id.code: 500,
        })
        test_saladv_payslip1.compute_sheet()
        test_saladv_payslip1.action_payslip_done()

        # Second salary advance payslip of 200 on 15/09/2024
        test_saladv_payslip2 = self._generate_payslip(
            date(2024, 9, 15), date(2024, 9, 30), struct_id=instant_pay_structure.id
        )
        test_saladv_payslip2._set_input_values({
            input_salary_advance_rule_id.code: 200,
        })

        test_saladv_payslip2.compute_sheet()
        test_saladv_payslip2.action_payslip_done()

        # September monthly payslip
        test_payslip_sept = self._generate_payslip(
            date(2024, 9, 1), date(2024, 9, 30), struct_id=uae_employee_structure.id
        )
        test_payslip_sept._compute_input_line_ids()
        # September monthly pay should have salary advance recovery = 700 by default
        amount_rec = self._get_payslip_property_amount(test_payslip_sept, input_advance_recovery_rule_id.code)
        self.assertEqual(amount_rec, 700)
        # Changing the recovery amount to 500 and validate the payslip
        test_payslip_sept._set_input_value('ADVREC', 500)
        test_payslip_sept.compute_sheet()
        test_payslip_sept.action_payslip_done()
        amount_rec = self._get_payslip_property_amount(test_payslip_sept, input_advance_recovery_rule_id.code)
        self.assertEqual(amount_rec, 500)

        # Third salary advance payslip of 300 on 1/10/2024
        test_saladv_payslip3 = self._generate_payslip(
            date(2024, 10, 1), date(2024, 10, 31), struct_id=instant_pay_structure.id
        )
        test_saladv_payslip3._set_input_values({
            input_salary_advance_rule_id.code: 300,
        })
        test_saladv_payslip3.compute_sheet()
        test_saladv_payslip3.action_payslip_done()

        # October monthly pay should have salary advance recovery = 500 (200+300) by default
        test_payslip_oct = self._generate_payslip(
            date(2024, 10, 1), date(2024, 10, 31), struct_id=uae_employee_structure.id
        )
        test_payslip_oct._compute_input_line_ids()
        test_payslip_oct.compute_sheet()
        test_payslip_oct.action_payslip_done()

        amount_rec = self._get_payslip_property_amount(test_payslip_oct, input_advance_recovery_rule_id.code)
        self.assertEqual(amount_rec, 500)

        # November monthly pay should have salary advance recovery = 0
        test_payslip_nov = self._generate_payslip(
            date(2024, 11, 1), date(2024, 11, 30), struct_id=uae_employee_structure.id
        )
        test_payslip_nov._compute_input_line_ids()
        test_payslip_nov.compute_sheet()
        test_payslip_nov.action_payslip_done()
        amount_rec = self._get_payslip_property_amount(test_payslip_nov, input_advance_recovery_rule_id.code)
        self.assertEqual(amount_rec, 0)

    @freeze_time("2017-02-20")
    def test_end_of_service_salary_rule_1(self):
        """Case: Employee worked 2 years, 8 months, and 15 days
        Expected: Calculate EOS for 2 years, 8 months and 15 days
        (2 years * 12 month / year) + 8 months = 32 months
        because the total is less than 6 years, ratio = 21 / 30
        (15_000 $/year) * ratio * (1/12 year/month) = 875 $/month
        (15_000 $/year) * ratio * (1/365 year/day) ~ 28.77 $/day

        total = 32 months * 875 $/month = 28_000 $
                15 days * 28.77 $/day ~ 432 $       +
              = 28_432 $
        """
        self._test_eos_calculation(
            start_date=date(2014, 6, 4),
            dismissal_date=date(2017, 2, 19),
            payslip_start=date(2017, 2, 1),
            payslip_end=date(2017, 2, 28),
            expected_eos=28_432.0,
            expected_eospc=27_182.0,  # 28_432.0 - (2 * 625.0)
            prior_months=2
        )

    @freeze_time("2025-01-31")
    def test_end_of_service_salary_rule_2(self):
        """Case: Employee worked 5 years, 5 months, and 17 days
        Expected: Calculate EOS for 5 years, 5 months and 17 days
        (5 years * 12 month / year) + 5 months = 65 months
        because the total is less than 6 years, ratio = 21 / 30
        (15_000 $/year) * ratio * (1/12 year/month) = 875 $/month
        (15_000 $/year) * ratio * (1/365 year/day) ~ 28.77 $/day

        total = 65 months * 875 $/month = 56_875 $
                17 days * 28.77 $/day ~ 490 $       +
              = 57_365 $
        """
        self._test_eos_calculation(
            start_date=date(2019, 7, 22),
            dismissal_date=date(2025, 1, 8),
            payslip_start=date(2025, 1, 1),
            payslip_end=date(2025, 1, 31),
            expected_eos=57_365.0,
            expected_eospc=56_115.0,  # 57_365.0 - (2 * 625.0)
            prior_months=2
        )

    @freeze_time("2025-01-31")
    def test_end_of_service_salary_rule_3(self):
        """Case: Employee worked 6 years, 5 months, and 17 days
        Expected: Calculate EOS for 6 years, 5 months and 17 days
        (6 years * 12 month / year) + 5 months = 77 months
        because the total is greater than 6 years, ratio = 1
        (15_000 $/year) * ratio * (1/12 year/month) = 1250 $/month
        (15_000 $/year) * ratio * (1/365 year/day) ~ 41.1 $/day

        total = 60 months * 1250 * (21/30) $/month = 52_500 $
                17 months * 1250 $/month = 21_250 $
                17 days * 41.1 $/day ~ 699 $       +
              = 74_449 $
        """
        self._test_eos_calculation(
            start_date=date(2018, 7, 22),
            dismissal_date=date(2025, 1, 8),
            payslip_start=date(2025, 1, 1),
            payslip_end=date(2025, 1, 31),
            expected_eos=74_449.0,
            expected_eospc=71_949.0,  # 74_449.0 - (2 * 1250.0)
            prior_months=2
        )

    @freeze_time("2025-09-01")
    def test_end_of_service_salary_rule_4(self):
        """Case: Employee worked 2 years, 8 months, and 15 days with 5 unpaid days
        Expected: Calculate EOS for 2 years, 8 months and 10 days
        (2 years * 12 month / year) + 8 months = 32 months
        because the total is less than 6 years, ratio = 21 / 30
        (15_000 $/year) * ratio * (1/12 year/month) = 875 $/month
        (15_000 $/year) * ratio * (1/365 year/day) ~ 28.77 $/day

        total = 32 months * 875 $/month = 28000 $
                10 days * 28.77 $/day ~ 288 $       +
              = 28_288 $
        """
        self._test_eos_calculation(
            start_date=date(2022, 12, 16),
            dismissal_date=date(2025, 8, 31),
            payslip_start=date(2025, 8, 1),
            payslip_end=date(2025, 8, 31),
            expected_eos=28_288.0,
            expected_eospc=27_038.0,  # 28_288.0 - (2 * 625.0)
            has_unpaid_leave=True,
            prior_months=2
        )

    @freeze_time("2025-09-01")
    def test_end_of_service_salary_rule_5(self):
        """Case: Employee worked 6 years and 3 days with 5 unpaid days
        Expected: Calculate EOS for 5 years, 11 months and 29 days
        (5 years * 12 month / year) + 11 months = 71 months
        because the total is less than 6 years, ratio = 21 / 30
        (15_000 $/year) * ratio * (1/12 year/month) = 875 $/month
        (15_000 $/year) * ratio * (1/365 year/day) ~ 28.77 $/day

        total = 71 months * 875 $/month = 62_125 $
                29 days * 28.77 $/day ~ 835 $       +
              = 62_960 $
        """
        self._test_eos_calculation(
            start_date=date(2019, 8, 28),
            dismissal_date=date(2025, 8, 31),
            payslip_start=date(2025, 8, 1),
            payslip_end=date(2025, 8, 31),
            expected_eos=62_960.0,
            expected_eospc=61_710.0,  # 62_960.0 - (2 * 625.0)
            has_unpaid_leave=True,
            prior_months=2
        )

    @freeze_time("2025-09-01")
    def test_end_of_service_salary_rule_6(self):
        """Case: Employee worked 7 years and 3 days with 5 unpaid days
        Expected: Calculate EOS for 6 years, 11 months and 29 days
        (6 years * 12 month / year) + 11 months = 83 months
        because the total is greater than 6 years, ratio = 1
        (15_000 $/year) * ratio * (1/12 year/month) = 1250 $/month
        (15_000 $/year) * ratio * (1/365 year/day) ~ 41.1 $/day

        total = 60 months * 1250 * (21/30) $/month = 52_500 $
                23 months * 1250 $/month = 28_750 $
                29 days * 41.1 $/day ~ 1192 $       +
              = 82_442 $
        """
        self._test_eos_calculation(
            start_date=date(2018, 8, 28),
            dismissal_date=date(2025, 8, 31),
            payslip_start=date(2025, 8, 1),
            payslip_end=date(2025, 8, 31),
            expected_eos=82_442.0,
            expected_eospc=79_942.0,  # 82442 - (2 * 1250)
            has_unpaid_leave=True,
            prior_months=2
        )

    def test_payslip_attendance_1(self):
        if self.env['ir.module.module']._get('hr_payroll_attendance').state != 'installed':
            self.skipTest("Skipping test because hr_payroll_attendance is not installed.")

        self.employee.country_id = False
        self.version.write({
            'contract_date_start': '2025-01-01',
            'attendance_based': True,
            'wage': 5000,
            'wage_type': 'monthly',
            'l10n_ae_housing_allowance': 2000,
            'l10n_ae_transportation_allowance': 1000,
            'l10n_ae_other_allowances': 100,
            'l10n_ae_is_dews_applied': False,
        })

        worked_days_vals = [
            {'name': 'Unpaid', 'code': '158.00', 'number_of_hours': 16, 'number_of_days': 2, 'version_id': self.version.id},
            {'name': 'Paid Time Off', 'code': '016.00', 'number_of_hours': 24, 'number_of_days': 3, 'version_id': self.version.id},
            {'name': 'Sick Leave', 'code': '013.00', 'number_of_hours': 24, 'number_of_days': 3, 'version_id': self.version.id},
            {'name': 'Out of Contract', 'code': '000.00', 'number_of_hours': 32, 'number_of_days': 4, 'version_id': self.version.id},
            {'name': 'Attendance', 'code': '002.00', 'number_of_hours': 88, 'number_of_days': 11, 'version_id': self.version.id},
        ]

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': datetime.date(2025, 7, 1),
            'date_to': datetime.date(2025, 7, 31),
            'struct_id': self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id,
        })
        payslip.write({
            "worked_days_line_ids": [self._create_worked_days(**vals) for vals in worked_days_vals],
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 2391.3, 'HOUALLOW': 956.52, 'TRAALLOW': 478.26, 'OTALLOW': 47.83, 'EOSP': 130.17, 'ALP': 421.08, 'ALPPOUT': 505.29, 'SL': 0.0, 'AEPAID': 1056.48, 'GROSS': 4930.39, 'NET': 4930.39, 'NETCOST': 4930.39}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_attendance_2(self):
        if self.env['ir.module.module']._get('hr_payroll_attendance').state != 'installed':
            self.skipTest("Skipping test because hr_payroll_attendance is not installed.")

        self.employee.country_id = False
        self.version.write({
            'contract_date_start': '2025-01-01',
            'attendance_based': True,
            'wage': 5000,
            'hourly_wage': 44.02,
            'wage_type': 'hourly',
            'l10n_ae_housing_allowance': 2000,
            'l10n_ae_transportation_allowance': 1000,
            'l10n_ae_other_allowances': 100,
            'l10n_ae_is_dews_applied': False,
        })

        worked_days_vals = [
            {'name': 'Unpaid', 'code': '158.00', 'number_of_hours': 16, 'number_of_days': 2, 'version_id': self.version.id},
            {'name': 'Paid Time Off', 'code': '016.00', 'number_of_hours': 24, 'number_of_days': 3, 'version_id': self.version.id},
            {'name': 'Sick Leave', 'code': '013.00', 'number_of_hours': 24, 'number_of_days': 3, 'version_id': self.version.id},
            {'name': 'Out of Contract', 'code': '000.00', 'number_of_hours': 32, 'number_of_days': 4, 'version_id': self.version.id},
            {'name': 'Attendance', 'code': '002.00', 'number_of_hours': 72, 'number_of_days': 9, 'version_id': self.version.id},
        ]

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': datetime.date(2025, 6, 1),
            'date_to': datetime.date(2025, 6, 30),
            'struct_id': self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id,
        })
        payslip.write({
            "worked_days_line_ids": [self._create_worked_days(**vals) for vals in worked_days_vals]
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 2142.86, 'EOSP': 71.43, 'ALP': 255.1, 'ALPPOUT': 306.12, 'SL': 0.0, 'AEPAID': 1056.48, 'GROSS': 3199.34, 'NET': 3199.34, 'NETCOST': 3199.34}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_attendance_3(self):
        if self.env['ir.module.module']._get('hr_payroll_attendance').state != 'installed':
            self.skipTest("Skipping test because hr_payroll_attendance is not installed.")

        self.employee.country_id = False
        self.version.write({
            'contract_date_start': '2025-01-01',
            'attendance_based': True,
            'wage': 10000,
            'wage_type': 'monthly',
            'l10n_ae_housing_allowance': 2000,
            'l10n_ae_transportation_allowance': 1000,
            'l10n_ae_other_allowances': 100,
            'l10n_ae_is_dews_applied': False,
        })

        worked_days_vals = [
            {'name': 'Attendance', 'code': '002.00', 'number_of_hours': 80, 'number_of_days': 20, 'version_id': self.version.id},
        ]

        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': datetime.date(2025, 11, 1),
            'date_to': datetime.date(2025, 11, 30),
            'struct_id': self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id,
        })
        payslip.write({
            "worked_days_line_ids": [self._create_worked_days(**vals) for vals in worked_days_vals],
        })
        payslip.compute_sheet()
        payslip_results = {'BASIC': 5000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 500.0, 'OTALLOW': 50.0, 'EOSP': 272.92, 'ALP': 818.75, 'AEPAID': 0.0, 'GROSS': 6550.0, 'NET': 6550.0, 'NETCOST': 6550.0}
        self._validate_payslip(payslip, payslip_results)

    def test_sick_leave_salary_rule(self):
        # 0% deduction for the first 15 sick days, 50% deduction from 16-45 sick days, and 100% deduction for 45+ sick days.
        employee_4 = self.env['hr.employee'].create({
            'name': 'Test Employee Rambo',
            'contract_date_start': date(2025, 7, 22),
            'date_version': date(2025, 7, 22),
            'wage': 5000.0,
        })
        uae_employee_structure = self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure')
        self.sick_time_off_type = self.env.ref("hr_work_entry.uae_work_entry_type_sick_leave")
        # Test with a leave that extends over two payslip periods
        self.env['hr.leave'].create({
                'name': 'Sick Time off',
                'employee_id': employee_4.id,
                'work_entry_type_id': self.sick_time_off_type.id,
                'request_date_from': datetime.date(2025, 9, 8),
                'request_date_to': datetime.date(2025, 10, 8),
        })
        payslip_1 = self.env['hr.payslip'].create({
            'employee_id': employee_4.id,
            'version_id': employee_4.version_id.id,
            'date_from': datetime.date(2025, 9, 1),
            'date_to': datetime.date(2025, 9, 30),
            'struct_id': uae_employee_structure.id,

        })
        payslip_1.compute_sheet()
        test_leave_days = payslip_1.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(test_leave_days.number_of_days, 17.0)
        payslip_1_results = {'BASIC': 5000.0, 'HOUALLOW': 0.0, 'TRAALLOW': 0.0, 'OTALLOW': 0.0, 'EOSP': 208.33, 'ALP': 568.18, 'SL': -166.67, 'GROSS': 5000.0, 'NET': 4833.33, 'NETCOST': 4833.33}
        self._validate_payslip(payslip_1, payslip_1_results, skip_lines=True)
        # October Payslip
        payslip_2 = self.env['hr.payslip'].create({
            'employee_id': employee_4.id,
            'version_id': employee_4.version_id.id,
            'date_from': datetime.date(2025, 10, 1),
            'date_to': datetime.date(2025, 10, 31),
            'struct_id': uae_employee_structure.id,

        })
        payslip_2.compute_sheet()
        test_leave_days_2 = payslip_2.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(test_leave_days_2.number_of_days, 6.0)
        payslip_2_results = {'BASIC': 5000.0, 'HOUALLOW': 0.0, 'TRAALLOW': 0.0, 'OTALLOW': 0.0, 'EOSP': 208.33, 'ALP': 543.48, 'SL': -500.0, 'GROSS': 5000.0, 'NET': 4500.0, 'NETCOST': 4500.0}
        self._validate_payslip(payslip_2, payslip_2_results, skip_lines=True)

    def test_out_of_contract_salary_rule(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee amah',
            'contract_date_start': date(2025, 10, 15),
            'date_version': date(2025, 10, 15),
            'wage': 10000.0,
        })
        payslip = self._generate_payslip(date(2025, 10, 1), date(2025, 10, 31), version_id=employee.version_id.id, employee_id=employee.id)
        payslip_results = {'OOC': -4516.13, 'GROSS': 5483.87, 'NET': 5483.87}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_social_insurance_rules_non_emirati(self):
        """Test that non-Emirati employees are not subject to social insurance rules"""
        # Change employee to non-Emirati
        self.employee.country_id = self.env.ref('base.us')

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))

        # Expected: No SICC/SIEC lines should exist for non-Emirati employees
        line_values = payslip._get_line_values(['SIEC', 'SICC'])
        self.assertNotIn('SIEC', line_values, "Non-Emirati should not have employee social insurance contribution")
        self.assertNotIn('SICC', line_values, "Non-Emirati should not have company social insurance contribution")

    def test_social_insurance_rules_dubai_before_cutoff(self):
        """Test GPSSA rules for Dubai employee before pension enrollment cutoff (Oct 31, 2023)"""
        # Set company to Dubai (non-Abu Dhabi)
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_du').id,  # Dubai
            'l10n_ae_is_private_sector': False,
        })

        # Set pension enrollment date before GPSSA cutoff
        self.version.l10n_ae_pansion_enrollment_date = date(2023, 10, 30)

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -2036.0, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 38684.0, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_social_insurance_rules_dubai_after_cutoff(self):
        """Test GPSSA rules for Dubai employee after pension enrollment cutoff (Oct 31, 2023)"""
        # Set company to Dubai (non-Abu Dhabi)
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_du').id,  # Dubai
            'l10n_ae_is_private_sector': False,
        })

        # Set pension enrollment date after GPSSA cutoff
        self.version.l10n_ae_pansion_enrollment_date = date(2023, 11, 1)

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_social_insurance_rules_dubai_private_sector_high_salary(self):
        """Test GPSSA rules for Dubai private sector with high salary (>20K) after cutoff"""
        # Set company to Dubai private sector
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_du').id,  # Dubai
            'l10n_ae_is_private_sector': True,
        })

        # Set pension enrollment date after GPSSA cutoff
        self.version.l10n_ae_pansion_enrollment_date = date(2023, 11, 1)

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        # High salary (40720 > 20K) + private sector = 15% company contribution
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_social_insurance_rules_dubai_private_sector_low_salary(self):
        """Test GPSSA rules for Dubai private sector with low salary (<20K) after cutoff"""
        # Set company to Dubai private sector
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_du').id,  # Dubai
            'l10n_ae_is_private_sector': True,
        })

        # Set low salary (total gross < 20K)
        self.version.write({
            'wage': 15000.0,
            'l10n_ae_housing_allowance': 2000.0,
            'l10n_ae_transportation_allowance': 1000.0,
            'l10n_ae_other_allowances': 500.0,
            'l10n_ae_pansion_enrollment_date': date(2023, 11, 1),  # After cutoff
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        # Low salary (18500 < 20K) + private sector = 12.5% company contribution
        payslip_results = {'BASIC': 15000.0, 'HOUALLOW': 2000.0, 'TRAALLOW': 1000.0, 'OTALLOW': 500.0, 'EOSP': 1541.67, 'ALP': 2010.87, 'SICC': 2312.5, 'SIEC': -2035.0, 'DEWSCOMP': 1249.5, 'GROSS': 18500.0, 'NET': 16465.0, 'NETCOST': 22062.0}
        self._validate_payslip(payslip, payslip_results)

    def test_social_insurance_rules_abu_dhabi_before_cutoff(self):
        """Test ADPF rules for Abu Dhabi employee before pension enrollment cutoff (Dec 1, 2023)"""
        # Set company to Abu Dhabi
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_az').id,  # Abu Dhabi
            'l10n_ae_is_private_sector': False,
        })

        # Set pension enrollment date before ADPF cutoff
        self.version.l10n_ae_pansion_enrollment_date = date(2023, 11, 30)

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -2036.0, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 38684.0, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_social_insurance_rules_abu_dhabi_after_cutoff(self):
        """Test ADPF rules for Abu Dhabi employee after pension enrollment cutoff (Dec 1, 2023)"""
        # Set company to Abu Dhabi
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_az').id,  # Abu Dhabi
            'l10n_ae_is_private_sector': False,
        })

        # Set pension enrollment date after ADPF cutoff
        self.version.l10n_ae_pansion_enrollment_date = date(2023, 12, 1)

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_social_insurance_rules_abu_dhabi_private_sector(self):
        """Test ADPF rules for Abu Dhabi private sector (should still be 15% company contribution)"""
        # Set company to Abu Dhabi private sector
        self.env.company.write({
            'state_id': self.env.ref('base.state_ae_az').id,  # Abu Dhabi
            'l10n_ae_is_private_sector': True,
        })

        # Set pension enrollment date after ADPF cutoff
        self.version.l10n_ae_pansion_enrollment_date = date(2023, 12, 1)

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        # Abu Dhabi always 15% company contribution regardless of private sector
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_dewsemp_rules_applied(self):
        """Test DEWSEMP rule when applied to the employee"""
        self.version.write({
            'l10n_ae_is_dews_applied': True,
            'l10n_ae_dews_emp_contribution': 0.05,
        })

        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 3393.33, 'ALP': 4426.09, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'DEWSEMP': -2000.0, 'GROSS': 40720.0, 'NET': 34240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

    def test_eos_provision_correction_resigned_no_benefit(self):
        self.employee.version_id.contract_date_start = date(2025, 1, 1)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 28))
        payslip.compute_sheet()
        payslip.action_payslip_done()
        # EOSP: 1696.67
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 1696.67, 'ALP': 5090.0, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 2332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 49160.0}
        self._validate_payslip(payslip, payslip_results)

        payslip2 = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        payslip2.compute_sheet()
        payslip2.action_payslip_done()
        # EOSP: 1696.67
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 1696.67, 'ALP': 5090.0, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 2332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 49160.0}
        self._validate_payslip(payslip2, payslip_results)

        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 1),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
        }]).action_register()

        final_slip = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 28))
        final_slip.compute_sheet()
        # EOS: 0, EOSPC: 0 - (1696.67 + 1696.67 ): -3393.34
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOS': 0.0, 'EOSP': 484.76, 'EOSPC': -3393.34, 'ALP': 5090.0, 'DEWSCOMP': 2332.0, 'OOC': -39265.71, 'ALEA': 10180.0, 'ALED': 0.0, 'GROSS': 11634.29, 'NET': 11634.29, 'NETCOST': 17359.63}
        self._validate_payslip(final_slip, payslip_results)

    def test_eos_provision_correction_resigned_reduced_benefit(self):
        self.employee.version_id.contract_date_start = date(2020, 1, 1)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 28))
        payslip.compute_sheet()
        payslip.action_payslip_done()
        # EOSP: 1696.67
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 1696.67, 'ALP': 5090.0, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip, payslip_results)

        payslip2 = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        payslip2.compute_sheet()
        payslip2.action_payslip_done()
        # EOSP: 1696.67
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOSP': 1696.67, 'ALP': 5090.0, 'SICC': 6108.0, 'SIEC': -4479.2, 'DEWSCOMP': 3332.0, 'GROSS': 40720.0, 'NET': 36240.8, 'NETCOST': 50160.0}
        self._validate_payslip(payslip2, payslip_results)

        self.env['hr.employee.departure'].create([{
            'employee_id': self.employee.id,
            'dismissal_date': date(2025, 3, 1),
            'departure_reason_id': self.env.ref('hr.departure_resigned').id,
        }]).action_register()

        final_slip = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 28))
        final_slip.compute_sheet()
        # EOSPC: 144667.0 - 1696.67 * 2
        # EOSPC: 141273.66
        payslip_results = {'BASIC': 40000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 220.0, 'OTALLOW': 100.0, 'EOS': 144667.0, 'EOSP': 2206.99, 'EOSPC': 141273.66, 'ALP': 23173.38, 'DEWSCOMP': 3332.0, 'OOC': -39265.71, 'ALEA': 10180.0, 'ALED': 0.0, 'GROSS': 156301.29, 'NET': 156301.29, 'NETCOST': 300906.95}
        self._validate_payslip(final_slip, payslip_results)

    def test_sick_leave_cross_year(self):
        """Test sick leave starting in previous year and continuing into current year.
        Ensures YTD sick days only start counting from Jan 1.
        """

        employee = self.env['hr.employee'].create({
            'name': 'Cross Year Sick Leave Employee',
            'contract_date_start': date(2024, 1, 1),
            'date_version': date(2024, 1, 1),
            'wage': 5000.0,
        })
        structure = self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure')
        sick_time_off_type = self.env.ref("hr_work_entry.uae_work_entry_type_sick_leave")
        # Sick leave spanning previous year to current year
        self.env['hr.leave'].create({
            'name': 'Cross Year Sick Leave',
            'employee_id': employee.id,
            'work_entry_type_id': sick_time_off_type.id,
            'request_date_from': date(2024, 12, 20),
            'request_date_to': date(2025, 1, 31),
        })
        # December payslip (previous year)
        payslip_dec = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31), version_id=employee.version_id.id, employee_id=employee.id, struct_id=structure.id)
        payslip_dec.compute_sheet()
        dec_sick_days = payslip_dec.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(dec_sick_days.number_of_days, 8.0)
        # Since this is the previous year, deduction bands restart next year
        payslip_dec_results = {'BASIC': 5000.0, 'HOUALLOW': 0.0, 'TRAALLOW': 0.0, 'OTALLOW': 0.0, 'EOSP': 208.33, 'ALP': 568.18, 'SL': 0.0, 'GROSS': 5000.0, 'NET': 5000.0, 'NETCOST': 5000.0}
        self._validate_payslip(payslip_dec, payslip_dec_results, skip_lines=True)
        # January payslip
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31), version_id=employee.version_id.id, employee_id=employee.id, struct_id=structure.id)
        payslip.compute_sheet()
        sick_days = payslip.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(sick_days.number_of_days, 23.0)
        # Expected deduction:
        # First 15 days = 0
        # Day 16-23 = 8 days at 50%
        # 8 * (166.67 * 0.5) = 666.67
        payslip_results = {'BASIC': 5000.0, 'HOUALLOW': 0.0, 'TRAALLOW': 0.0, 'OTALLOW': 0.0, 'EOSP': 208.33, 'ALP': 543.48, 'SL': -666.67, 'GROSS': 5000.0, 'NET': 4333.33, 'NETCOST': 4333.33}
        self._validate_payslip(payslip, payslip_results, skip_lines=True)

    def test_sick_leave_multiple_separate_leaves(self):
        """Test sick leave rule when leaves are taken in separate months.
        Jan: 10 days
        Feb: 10 days
        Mar: 1 day
        Total YTD = 21 days (deduction should apply after 15 days)
        """

        employee = self.env['hr.employee'].create({
            'name': 'Test Employee Multi Leave',
            'contract_date_start': date(2025, 1, 1),
            'date_version': date(2025, 1, 1),
            'wage': 5000.0,
        })
        structure = self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure')
        sick_time_off_type = self.env.ref("hr_work_entry.uae_work_entry_type_sick_leave")
        # Batch create leaves
        self.env['hr.leave'].create([
            {
                'name': 'Jan Sick Leave',
                'employee_id': employee.id,
                'work_entry_type_id': sick_time_off_type.id,
                'request_date_from': date(2025, 1, 1),
                'request_date_to': date(2025, 1, 14),
            },
            {
                'name': 'Feb Sick Leave',
                'employee_id': employee.id,
                'work_entry_type_id': sick_time_off_type.id,
                'request_date_from': date(2025, 2, 2),
                'request_date_to': date(2025, 2, 14),
            },
            {
                'name': 'Mar Sick Leave',
                'employee_id': employee.id,
                'work_entry_type_id': sick_time_off_type.id,
                'request_date_from': date(2025, 3, 3),
                'request_date_to': date(2025, 3, 3),
            },
        ])
        daily_salary = 5000 / 30
        # January Payslip
        payslip_jan = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31), version_id=employee.version_id.id, employee_id=employee.id, struct_id=structure.id)
        payslip_jan.compute_sheet()
        self.assertEqual(payslip_jan.year_to_date_sick_days, 10)
        jan_leave_days = payslip_jan.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(jan_leave_days.number_of_days, 10)
        sl_line = payslip_jan.line_ids.filtered(lambda l: l.code == 'SL')
        self.assertEqual(sl_line.total, 0)  # first 15 days -> no deduction
        # February Payslip
        payslip_feb = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28), version_id=employee.version_id.id, employee_id=employee.id, struct_id=structure.id)
        payslip_feb.compute_sheet()
        payslip_feb.compute_sheet()
        self.assertEqual(payslip_feb.year_to_date_sick_days, 20)
        feb_leave_days = payslip_feb.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(feb_leave_days.number_of_days, 10)
        # days 16-20, 5 days at 50%
        expected_feb_deduction = -(5 * 0.5 * daily_salary)
        sl_line = payslip_feb.line_ids.filtered(lambda l: l.code == 'SL')
        self.assertAlmostEqual(sl_line.total, expected_feb_deduction, places=2)
        # March Payslip
        payslip_mar = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 31), version_id=employee.version_id.id, employee_id=employee.id, struct_id=structure.id)
        payslip_mar.compute_sheet()
        self.assertEqual(payslip_mar.year_to_date_sick_days, 21)
        mar_leave_days = payslip_mar.worked_days_line_ids.filtered(lambda l: l.code == '013.00')
        self.assertEqual(mar_leave_days.number_of_days, 1)
        # day 21, 50%
        expected_mar_deduction = -(0.5 * daily_salary)
        sl_line = payslip_mar.line_ids.filtered(lambda l: l.code == 'SL')
        self.assertAlmostEqual(sl_line.total, expected_mar_deduction, places=2)

    def test_payslip_overtime(self):
        self.employee_test = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'structure_type_id': self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure_type').id,
            'country_id': self.env.ref('base.ae').id,
            'date_version': date(2025, 3, 1),
            'contract_date_start': date(2025, 3, 1),
            'wage': 5000
        })
        ae_ot_work_entry_type = self.env.ref('hr_work_entry.uae_work_entry_type_overtime')
        ae_ot_work_entry_type.sudo().write({'requires_allocation': False, 'request_unit': 'day'})
        if 'overtime_deductible' in ae_ot_work_entry_type:
            ae_ot_work_entry_type.overtime_deductible = False
        self.env['hr.leave'].create({
            'name': 'AE OT',
            'employee_id': self.employee_test.id,
            'request_date_from': date(2026, 3, 11),
            'request_date_to': date(2026, 3, 11),
            'work_entry_type_id': ae_ot_work_entry_type.id,
        })
        payslip_test = self._generate_payslip(date(2026, 3, 1), date(2026, 3, 31), employee_id=self.employee_test.id, version_id=self.employee_test.version_id.id)
        payslip_test.compute_sheet()
        payslip_results = {'BASIC': 5000.0, 'HOUALLOW': 0.0, 'TRAALLOW': 0.0, 'OTALLOW': 0.0, 'EOSP': 208.33, 'ALP': 595.24, 'SICC': 750.0, 'SIEC': -550.0, 'OT': 227.27, 'GROSS': 5227.27, 'NET': 4677.27, 'NETCOST': 5977.27}
        self._validate_payslip(payslip_test, payslip_results)

    def test_net_cost_calculation(self):
        new_category = self.env['hr.salary.rule.category'].create({
            'name': 'new_category',
            'code': 'new_cat',
            'parent_id': self.env.ref('hr_payroll.COMP').id,
            'country_id': self.country.id
        })
        new_child = self.env['hr.salary.rule.category'].create({
            'name': 'new_child_category',
            'code': 'new_ch_cat',
            'parent_id': new_category.id,
            'country_id': self.country.id
        })
        simple_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule',
            'code': 'new_ru',
            'category_ids': [(4, new_child.id)],
            'amount_fix': 100,
            'struct_ids': [(4, self.structure.id)]
        })
        double_cat_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule_2',
            'code': 'new_ru2',
            'category_ids': [(4, new_category.id), (4, self.env.ref('hr_payroll.DED').id)],
            'amount_fix': 200,
            'struct_ids': [(4, self.structure.id)]
        })
        negative_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule_3',
            'code': 'new_ru3',
            'category_ids': [(4, self.env.ref('hr_payroll.COMP').id)],
            'amount_fix': -50,
            'struct_ids': [(4, self.structure.id)]
        })
        _irrelevant_salary_rule = self.env['hr.salary.rule'].create({
            'name': 'new_rule_4',
            'code': 'new_ru4',
            'category_ids': [(4, self.env.ref('hr_payroll.DED').id)],
            'amount_fix': -500,
            'struct_ids': [(4, self.structure.id)]
        })

        test_payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        test_payslip.compute_sheet()
        company_contribution = abs(simple_salary_rule.amount_fix) \
                             + abs(double_cat_salary_rule.amount_fix) \
                             + abs(negative_salary_rule.amount_fix) \
                             + abs(test_payslip._get_line_values(['SIEC'])['SIEC'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['SICC'])['SICC'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['DEWSCOMP'])['DEWSCOMP'][test_payslip.id]['total']) \
                             + abs(test_payslip._get_line_values(['DEWSEMP'])['DEWSEMP'][test_payslip.id]['total'])
        expected_net_cost = test_payslip.net_wage + company_contribution
        calcuted_net_cost = test_payslip._get_line_values(['NETCOST'])['NETCOST'][test_payslip.id]['total']
        self.assertEqual(calcuted_net_cost, expected_net_cost, "Net Cost calculation is incorrect")
