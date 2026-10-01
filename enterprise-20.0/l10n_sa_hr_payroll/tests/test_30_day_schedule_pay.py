# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from .common import TestSACommon
from odoo.tests.common import tagged


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class Test30DaySchedulePay(TestSACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("hr_work_entry.l10n_sa_work_entry_type_overtime").sudo().requires_allocation = False
        cls.saudi_employee.version_id.schedule_pay = '30_monthly'
        cls.saudi_employee.version_id.resource_calendar_id = cls.sa_full_week_calendar

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

    def test_30_day_saudi_payslip(self):
        self.saudi_employee.version_id.contract_date_end = '2026-4-27'
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
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'UNPAID': -2283.33, 'ALPPOUT': 1370.0, 'EOSP': 475.69, 'ANNUALP': 799.17, 'GROSS': 13700.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 10149.17, 'NETCOST': 14144.17}
        self._validate_payslip(payslip, payslip_results)

    def test_30_day_saudi_payslip_laid_off(self):
        # Generate 2 prior payslips to accrue EOSP provisions
        payslip_jan = self._generate_payslip(
            date(2024, 1, 1), date(2024, 1, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_jan.compute_sheet()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'EOSP': 570.83, 'ANNUALP': 799.17, 'GROSS': 13700.0, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 12432.5, 'NETCOST': 16427.5}
        self._validate_payslip(payslip_jan, payslip_results)
        payslip_jan.action_payslip_done()

        payslip_feb = self._generate_payslip(
            date(2024, 2, 1), date(2024, 2, 29),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_feb.compute_sheet()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'EOSP': 570.83, 'ANNUALP': 799.17, 'GROSS': 13700.0, 'IQAMA': 500.0, 'MEDICAL': 400.0, 'WORKPER': 300.0, 'NET': 12432.5, 'NETCOST': 16427.5}
        self._validate_payslip(payslip_feb, payslip_results)
        payslip_feb.action_payslip_done()
        self.saudi_employee.write({
            'active': False,
            'departure_reason_id': self.env.ref('l10n_sa_hr_payroll.saudi_departure_company_article_77').id,
            'departure_date': date(2024, 3, 31),
        })
        self.saudi_employee.version_id.date_end = date(2024, 3, 31)
        payslip = self._generate_payslip(
            date(2024, 3, 1), date(2024, 3, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'BASIC': 12000.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'HOUALLOW': 1000.0, 'OTALLOW': 500.0, 'TRAALLOW': 200.0, 'EOSP': 570.83, 'EOSB': 27400.0, 'EOSPC': 26258.34, 'ANNUALP': 799.17, 'ANNUALCOMP': 9590.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'GROSS': 50690.0, 'NET': 49422.5, 'NETCOST': 79675.84}
        self._validate_payslip(payslip, payslip_results)

    def test_30_day_payslip_overtime_1(self):
        self.employee.version_id.write({
            'wage': 10000.0,
            'l10n_sa_housing_allowance': 400.0,
            'l10n_sa_transportation_allowance': 200.0,
            'l10n_sa_other_allowances': 150.0,
            'l10n_sa_number_of_days': 20.0,
            'schedule_pay': '30_monthly',
            'resource_calendar_id': self.sa_full_week_calendar.id
        })
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
        payslip_results = {'BASIC': 10000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 200.0, 'OTALLOW': 150.0, 'GOSI_COMP': 0.0, 'GOSI_EMP': 0.0, 'OT': 179.17, 'EOSP': 895.83, 'ANNUALP': 597.22, 'GROSS': 10929.17, 'NET': 10929.17, 'NETCOST': 10929.17}
        self._validate_payslip(payslip, payslip_results)

    def test_30_day_payslip_overtime_2(self):
        self.employee.version_id.write({
            'wage': 10000.0,
            'l10n_sa_housing_allowance': 400.0,
            'l10n_sa_transportation_allowance': 200.0,
            'l10n_sa_other_allowances': 150.0,
            'l10n_sa_number_of_days': 20.0,
            'schedule_pay': '30_monthly',
            'resource_calendar_id': self.sa_full_week_calendar.id
        })
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
        payslip_results = {'BASIC': 10000.0, 'HOUALLOW': 400.0, 'TRAALLOW': 200.0, 'OTALLOW': 150.0, 'GOSI_COMP': 0.0, 'GOSI_EMP': 0.0, 'OT': 537.5, 'EOSP': 895.83, 'ANNUALP': 597.22, 'GROSS': 11287.5, 'NET': 11287.5, 'NETCOST': 11287.5}
        self._validate_payslip(payslip, payslip_results)

    def test_30_day_saudi_payslip_gosi_contribution(self):
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
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'GOSI_COMP': -1527.5, 'GOSI_EMP': -1267.5, 'UNPAID': -685.0, 'EOSP': 542.29, 'ANNUALP': 799.17, 'GROSS': 13700.0, 'MEDICAL': 400.0, 'IQAMA': 500.0, 'WORKPER': 300.0, 'NET': 11747.5, 'NETCOST': 15742.5}
        self._validate_payslip(payslip, payslip_results)

    def test_30_day_saudi_payslip_deferred_amount(self):
        self.env['hr.leave'].create({
            'name': 'Unpaid Leave',
            'employee_id': self.saudi_employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.sa_work_entry_type_unpaid_leave').id,
            'request_date_from': date(2026, 7, 1),
            'request_date_to': date(2026, 8, 31),
        })
        payslip_jul = self._generate_payslip(
            date(2026, 7, 1), date(2026, 7, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_jul.action_validate()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'UNPAID': -13700.0, 'AMOUNTTODEFER': -456.67}
        self._validate_payslip(payslip_jul, payslip_results, skip_lines=True)
        payslip_aug = self._generate_payslip(
            date(2026, 8, 1), date(2026, 8, 31),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_aug.action_validate()
        payslip_results = {'BASIC': 12000.0, 'HOUALLOW': 1000.0, 'TRAALLOW': 200.0, 'OTALLOW': 500.0, 'UNPAID': -13700.0, 'DEFERREDAMOUNT': 0, 'AMOUNTTODEFER': -913.34}
        self._validate_payslip(payslip_aug, payslip_results, skip_lines=True)
        payslip_sep = self._generate_payslip(
            date(2026, 9, 1), date(2026, 9, 30),
            employee_id=self.saudi_employee.id,
            version_id=self.saudi_employee.version_id.id,
            struct_id=self.env.ref('l10n_sa_hr_payroll.ksa_saudi_employee_payroll_structure').id)
        payslip_results = {'DEFERREDAMOUNT': -913.34}
        self._validate_payslip(payslip_sep, payslip_results, skip_lines=True)
