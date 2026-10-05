# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('iq')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.iq'),
            structure=cls.env.ref('l10n_iq_hr_payroll.l10n_iq_regular_pay'),
            structure_type=cls.env.ref('l10n_iq_hr_payroll.l10n_iq_employee'),
            resource_calendar=cls.env.ref('l10n_iq_hr_payroll.l10n_iq_resource_calendar'),
        )

        cls.env.company.write({
            'l10n_iq_is_oil_and_gas_company': True,
        })
        cls.iraqi_employee = cls.env['hr.employee'].create({
            'name': 'Iraqi Employee',
            'company_id': cls.env.company.id,
            'wage': 250000,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
        })
        cls.iraqi_employee.version_id._set_property_input_value('OTHER_ALLOWANCE', 50000.0)

        cls.non_oil_company = cls.env['res.company'].create({
            'name': 'Non Oil Company',
            'country_id': cls.env.ref('base.iq').id,
            'currency_id': cls.env.ref('base.IQD').id,
            'l10n_iq_is_oil_and_gas_company': False,
            'resource_calendar_id': cls.env.ref('l10n_iq_hr_payroll.l10n_iq_resource_calendar').copy({'name': 'Non Oil Iraq Company Calendar'}).id,
        })
        cls.env.user.company_ids += cls.non_oil_company
        cls.non_iraqi_employee = cls.env['hr.employee'].create({
            'name': 'Non Iraqi Employee',
            'company_id': cls.non_oil_company.id,
            'wage': 200000,
            'date_version': date(2025, 4, 1),
            'contract_date_start': date(2025, 4, 1),
        })
        cls.non_iraqi_employee.create_version({
            'wage': 230000,
            'date_version': date(2026, 3, 1),
            'contract_date_start': date(2025, 4, 1),
        })

        allocations = cls.env['hr.leave.allocation'].create([{
            'name': 'Iq Legal Leave Allocation',
            'employee_id': cls.iraqi_employee.id,
            'accrual_plan_id': cls.env.ref('l10n_iq_hr_payroll.l10n_iq_hr_accrual_plan_paid_time_off').id,
            'number_of_days': 23,
            'date_from': date(2020, 1, 1),
            'work_entry_type_id': cls.env.ref('hr_work_entry.iq_work_entry_type_legal_leave').id,
        }, {
            'name': 'Non Iq Legal Leave Allocation',
            'employee_id': cls.non_iraqi_employee.id,
            'accrual_plan_id': cls.env.ref('l10n_iq_hr_payroll.l10n_iq_hr_accrual_plan_paid_time_off').id,
            'number_of_days': 21,
            'date_from': date(2025, 4, 1),
            'work_entry_type_id': cls.env.ref('hr_work_entry.iq_work_entry_type_legal_leave').id,
        }])
        allocations.action_approve()

        cls.env['hr.employee.departure'].create([{
            'employee_id': cls.iraqi_employee.id,
            'dismissal_date': date(2026, 4, 30),
            'departure_reason_id': cls.env.ref('l10n_iq_hr_payroll.iq_departure_misconduct').id,
        }, {
            'employee_id': cls.non_iraqi_employee.id,
            'dismissal_date': date(2026, 4, 30),
            'departure_reason_id': cls.env.ref('l10n_iq_hr_payroll.iq_departure_contract_terminated').id,
        }])

    def test_iraqi_payslip(self):
        self.env['hr.leave'].create([{
            'name': 'Unpaid Leave',
            'employee_id': self.iraqi_employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.iq_work_entry_type_unpaid_leave').id,
            'request_date_from': date(2025, 1, 6),
            'request_date_to': date(2025, 1, 7),
        }, {
            'name': 'paid Leave',
            'employee_id': self.iraqi_employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.iq_work_entry_type_legal_leave').id,
            'request_date_from': date(2025, 4, 6),
            'request_date_to': date(2025, 4, 7),
        }])

        version = self.iraqi_employee._get_version(date=date(2025, 4, 1))
        jan_payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31), version_id=version.id, employee_id=self.iraqi_employee.id)
        payslip_results = {'BASIC': 227272.727, 'OTHER_ALLOWANCE': 45454.545, 'GROSS': 272727.272, 'SSPC_EMPLOYEE': -13636.364, 'SSPC_EMPLOYER': -68181.818, 'EOSP': 10416.667, 'ANNUAL_LEAVE_PROVISION': 19886.364, 'NET': 259090.909, 'NETCOST': 340909.091}
        self._validate_payslip(jan_payslip, payslip_results)
        payslip = self._generate_payslip(date(2025, 4, 1), date(2025, 4, 30), version_id=version.id, employee_id=self.iraqi_employee.id)
        payslip_results = {'BASIC': 250000.0, 'OTHER_ALLOWANCE': 50000.0, 'GROSS': 300000.0, 'SSPC_EMPLOYEE': -15000.0, 'SSPC_EMPLOYER': -75000.0, 'EOSP': 10416.667, 'ANNUAL_LEAVE_PROVISION': 19886.364, 'ANNUAL_LEAVE_PPAYOUT': 22727.273, 'NET': 285000.0, 'NETCOST': 375000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_iraqi_departure_payslip(self):
        version = self.iraqi_employee._get_version(date=date(2026, 4, 1))
        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), version_id=version.id, employee_id=self.iraqi_employee.id)
        payslip_results = {'BASIC': 250000.0, 'OTHER_ALLOWANCE': 50000.0, 'GROSS': 300000.0, 'SSPC_EMPLOYEE': -15000.0, 'SSPC_EMPLOYER': -75000.0, 'ANNUAL_LEAVE_PROVISION': 19886.364, 'RLC': 261363.636, 'NET': 546363.636, 'NETCOST': 636363.636}
        self._validate_payslip(payslip, payslip_results)

    def test_iraqi_prorated_contribution_payslip(self):
        version = self.iraqi_employee._get_version(date=date(2025, 4, 1))
        version.contract_date_end = date(2025, 4, 15)
        jan_payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31), version_id=version.id, employee_id=self.iraqi_employee.id)
        payslip_results = {'BASIC': 250000.0, 'OTHER_ALLOWANCE': 50000.0, 'GROSS': 300000.0, 'SSPC_EMPLOYEE': -15000.0, 'SSPC_EMPLOYER': -75000.0, 'EOSP': 10416.667, 'ANNUAL_LEAVE_PROVISION': 19886.364, 'NET': 285000.0, 'NETCOST': 375000.0}
        self._validate_payslip(jan_payslip, payslip_results)
        payslip = self._generate_payslip(date(2025, 4, 1), date(2025, 4, 30), version_id=version.id, employee_id=self.iraqi_employee.id)
        payslip_results = {'BASIC': 125000.0, 'OTHER_ALLOWANCE': 25000.0, 'GROSS': 150000.0, 'SSPC_EMPLOYEE': -7500.0, 'SSPC_EMPLOYER': -37500.0, 'EOSP': 10416.667, 'ANNUAL_LEAVE_PROVISION': 19886.364, 'NET': 142500.0, 'NETCOST': 187500.0}
        self._validate_payslip(payslip, payslip_results)

    def test_non_iraqi_payslip(self):
        self.env['hr.leave'].create({
            'name': 'paid Leave',
            'employee_id': self.non_iraqi_employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.iq_work_entry_type_legal_leave').id,
            'request_date_from': date(2025, 4, 6),
            'request_date_to': date(2025, 4, 7),
        })

        version = self.non_iraqi_employee._get_version(date=date(2025, 4, 1))
        payslip = self._generate_payslip(date(2025, 4, 1), date(2025, 4, 30), version_id=version.id, employee_id=self.non_iraqi_employee.id)
        payslip_results = {'BASIC': 200000.0, 'GROSS': 200000.0, 'SSPC_EMPLOYEE': -10000.0, 'SSPC_EMPLOYER': -40000.0, 'EOSP': 8333.333, 'ANNUAL_LEAVE_PROVISION': 15909.091, 'ANNUAL_LEAVE_PPAYOUT': 18181.818, 'NET': 190000.0, 'NETCOST': 240000.0}
        self._validate_payslip(payslip, payslip_results)

    def test_non_iraqi_departure_payslip(self):
        version = self.non_iraqi_employee._get_version(date=date(2026, 4, 1))
        payslip = self._generate_payslip(date(2026, 4, 1), date(2026, 4, 30), version_id=version.id, employee_id=self.non_iraqi_employee.id)
        payslip_results = {'BASIC': 230000.0, 'GROSS': 230000.0, 'SSPC_EMPLOYEE': -11500.0, 'SSPC_EMPLOYER': -46000.0, 'EOSB': 115000.0, 'ANNUAL_LEAVE_PROVISION': 18295.455, 'RLC': 219545.455, 'NET': 553045.455, 'NETCOST': 610545.455}
        self._validate_payslip(payslip, payslip_results)
