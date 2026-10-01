# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from freezegun import freeze_time

from odoo.tests.common import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('om')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.om'),
            structure=cls.env.ref('l10n_om_hr_payroll.l10n_om_monthly_pay'),
            structure_type=cls.env.ref('l10n_om_hr_payroll.l10n_om_employee'),
            resource_calendar=cls.env.ref('l10n_om_hr_payroll.l10n_om_resource_calendar_def_40h'),
            tz='Asia/Muscat',
            version_fields={
                'wage': 2660000,
                'date_version': date(2020, 1, 1),
            },
            employee_fields={
            'name': 'Oman Employee Old',
            'wage': 2660000,
            'contract_date_start': date(2020, 1, 1),
            'l10n_om_employee_is_eos_eligible': True,
            'structure_type_id': cls.env.ref('l10n_om_hr_payroll.l10n_om_employee').id,
            'resource_calendar_id': cls.env.ref('l10n_om_hr_payroll.l10n_om_resource_calendar_def_40h').id,
            },
        )
        cls.paid_time_off_type = cls.env.ref('hr_work_entry.om_work_entry_type_legal_leave')
        cls.env.company.l10n_om_annual_work_entry_type_id = cls.paid_time_off_type
        cls.env['hr.leave.allocation'].create([
            {
                'name': 'Annual Leave Allocation',
                'employee_id': cls.employee.id,
                'date_from': date(2025, 1, 1),
                'work_entry_type_id': cls.paid_time_off_type.id,
                'number_of_days': 21,
            },
        ]).action_approve()

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'BASIC': 2660000.0, 'SPF_COMP': -385700.0, 'SPF_EMP': -212800.0, 'EOSP': 221666.667, 'ANNUALPROV': 302272.727, 'NET': 2447200.0, 'NETCOST': 2798239.394}
        self._validate_payslip(payslip, payslip_results)

    def _create_overtime_entry(self, employee, date_from, date_to, hour_from, hour_to, hours, work_entry_type):
        work_entry_type.requires_allocation = False
        work_entry_type.request_unit = 'hour'
        self.env['hr.leave'].create({
            'name': 'Overtime',
            'employee_id': employee.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'request_hour_from': hour_from,
            'request_hour_to': hour_to,
            'number_of_hours': hours,
            'work_entry_type_id': work_entry_type.id,
        })

    def test_oman_overtime_calculation(self):
        self._create_overtime_entry(self.employee, date(2024, 1, 1), date(2024, 1, 1), 8, 12, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_work_days_daytime'))
        self._create_overtime_entry(self.employee, date(2024, 1, 8), date(2024, 1, 8), 20, 24, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_work_days_nighttime'))
        self._create_overtime_entry(self.employee, date(2024, 1, 6), date(2024, 1, 6), 8, 12, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_rest_days'))
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip.compute_sheet()
        self._validate_worked_days(payslip, {
            'OMOTWDD': (0.5, 4, 72282.609),
            'OMOTWDN': (0.5, 4, 86739.13),
            'OMOTPHD': (0.5, 4, 115652.174),
        }, skip_lines=True)
        payslip_results = {'BASIC': 2891304.348, 'SPF_COMP': -419239.13, 'SPF_EMP': -231304.348, 'EOSP': 240942.029, 'ANNUALPROV': 314272.212, 'NET': 2660000.0, 'NETCOST': 3027279.459}
        self._validate_payslip(payslip, payslip_results)

    def test_oman_special_overtime_calculation(self):
        self._create_overtime_entry(self.employee, date(2025, 2, 1), date(2025, 2, 1), 8, 12, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_special_work_days_daytime'))
        self._create_overtime_entry(self.employee, date(2025, 2, 8), date(2025, 2, 8), 20, 24, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_special_work_days_nighttime'))
        self._create_overtime_entry(self.employee, date(2025, 2, 6), date(2025, 2, 6), 8, 12, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_special_rest_days'))
        payslip = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        payslip.compute_sheet()
        self._validate_worked_days(payslip, {
            'OMSOTWDD': (0.5, 4, 99750.0),
            'OMSOTWDN': (0.5, 4, 116375.0),
            'OMSOTPHD': (0.5, 4, 199500.0),
        }, skip_lines=True)
        payslip_results = {'BASIC': 3025750.0, 'SPF_COMP': -438733.75, 'SPF_EMP': -242060.0, 'EOSP': 252145.833, 'ANNUALPROV': 378218.75, 'NET': 2783690.0, 'NETCOST': 3217380.833}
        self._validate_payslip(payslip, payslip_results)

    @freeze_time("2025-04-01")
    def test_oman_end_of_service(self):
        self._generate_leave(self.employee, date(2025, 3, 10), date(2025, 3, 13), self.paid_time_off_type, False)

        self.env['hr.employee.departure'].create([
            {
                'employee_id': self.employee.id,
                'departure_date': date(2025, 3, 31),
                'departure_description': 'End of contract',
                'departure_reason_id': self.env.ref('hr.departure_fired').id,
            },
        ]).action_register()

        self.employee.departure_date = date(2025, 3, 31)

        payslip = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 31), employee_id=self.employee.id)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 2660000.0, 'SPF_COMP': -385700.0, 'SPF_EMP': -212800.0, 'ANNUALCOMP': 2055454.545, 'ANNUALPROV': 302272.727, 'ANNUALPROVPAY': 483636.364, 'EOSB': 13300000.0, 'NET': 17802654.545, 'NETCOST': 18415663.636}
        self._validate_payslip(payslip, payslip_results)

    def test_hourly_wage_basic_payslip(self):
        self.version.sudo().write({
            'wage_type': 'hourly',
            'hourly_wage': 10,
            'wage': 0,
        })
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'BASIC': 1760.0, 'SPF_COMP': -255.2, 'SPF_EMP': -140.8, 'EOSP': 146.667, 'ANNUALPROV': 200.0, 'NET': 1619.2, 'NETCOST': 1851.467}
        self._validate_payslip(payslip, payslip_results)

    def test_hourly_wage_overtime(self):
        self.version.sudo().write({
            'wage_type': 'hourly',
            'hourly_wage': 10,
            'wage': 0,
        })
        self._create_overtime_entry(self.employee, date(2025, 1, 5), date(2025, 1, 5), 17, 21, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_work_days_daytime'))
        self._create_overtime_entry(self.employee, date(2025, 1, 6), date(2025, 1, 6), 20, 24, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_work_days_nighttime'))
        self._create_overtime_entry(self.employee, date(2025, 1, 4), date(2025, 1, 4), 8, 12, 4, self.env.ref('hr_work_entry.l10n_om_work_entry_type_overtime_rest_days'))
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()
        self._validate_worked_days(payslip, {
            'OMOTWDD': (0.5, 4, 50.0),
            'OMOTWDN': (0.5, 4, 60.0),
            'OMOTPHD': (0.5, 4, 80.0),
        }, skip_lines=True)
        payslip_results = {'BASIC': 1950.0, 'SPF_COMP': -282.75, 'SPF_EMP': -156.0, 'EOSP': 162.5, 'ANNUALPROV': 221.591, 'NET': 1794.0, 'NETCOST': 2051.341}
        self._validate_payslip(payslip, payslip_results)
