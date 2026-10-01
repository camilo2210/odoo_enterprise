# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('tr')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.tr'),
            structure=cls.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary'),
            structure_type=cls.env.ref('l10n_tr_hr_payroll.structure_type_employee_tr'),
            version_fields={
                'wage': 50000,
                'l10n_tr_is_net_to_gross': False,
                'l10n_tr_food_allowance': 100,
            },
            employee_fields={
                'l10n_tr_occupational_code': '2320.95',
                'l10n_tr_social_insurance_number': '123456789',
            },
        )
        cls.env.company.write({
            'l10n_tr_sgk_workspace_registration_no': '1234567',
            'l10n_tr_tax_reponsible_id': cls.employee.id,
            'l10n_tr_sgk_intermediary_code': '000',
            'l10n_tr_old_unit_code': '01',
            'l10n_tr_new_unit_code': '01',
        })

    def test_basic_payslip(self):
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        # The first contract for the employee was in 2016. So, it is nearly 9 years.
        # Since the employee has 20 days of leave, ALP is wage / working days * leave days / 12.
        payslip_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 42500.0, 'CURTAXABLE': 42500.0, 'TAXB': 42500.0, 'TOTTB': 6375.0, 'BTAXNET': 6375.0, 'BTNET': -3824.68, 'SEVPROV': 4166.67, 'STAX': -227.68, 'NETTAX': -4052.36, 'EXPNET': 38447.64, 'NET': 38547.64, 'FDALW': 100, 'ALP': 3623.19}
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip_second_month = self._generate_payslip(date(2024, 2, 1), date(2024, 2, 29))
        payslip_second_month_results = {'YTDGROSS': 42500.0, 'ACTD': 6375.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 85000.0, 'CURTAXABLE': 42500.0, 'TAXB': 85000.0, 'TOTTB': 12750.0, 'BTAXNET': 6375.0, 'BTNET': -3824.68, 'SEVPROV': 4166.67, 'STAX': -227.68, 'NETTAX': -4052.36, 'EXPNET': 38447.64, 'NET': 38547.64, 'FDALW': 100, 'ALP': 3968.25}
        self._validate_payslip(payslip_second_month, payslip_second_month_results)
        payslip_second_month.action_payslip_done()
        payslip_second_month.action_payslip_paid()

        payslip_third_month = self._generate_payslip(date(2024, 3, 1), date(2024, 3, 31))

        payslip_second_month.action_payslip_cancel()
        payslip_third_month.compute_sheet()
        payslip_third_month_results = {'YTDGROSS': 42500.0, 'ACTD': 6375.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 85000.0, 'CURTAXABLE': 42500.0, 'TAXB': 85000.0, 'TOTTB': 12750.0, 'BTAXNET': 6375.0, 'BTNET': -3824.68, 'SEVPROV': 4166.67, 'STAX': -227.68, 'NETTAX': -4052.36, 'EXPNET': 38447.64, 'NET': 38547.64, 'FDALW': 100, 'ALP': 3968.25}
        self._validate_payslip(payslip_third_month, payslip_third_month_results)

    def test_alp_after_one_year(self):
        self.version.contract_date_start = date(2024, 7, 1)
        payslip = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        # No ALP for < 1 year.
        payslip_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 42500.0, 'CURTAXABLE': 42500.0, 'TAXB': 42500.0, 'TOTTB': 6375.0, 'BTAXNET': 6375.0, 'BTNET': -3059.3, 'SEVPROV': 4166.67, 'STAX': -182.12, 'NETTAX': -3241.42, 'EXPNET': 39258.58, 'FDALW': 100.0, 'NET': 39358.58}
        self._validate_payslip(payslip, payslip_results)

        # Tenure started on July 1st, 2024, so August 2025 is > 1 year.
        # ALP = 50000 / 21 working days * 14 leave days / 12 = 2777.78
        payslip = self._generate_payslip(date(2025, 8, 1), date(2025, 8, 31))
        payslip_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 42500.0, 'CURTAXABLE': 42500.0, 'TAXB': 42500.0, 'TOTTB': 6375.0, 'BTAXNET': 6375.0, 'BTNET': -3059.3, 'SEVPROV': 4166.67, 'STAX': -182.12, 'NETTAX': -3241.42, 'EXPNET': 39258.58, 'FDALW': 100.0, 'ALP': 2777.78, 'NET': 39358.58}
        self._validate_payslip(payslip, payslip_results)

    def test_ntg_payslip(self):
        self.version.l10n_tr_is_net_to_gross = True
        self.version.l10n_tr_food_allowance = 0
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'GFNET': 65024.86, 'BASIC': 65024.86, 'SSIEDED': -9753.73, 'SSICDED': 15443.40, 'GROSS': 55271.13, 'CURTAXABLE': 55271.13, 'TAXB': 55271.13, 'TOTTB': 8290.67, 'BTAXNET': 8290.67, 'BTNET': -4974.97, 'SEVPROV': 4166.67, 'STAX': -296.16, 'NETTAX': -5271.13, 'EXPNET': 50000.0, 'NET': 50000.0, 'FDALW': 0, 'ALP': 3623.19}
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()
        payslip.action_payslip_paid()

        payslip_second_month = self._generate_payslip(date(2025, 2, 1), date(2025, 2, 28))
        payslip_second_month_results = {'YTDGROSS': 55271.13, 'ACTD': 8290.67, 'GFNET': 65024.86, 'BASIC': 65024.86, 'SSIEDED': -9753.73, 'SSICDED': 15443.40, 'GROSS': 110542.26, 'CURTAXABLE': 55271.13, 'TAXB': 110542.26, 'TOTTB': 16581.34, 'BTAXNET': 8290.67, 'BTNET': -4974.97, 'SEVPROV': 4166.67, 'STAX': -296.16, 'NETTAX': -5271.13, 'EXPNET': 50000.0, 'NET': 50000.0, 'FDALW': 0, 'ALP': 4166.67}
        self._validate_payslip(payslip_second_month, payslip_second_month_results)
        payslip_second_month.action_payslip_done()
        payslip_second_month.action_payslip_paid()

        payslip_third_month = self._generate_payslip(date(2025, 3, 1), date(2025, 3, 31))

        payslip_second_month.action_payslip_cancel()
        payslip_third_month.compute_sheet()
        payslip_third_month_results = {'YTDGROSS': 55271.13, 'ACTD': 8290.67, 'GFNET': 65024.86, 'BASIC': 65024.86, 'SSIEDED': -9753.73, 'SSICDED': 15443.40, 'GROSS': 110542.26, 'CURTAXABLE': 55271.13, 'TAXB': 110542.26, 'TOTTB': 16581.34, 'BTAXNET': 8290.67, 'BTNET': -4974.97, 'SEVPROV': 4166.67, 'STAX': -296.16, 'NETTAX': -5271.13, 'EXPNET': 50000.0, 'NET': 50000.0, 'FDALW': 0, 'ALP': 3968.25}
        self._validate_payslip(payslip_third_month, payslip_third_month_results)

    def test_ntg_payslip_deduction(self):
        self.version.l10n_tr_is_net_to_gross = True
        self.version.l10n_tr_food_allowance = 0
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        manual_deduction_rule_id = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_manual_deduction')
        manual_addition_rule_id = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_manual_addition')
        for code, value in {
            manual_deduction_rule_id.code: 100,
            manual_addition_rule_id.code: 295,
        }.items():
            payslip._set_input_value(code, value)
        payslip.compute_sheet()
        payslip_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'GFNET': 65024.86, 'BASIC': 65024.86, 'SSIEDED': -9753.73, 'SSICDED': 15443.40, 'GROSS': 55271.13, 'CURTAXABLE': 55271.13, 'TAXB': 55271.13, 'TOTTB': 8290.67, 'BTAXNET': 8290.67, 'BTNET': -4974.97, 'SEVPROV': 4166.67, 'STAX': -296.16, 'NETTAX': -5271.13, 'EXPNET': 50000.0, 'MANDED': 100.0, 'MANADD': 295.0, 'NET': 50195.0, 'FDALW': 0, 'ALP': 3623.19}
        self._validate_payslip(payslip, payslip_results)

    def test_severance_pay_less_than_1_year(self):
        # Employee with less than 1 year (6 months) - should get 0
        self.employee.contract_date_start = date(2025, 1, 1)
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 6, 30),
            'departure_description': 'Test departure',
        })
        departure.action_register()
        payslip_6_months = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        payslip_6_months.compute_sheet()
        payslip_6_months_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 42500.0, 'CURTAXABLE': 42500.0, 'TAXB': 42500.0, 'TOTTB': 6375.0, 'BTAXNET': 6375.0, 'BTNET': -3059.3, 'SEVPAY': 0.0, 'STAX': -182.12, 'NETTAX': -3241.42, 'EXPNET': 39258.58, 'FDALW': 100.0, 'NET': 39358.58}
        self._validate_payslip(payslip_6_months, payslip_6_months_results)

    def test_severance_pay_more_than_1_year(self):
        # Employee with more than 1 year (18 months) - should calculate properly
        self.employee.contract_date_start = date(2024, 1, 1)
        self.employee.contract_date_end = date(2025, 6, 30)
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 6, 30),
            'departure_description': 'Test departure',
        })
        departure.action_register()
        payslip_18_months = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        payslip_18_months.compute_sheet()
        # Worked duration: 1 year, 6 months = 1 + (6/12) = 1.5 years
        # Capped monthly: min(50000, 46655.43) = 46655.43
        # SEVPAY: 46655.43 * 1.5 = 69983.15
        payslip_18_months_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 42500.0, 'CURTAXABLE': 42500.0, 'TAXB': 42500.0, 'TOTTB': 6375.0, 'BTAXNET': 6375.0, 'BTNET': -3059.3, 'SEVPAY': 69983.15, 'STAX': -713.29, 'NETTAX': -3772.59, 'EXPNET': 108710.55, 'FDALW': 100.0, 'NET': 108810.55}
        self._validate_payslip(payslip_18_months, payslip_18_months_results)

    def test_severance_pay_with_unpaid_leave(self):
        # Employee with unpaid leave - should calculate properly
        self.employee.contract_date_start = date(2024, 1, 1)
        self.employee.contract_date_end = date(2025, 6, 30)
        self.env['hr.leave'].create({
            'name': 'Unpaid Leave',
            'employee_id': self.employee.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.tr_work_entry_type_unpaid_leave').id,
            'request_date_from': date(2025, 5, 5),
            'request_date_to': date(2025, 5, 9),
        })
        # Generate and validate May payslip with unpaid leave to record it in history
        may_payslip = self._generate_payslip(date(2025, 5, 1), date(2025, 5, 31))
        may_payslip.compute_sheet()
        self.employee.review_state = '1_reviewed'
        may_payslip.action_payslip_done()
        # Now depart in June and generate final payslip with severance
        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 6, 30),
            'departure_description': 'Test departure',
        })
        departure.action_register()
        payslip_with_severance = self._generate_payslip(date(2025, 6, 1), date(2025, 6, 30))
        payslip_with_severance.compute_sheet()
        # Worked duration reduced by 5 unpaid days: 1 year, 5 months, 25 days = 1 + (5/12) + (25/365) = 1.485 years
        # Capped monthly: min(50000, 46655.43) = 46655.43
        # SEVPAY: 46655.43 * 1.485 = 69290.77
        payslip_results = {'YTDGROSS': 32840.91, 'ACTD': 4926.14, 'BASIC': 50000.0, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 75340.91, 'CURTAXABLE': 42500.0, 'TAXB': 75340.91, 'TOTTB': 11301.14, 'BTAXNET': 6375.0, 'BTNET': -3059.3, 'SEVPAY': 69290.77, 'STAX': -708.04, 'NETTAX': -3767.33, 'EXPNET': 108023.44, 'FDALW': 100.0, 'NET': 108123.44}
        self._validate_payslip(payslip_with_severance, payslip_results)

    @freeze_time("2025-12-31")
    def test_annual_leave_compensation(self):
        self.employee.contract_date_start = date(2025, 2, 1)
        annual_leave_type = self.env.ref('hr_work_entry.tr_work_entry_type_legal_leave')
        self.employee.company_id.l10n_tr_annual_work_entry_type_id = annual_leave_type.id
        allocation = self.env['hr.leave.allocation'].create({
            'name': 'Annual Leave Allocation 2025',
            'work_entry_type_id': annual_leave_type.id,
            'number_of_days': 10,
            'employee_id': self.employee.id,
            'date_from': date(2025, 2, 1),
        })
        allocation.action_approve()

        departure = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 12, 31),
            'action_date': date(2025, 12, 31),
            'departure_description': 'foo',
        })
        departure.action_register()

        payslip = self._generate_payslip(date(2025, 12, 1), date(2025, 12, 31))
        payslip.compute_sheet()
        # Daily salary: (50000 + 0) / 30 = 1666.67
        # ANNUALCOMP: 1666.67 * 10 = 16666.67
        payslip_with_leave_results = {'YTDGROSS': 0.0, 'ACTD': 0.0, 'BASIC': 50000.0, 'ANNUALCOMP': 16666.67, 'SSIEDED': -7500.0, 'SSICDED': 11875.0, 'GROSS': 59166.67, 'CURTAXABLE': 42500.0, 'TAXB': 59166.67, 'TOTTB': 8875.0, 'BTAXNET': 8875.0, 'BTNET': -5559.3, 'SEVPAY': 0.0, 'STAX': -182.12, 'NETTAX': -5741.42, 'EXPNET': 53425.25, 'FDALW': 100.0, 'NET': 53525.25}
        self._validate_payslip(payslip, payslip_with_leave_results)

    def test_rd_incentive(self):
        # 1.l10n_tr_is_rd_incentive is False (Default)
        self.version.l10n_tr_is_rd_incentive = False
        payslip_off = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self._validate_payslip(payslip_off, {'STAX': -227.68, 'BTNET': -3824.68}, skip_lines=True)

        # 2. R&D Incentive Enabled (l10n_tr_is_rd_incentive = True)
        self.version.l10n_tr_is_rd_incentive = True

        # Lower than Master's (e.g. high school / default) -> 80% relief, stamp tax = 0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self._validate_payslip(payslip, {'STAX': 0.0, 'BTNET': -764.936}, skip_lines=True)

        # Master's -> 90% relief
        self.employee.certificate = 'master'
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self._validate_payslip(payslip, {'STAX': 0.0, 'BTNET': -382.468}, skip_lines=True)

        # Doctorate -> 95% relief
        self.employee.certificate = 'l10n_tr_7_doctorate'
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self._validate_payslip(payslip, {'STAX': 0.0, 'BTNET': -191.234}, skip_lines=True)

        # Above ceiling (wage > 40x gross min wage)
        self.version.wage = 1500000.0
        payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31))
        self._validate_payslip(payslip, {'STAX': -5312.241, 'BTNET': -241090.84}, skip_lines=True)

        # 2025 Minimum Gross Wage Parameter Test (26,005.50 TL)
        self.version.wage = 1300000.0
        payslip_2025 = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        self._validate_payslip(payslip_2025, {'STAX': -1971.73, 'BTNET': -80228.11}, skip_lines=True)
