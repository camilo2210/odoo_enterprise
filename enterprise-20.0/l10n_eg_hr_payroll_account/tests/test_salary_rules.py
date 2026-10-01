# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('eg')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.eg'),
            structure=cls.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary'),
            structure_type=cls.env.ref('l10n_eg_hr_payroll.structure_type_employee_eg'),
            resource_calendar=cls.env.ref('l10n_eg_hr_payroll.resource_calendar_def_40h'),
            version_fields={
                'wage': 10000,
                'l10n_eg_social_insurance_reference': 1000,
                'l10n_eg_housing_allowance': 100,
                'l10n_eg_transportation_allowance': 110,
                'l10n_eg_other_allowances': 80,
            },
            employee_fields={
                'identification_id': 'identification12345',
            },
        )
        cls.employee.l10n_eg_eligible_for_eos = True

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SIEMP': -110.0, 'SICOMP': 187.5, 'EOSP': 833.33, 'ANNUALP': 782.93, 'GROSS': 10290.0, 'GROSSY': 122160.0, 'TAXBLEAM': 102160.0, 'TOTTB': -848.5, 'NET': 9331.5}
        self._validate_payslip(payslip, payslip_results)

    @freeze_time("2025-01-31")
    def test_end_of_service_payslip(self):
        annual_work_entry_type = self.env.ref('hr_work_entry.eg_work_entry_type_legal_leave')
        self.employee.company_id.l10n_eg_annual_work_entry_type_id = annual_work_entry_type.id
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'work_entry_type_id': annual_work_entry_type.id,
            'number_of_days': 15,
        })
        allocation.action_approve()
        self._generate_leave(self.employee, date(2025, 1, 20), date(2025, 1, 21), annual_work_entry_type, False)

        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 1, 31),
            'action_date': date(2025, 1, 31),
            'departure_description': 'foo',
        })
        departure.action_register()

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'ANNUALP': 818.52, 'ANNUALCOMP': 6080.45, 'EOSB': 65806.45, 'GROSS': 82176.91, 'GROSSY': 984802.87, 'TAXBLEAM': 964802.87, 'TOTTB': -19266.73, 'NET': 62800.18}
        self._validate_payslip(payslip, payslip_results)

    @freeze_time("2025-02-01")
    def test_end_of_service_departure_dates_payslips(self):
        self.env.user.group_ids |= self.env.ref('hr.group_hr_user')
        self.env.user.group_ids |= self.env.ref('hr_payroll.group_hr_payroll_user')
        version_start_dates = [date(2022, 2, 1), date(2021, 8, 1), date(2021, 5, 1), date(2018, 5, 1)]
        first_version = self.employee._get_first_versions().sorted('date_start')[0]
        payslip_results = [
            {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'ANNUALP': 818.52, 'ANNUALCOMP': 7015.91, 'EOSB': 15000.0, 'GROSS': 32305.91, 'GROSSY': 386350.91, 'TAXBLEAM': 366350.91, 'TOTTB': -5598.25, 'NET': 26597.66},
            {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'ANNUALP': 818.52, 'ANNUALCOMP': 7015.91, 'EOSB': 17500.0, 'GROSS': 34805.91, 'GROSSY': 416350.91, 'TAXBLEAM': 396350.91, 'TOTTB': -6160.75, 'NET': 28535.16},
            {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'ANNUALP': 818.52, 'ANNUALCOMP': 7015.91, 'EOSB': 18750.0, 'GROSS': 36055.91, 'GROSSY': 431350.91, 'TAXBLEAM': 411350.91, 'TOTTB': -6465.64, 'NET': 29480.27},
            {'BASIC': 10000.0, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'ANNUALP': 818.52, 'ANNUALCOMP': 7015.91, 'EOSB': 42500.0, 'GROSS': 59805.91, 'GROSSY': 716350.91, 'TAXBLEAM': 696350.91, 'TOTTB': -12736.48, 'NET': 46959.43},
        ]

        annual_work_entry_type = self.env.ref('hr_work_entry.generic_work_entry_type_legal_leave')
        self.employee.company_id.l10n_eg_annual_work_entry_type_id = annual_work_entry_type.id
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2022, 2, 1),
            'work_entry_type_id': annual_work_entry_type.id,
            'number_of_days': 15,
        })
        allocation.action_approve()
        self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'departure_description': 'foo',
        })
        for i in range(len(version_start_dates)):
            first_version.contract_date_start = version_start_dates[i]
            payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
            payslip.compute_sheet()
            self._validate_payslip(payslip, payslip_results[i])

    def test_payslip_with_other_input(self):
        ot_rest_days = self.env.ref('hr_work_entry.l10n_eg_work_entry_type_overtime_rest_days')
        ot_work_days = self.env.ref('hr_work_entry.l10n_eg_work_entry_type_overtime_work_days_daytime')
        (ot_rest_days | ot_work_days).sudo().write({
            'requires_allocation': False,
            'request_unit': 'hour',
        })
        self.env['hr.leave'].create({
            'name': 'Rest day',
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 1, 4),  # Saturday
            'request_date_to': date(2025, 1, 4),
            'request_hour_from': 8,
            'request_hour_to': 10,
            'number_of_hours': 2,
            'work_entry_type_id': ot_rest_days.id,
        })
        self.env['hr.leave'].create({
            'name': 'Work day',
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 1, 7),  # Monday
            'request_date_to': date(2025, 1, 7),
            'request_hour_from': 1,
            'request_hour_to': 3,
            'number_of_hours': 2,
            'work_entry_type_id': ot_work_days.id,
        })

        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 1, 31),
            'departure_description': 'foo',
        })
        departure.action_register()

        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10380.68, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'SICOMP': 187.5, 'SIEMP': -110.0, 'ANNUALP': 818.52, 'EOSB': 65806.45, 'GROSS': 76477.13, 'GROSSY': 916405.58, 'TAXBLEAM': 896405.58, 'TOTTB': -17425.12, 'NET': 58942.02}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_with_unpaid_sick_leave(self):
        unpaid_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_eg_work_entry_type_sick_leave_unpaid')
        self._generate_leave(self.employee, date(2025, 1, 15), date(2025, 1, 16), unpaid_sick_work_entry_type)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 9090.91, 'HOU': 90.91, 'TA': 100.0, 'OA': 72.73, 'EOSP': 833.33, 'SIEMP': -110.0, 'SICOMP': 187.5, 'ANNUALP': 818.52, 'GROSS': 9354.55, 'GROSSY': 110934.56, 'TAXBLEAM': 90934.56, 'TOTTB': -661.41, 'NET': 8583.14}
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_with_75_paid_sick_leave(self):
        sick_leave_75_type = self.env.ref('hr_work_entry.l10n_eg_work_entry_type_sick_leave_75')
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Sick Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'work_entry_type_id': sick_leave_75_type.id,
            'number_of_days': 2,
        })
        allocation.action_approve()
        self._generate_leave(self.employee, date(2025, 1, 15), date(2025, 1, 16), sick_leave_75_type)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 9772.73, 'HOU': 100.0, 'TA': 110.0, 'OA': 80.0, 'EOSP': 833.33, 'SIEMP': -110.0, 'SICOMP': 187.5, 'ANNUALP': 800.44, 'GROSS': 10062.73, 'GROSSY': 119432.76, 'TAXBLEAM': 99432.76, 'TOTTB': -803.05, 'NET': 9149.68}
        self._validate_payslip(payslip, payslip_results)

    def test_end_of_year_tax_adjustment(self):
        nov_payslip = self._generate_payslip(date(2024, 11, 1), date(2024, 11, 30))
        nov_payslip.action_payslip_done()
        dec_payslip = self._generate_payslip(date(2024, 12, 1), date(2024, 12, 31))
        tax_adjustment_wizard = self.env['l10n.eg.ytd.tax.adjustment.wizard'].create({
            'payslip_id': dec_payslip.id,
        })
        tax_adjustment_wizard.action_confirm_eg_adjustment()
        self._validate_payslip(dec_payslip, {'TAX_CORRECT_POS': 1697.0}, skip_lines=True)
