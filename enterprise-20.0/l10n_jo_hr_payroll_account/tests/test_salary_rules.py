# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('jo')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.jo'),
            structure=cls.env.ref('l10n_jo_hr_payroll.hr_payroll_structure_jo_employee_salary'),
            structure_type=cls.env.ref('l10n_jo_hr_payroll.structure_type_employee_jo'),
            resource_calendar=cls.env.ref('l10n_jo_hr_payroll.l10n_jo_resource_calender'),
            version_fields={
                'wage': 40000.0,
                'l10n_jo_housing_allowance': 400.0,
                'l10n_jo_transportation_allowance': 220.0,
                'l10n_jo_other_allowances': 100.0,
            }
        )

    def test_payslip_1(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 40720.0,
            'GROSSY': 476640.0,
            'TXB': -9721.666,
            'NET': 30747.159
        }
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_sick_leave_unpaid(self):
        unpaid_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_jo_work_entry_type_sick_leave_unpaid')
        self._generate_leave(self.employee, date(2025, 1, 8), date(2025, 1, 9), unpaid_sick_work_entry_type)
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'SICKLEAVE0': -2714.667,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 40720.0,
            'GROSSY': 476640.0,
            'TXB': -9721.666,
            'NET': 28032.492
        }
        self._validate_payslip(payslip, payslip_results)

    @freeze_time("2025-03-31")
    def test_payslip_end_of_service(self):
        annual_work_entry_type = self.env.ref('hr_work_entry.jo_work_entry_type_legal_leave')
        self.employee.company_id.l10n_jo_annual_work_entry_type_id = annual_work_entry_type.id
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation',
            'employee_id': self.employee.id,
            'date_from': date(2025, 1, 1),
            'work_entry_type_id': annual_work_entry_type.id,
            'number_of_days': 14,
        })
        allocation.action_approve()
        self._generate_leave(self.employee, date(2025, 1, 10), date(2025, 1, 13), annual_work_entry_type)
        self.employee.l10n_jo_is_eligible_for_eos = True

        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'departure_date': date(2025, 3, 31),
            'action_date': date(2025, 3, 31),
            'departure_description': 'foo',
        })
        departure.action_register()

        self.employee.departure_date = date(2025, 3, 31)
        self.employee.departure_reason_id = self.env.ref('hr.departure_fired')
        payslip = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 40000.0,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 40720.0,
            'GROSSY': 476640.0,
            'TXB': -9721.666,
            'EOSB': 376613.516,
            'EOSLEAVES': 4750.667,
            'EOSTXD': -90403.372,
            'NET': 321707.97,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_payslip_overtime_calculations(self):
        ot_rest_days = self.env.ref('hr_work_entry.l10n_jo_work_entry_type_rest_days_overtime')
        ot_week_days = self.env.ref('hr_work_entry.l10n_jo_work_entry_type_week_days_overtime')
        (ot_rest_days | ot_week_days).sudo().write({
            'requires_allocation': False,
            'request_unit': 'hour',
        })
        self.env['hr.leave'].create({
            'name': 'Rest Days OT',
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 1, 4),  # Saturday
            'request_date_to': date(2025, 1, 4),
            'request_hour_from': 8,
            'request_hour_to': 9,
            'number_of_hours': 1,
            'work_entry_type_id': ot_rest_days.id,
        })
        self.env['hr.leave'].create({
            'name': 'Weekdays OT',
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 1, 5),  # Sunday (working day)
            'request_date_to': date(2025, 1, 5),
            'request_hour_from': 8,
            'request_hour_to': 10,
            'number_of_hours': 2,
            'work_entry_type_id': ot_week_days.id,
        })
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip.compute_sheet()
        payslip_results = {
            'BASIC': 39545.455,
            'HOUALLOW': 400.0,
            'TRAALLOW': 220.0,
            'OTALLOW': 100.0,
            'SSC': -477.233,
            'SSE': -251.175,
            'ROVT': 340.909,
            'WOVT': 568.182,
            'EOSPROV': 3393.333,
            'ANNUALP': 1583.556,
            'GROSS': 41174.546,
            'GROSSY': 482094.552,
            'TXB': -9835.303,
            'NET': 31088.068,
        }
        self._validate_payslip(payslip, payslip_results)
