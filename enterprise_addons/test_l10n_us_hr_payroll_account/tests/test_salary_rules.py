# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'us_payslips_validation')
class TestPayslipValidation(TestPayslipValidationCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('us')
    def setUpClass(cls):
        super().setUpClass()
        cls.resource_calendar = cls.env['resource.calendar'].create({
            'name': 'US Calendar',
            'company_id': cls.env.company.id,
            'full_time_required_hours': 40,
        })
        cls.env.user.group_ids |= cls.env.ref("hr_payroll.group_hr_payroll_user")

        cls.work_address = cls.env['res.partner'].create([{
            'name': "US Office",
            'company_id': cls.env.company.id,
            'state_id': cls.env.ref('base.state_us_5').id,
        }])

        cls._setup_common(
            country=cls.env.ref('base.us'),
            structure=cls.env.ref('l10n_us_hr_payroll.hr_payroll_structure_us_employee_salary'),
            structure_type=cls.env.ref('l10n_us_hr_payroll.structure_type_employee_us'),
            tz='America/Los_Angeles',
            version_fields={
                'date_start': datetime.date(2018, 12, 31),
                'wage': 14000.0,
            },
            employee_fields={
                'address_id': cls.work_address.id,
                'l10n_us_state_filing_status': 'ca_status_1',
            },
            resource_calendar=cls.resource_calendar
        )

        cls.env.ref('l10n_us_hr_payroll.rule_parameter_ca_sui_rate_2023').sudo().parameter_value = "1.7"

    def test_001_semi_monthly(self):
        # A salaried employee with semi-monthly payment.
        # Benefits: No healthcare but pre-tax retirement contributions
        self.version.write({
            'wage': 4791.69,
            'l10n_us_pre_retirement_amount': 27.0,
            'l10n_us_pre_retirement_type': 'percent',
            'schedule_pay': 'semi-monthly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))

        self.assertEqual(len(payslip.worked_days_line_ids), 1)
        self.assertEqual(len(payslip.input_line_ids), 0)

        self._validate_worked_days(payslip, {'002.00': (10.0, 80.0, 4791.69)})

        payslip_results = {'BASIC': 4791.69, 'GROSS': 4791.69, '401K': -1293.76, 'TAXABLE': 3497.93, 'FIT': -447.07, 'SST': -297.08, 'MEDICARE': -69.48, 'MEDICAREADD': 0.0, 'CAINCOMETAX': -186.82, 'CASDITAX': -43.13, 'COMPANYSOCIAL': 297.08, 'COMPANYMEDICARE': 69.48, 'COMPANYFUTA': 287.5, 'COMPANYSUI': 81.46, 'COMPANYCAETT': 4.79, 'NET': 2454.36}
        self._validate_payslip(payslip, payslip_results)

    def test_002_semi_monthly_commission(self):
        # A Salaried employee plus commissions with semi-monthly payment
        # Benefits: Healthcare contributions, post-tax retirement contributions
        self.version.write({
            'wage': 2398.68,
            'l10n_us_health_benefits_medical': 42.87,
            'l10n_us_health_benefits_dental': 3.69,
            'l10n_us_health_benefits_vision': 0.49,
            'l10n_us_health_benefits_fsa': 22.73,
            'l10n_us_post_roth_401k_amount': 8,
            'schedule_pay': 'semi-monthly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip._set_input_value('COMMISSION', 3365.60)
        payslip.compute_sheet()

        self.assertEqual(len(payslip.worked_days_line_ids), 1)

        self._validate_worked_days(payslip, {'002.00': (10.0, 80.0, 2398.68)})

        payslip_results = {'BASIC': 2398.68, 'COMMISSION': 3365.6, 'GROSS': 5764.28, 'DENTAL': -3.69, 'MEDICAL': -42.87, 'VISION': -0.49, 'MEDICALFSA': -22.73, 'TAXABLE': 5694.5, 'FIT': -953.18, 'MEDICARE': -82.57, 'MEDICAREADD': 0, 'SST': -353.06, 'CAINCOMETAX': -411.53, 'CASDITAX': -51.25, 'ROTH401K': -461.14, 'COMPANYFUTA': 341.67, 'COMPANYMEDICARE': 82.57, 'COMPANYSOCIAL': 353.06, 'COMPANYSUI': 96.81, 'COMPANYCAETT': 5.69, 'NET': 3381.77}
        self._validate_payslip(payslip, payslip_results)

    def test_004_tax_status_married_jointly_old_w4(self):
        self.version.write({
            'wage': 4791.69,
            'l10n_us_pre_retirement_amount': 27.0,
            'l10n_us_pre_retirement_type': 'percent',
            'schedule_pay': 'monthly',
        })

        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_step_2': True,
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_2',
        })
        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 4791.69, 'GROSS': 4791.69, '401K': -1293.76, 'TAXABLE': 3497.93, 'FIT': -192.09, 'SST': -297.08, 'MEDICARE': -69.48, 'MEDICAREADD': 0, 'CAINCOMETAX': -36.05, 'CASDITAX': -43.13, 'COMPANYSOCIAL': 297.08, 'COMPANYMEDICARE': 69.48, 'COMPANYFUTA': 287.5, 'COMPANYSUI': 81.46, 'COMPANYCAETT': 4.79, 'NET': 2860.11}
        self._validate_payslip(payslip, payslip_results)

    def test_005_tax_status_married_jointly_new_w4(self):
        self.version.write({
            'wage': 4791.69,
            'schedule_pay': 'monthly',
        })

        self.employee.write({
            'l10n_us_w4_step_2': True,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_2',
        })
        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 4791.69, 'GROSS': 4791.69, 'TAXABLE': 4791.69, 'FIT': -418.17, 'SST': -297.08, 'MEDICARE': -69.48, 'MEDICAREADD': 0, 'CAINCOMETAX': -85.39, 'CASDITAX': -43.13, 'COMPANYSOCIAL': 297.08, 'COMPANYMEDICARE': 69.48, 'COMPANYFUTA': 287.5, 'COMPANYSUI': 81.46, 'COMPANYCAETT': 4.79, 'NET': 3878.44}
        self._validate_payslip(payslip, payslip_results)

    def test_006_ca_state_single_no_allowance(self):
        self.version.write({
            'wage': 3416.68,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 256.86,
            'l10n_us_pre_retirement_type': 'fixed',
            'l10n_us_health_benefits_medical': 62.01,
            'l10n_us_health_benefits_dental': 2.48,
            'l10n_us_health_benefits_vision': 0.49,
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip._set_input_value('COMMISSION', 864.29)
        payslip.compute_sheet()

        payslip_results = {'BASIC': 3416.68, 'COMMISSION': 864.29, 'GROSS': 4280.97, '401K': -256.86, 'DENTAL': -2.48, 'MEDICAL': -62.01, 'VISION': -0.49, 'TAXABLE': 3959.13, 'FIT': -548.53, 'MEDICARE': -61.13, 'MEDICAREADD': 0, 'SST': -261.39, 'CAINCOMETAX': -234.0, 'CASDITAX': -37.94, 'COMPANYFUTA': 252.96, 'COMPANYMEDICARE': 61.13, 'COMPANYSOCIAL': 261.39, 'COMPANYSUI': 71.67, 'COMPANYCAETT': 4.22, 'NET': 2816.14}
        self._validate_payslip(payslip, payslip_results)

    def test_007_ca_state_post_retirement(self):
        self.version.write({
            'wage': 2398.68,
            'schedule_pay': 'semi-monthly',
            'l10n_us_health_benefits_medical': 42.87,
            'l10n_us_health_benefits_dental': 3.69,
            'l10n_us_health_benefits_vision': 0.49,
            'l10n_us_health_benefits_fsa': 22.73,
            'l10n_us_post_roth_401k_amount': 461.14,
            'l10n_us_post_roth_401k_type': 'fixed',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip._set_input_value('COMMISSION', 3365.60)
        payslip.compute_sheet()

        payslip_results = {'BASIC': 2398.68, 'COMMISSION': 3365.6, 'GROSS': 5764.28, 'DENTAL': -3.69, 'MEDICAL': -42.87, 'VISION': -0.49, 'MEDICALFSA': -22.73, 'TAXABLE': 5694.5, 'FIT': -953.18, 'MEDICARE': -82.57, 'MEDICAREADD': 0, 'SST': -353.06, 'CAINCOMETAX': -411.53, 'CASDITAX': -51.25, 'ROTH401K': -461.14, 'COMPANYFUTA': 341.67, 'COMPANYMEDICARE': 82.57, 'COMPANYSOCIAL': 353.06, 'COMPANYSUI': 96.81, 'COMPANYCAETT': 5.69, 'NET': 3381.77}
        self._validate_payslip(payslip, payslip_results)

    def test_008_benefits_matching(self):
        self.version.write({
            'wage': 4791.69,
            'l10n_us_pre_retirement_amount': 27.0,
            'l10n_us_pre_retirement_type': 'percent',
            'l10n_us_pre_retirement_matching_amount': 50.0,
            'l10n_us_pre_retirement_matching_type': 'percent',
            'schedule_pay': 'semi-monthly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))

        self.assertEqual(len(payslip.worked_days_line_ids), 1)
        self.assertEqual(len(payslip.input_line_ids), 0)

        self._validate_worked_days(payslip, {'002.00': (10.0, 80.0, 4791.69)})

        payslip_results = {'BASIC': 4791.69, 'GROSS': 4791.69, '401K': -1293.76, '401KMATCHING': 646.88, 'TAXABLE': 3497.93, 'FIT': -447.07, 'SST': -297.08, 'MEDICARE': -69.48, 'MEDICAREADD': 0, 'CAINCOMETAX': -186.82, 'CASDITAX': -43.13, 'COMPANYSOCIAL': 297.08, 'COMPANYMEDICARE': 69.48, 'COMPANYFUTA': 287.5, 'COMPANYSUI': 81.46, 'COMPANYCAETT': 4.79, 'NET': 2454.36}
        self._validate_payslip(payslip, payslip_results)

        # ================================================
        # Verify Retirement Matching for Hourly Employees
        # ================================================
        self.employee.wage_type = 'hourly'
        self.version.write({
            'wage': 0.0,
            'hourly_wage': 25.0,
            'schedule_pay': 'monthly',
            'l10n_us_pre_retirement_amount': 3.0,
            'l10n_us_pre_retirement_type': 'percent',
            'l10n_us_pre_retirement_matching_amount': 100.0,
            'l10n_us_pre_retirement_matching_type': 'percent',
            'l10n_us_pre_retirement_matching_yearly_cap': 3.0,
        })

        payslip_retirement = self._generate_payslip(datetime.date(2023, 2, 1), datetime.date(2023, 2, 28))

        line_401k = payslip_retirement.line_ids.filtered(lambda l: l.code == '401K')
        line_matching = payslip_retirement.line_ids.filtered(lambda l: l.code == '401KMATCHING')

        # 3% of GROSS ($4000) = $120
        self.assertTrue(line_401k, "401K deduction line should be generated")
        self.assertAlmostEqual(line_401k.total, -120.00, places=2, msg="401K deduction should be 3% of GROSS")

        # Employer Match = Min(Contribution ($120), Cap (3% of $4000 GROSS = $120)) = $120
        self.assertTrue(line_matching, "401K Matching line should be generated")
        self.assertAlmostEqual(line_matching.total, 120.00, places=2, msg="401K Matching should scale dynamically with GROSS")

    def test_009_semi_monthly_cap_1_month(self):
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': '30000',
            'l10n_us_pre_retirement_amount': 4500.0,
            'l10n_us_pre_retirement_type': 'fixed',
            'l10n_us_pre_retirement_matching_amount': 450,
            'l10n_us_pre_retirement_matching_type': 'fixed',
            'l10n_us_health_benefits_medical': 10.0,
            'l10n_us_health_benefits_dental': 10.0,
            'l10n_us_health_benefits_vision': 10.0,
            'l10n_us_health_benefits_fsa': 10.0,
            'l10n_us_health_benefits_fsadc': 10.0,
            'l10n_us_health_benefits_hsa': 10.0,
            'l10n_us_commuter_benefits': 10.0,
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 30000.0, 'GROSS': 30000.0, '401K': -4500.0, '401KMATCHING': 450.0, 'MEDICAL': -10.0, 'DENTAL': -10.0, 'VISION': -10.0, 'MEDICALFSA': -10.0, 'MEDICALFSADC': -10.0, 'MEDICALHSA': -10.0, 'COMMUTER': -10.0, 'TAXABLE': 25430.0, 'FIT': -7542.75, 'SST': -1855.66, 'MEDICARE': -433.99, 'MEDICAREADD': 0, 'CAINCOMETAX': -2644.93, 'CASDITAX': -269.46, 'COMPANYSOCIAL': 1855.66, 'COMPANYMEDICARE': 433.99, 'COMPANYFUTA': 420.0, 'COMPANYSUI': 119.0, 'COMPANYCAETT': 7.0, 'NET': 12683.22}
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()

        payslip = self._generate_payslip(datetime.date(2023, 1, 16), datetime.date(2023, 1, 31))
        payslip_results = {'BASIC': 30000.0, 'GROSS': 30000.0, '401K': -4500.0, '401KMATCHING': 450.0, 'MEDICAL': -10.0, 'DENTAL': -10.0, 'VISION': -10.0, 'MEDICALFSA': -10.0, 'MEDICALFSADC': -10.0, 'MEDICALHSA': -10.0, 'COMMUTER': -10.0, 'TAXABLE': 25430.0, 'FIT': -7542.75, 'SST': -1855.66, 'MEDICARE': -433.99, 'MEDICAREADD': 0, 'CAINCOMETAX': -2644.93, 'CASDITAX': -269.46, 'COMPANYSOCIAL': 1855.66, 'COMPANYMEDICARE': 433.99, 'COMPANYFUTA': 0, 'COMPANYSUI': 0, 'COMPANYCAETT': 0, 'NET': 12683.22}
        self._validate_payslip(payslip, payslip_results)

    def test_010_semi_monthly_cap_6_months(self):
        self.env.ref('l10n_us_hr_payroll.rule_parameter_ca_sui_rate_2023').sudo().parameter_value = "6"

        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': '30000',
            'l10n_us_pre_retirement_amount': 4500.0,
            'l10n_us_pre_retirement_type': 'fixed',
            'l10n_us_pre_retirement_matching_amount': 450,
            'l10n_us_pre_retirement_matching_type': 'fixed',
            'l10n_us_health_benefits_medical': 10.0,
            'l10n_us_health_benefits_dental': 10.0,
            'l10n_us_health_benefits_vision': 10.0,
            'l10n_us_health_benefits_fsa': 10.0,
            'l10n_us_health_benefits_fsadc': 10.0,
            'l10n_us_health_benefits_hsa': 10.0,
            'l10n_us_commuter_benefits': 10.0,
            'l10n_us_post_roth_401k_amount': 4500.0,
            'l10n_us_post_roth_401k_type': 'fixed',
        })

        all_payslips = self.env['hr.payslip']
        for month in range(1, 7):
            # First Payslip
            date_from = datetime.date(2023, month, 1)
            date_to = datetime.date(2023, month, 15)
            payslip = self._generate_payslip(date_from, date_to)
            all_payslips += payslip
            payslip.action_payslip_done()
            # Second Payslip
            date_from = datetime.date(2023, month, 16)
            date_to = datetime.date(2023, month, 1) + relativedelta(day=31)
            payslip = self._generate_payslip(date_from, date_to)
            all_payslips += payslip
            payslip.action_payslip_done()

        line_sums = {
            '401K': -22500,
            'COMPANYCAETT': 7,
            'COMPANYSUI': 420,
            'COMPANYFUTA': 420,
            'COMPANYSOCIAL': 9932.4,
            'ROTH401K': -22500,
        }
        line_values = all_payslips._get_line_values(line_sums.keys(), compute_sum=True)
        for code, total in line_sums.items():
            self.assertAlmostEqual(line_values[code]['sum']['total'], total)

    def test_011_additional_medicare(self):
        self.version.write({
            'schedule_pay': 'semi-annually',
            'wage': 150000,
            'l10n_us_pre_retirement_amount': 4500.0,
            'l10n_us_pre_retirement_type': 'fixed',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 6, 30))
        payslip_results = {'BASIC': 150000.0, 'GROSS': 150000.0, '401K': -4500.0, 'TAXABLE': 145500.0, 'FIT': -34448.5, 'SST': -9300.0, 'MEDICARE': -2175.0, 'MEDICAREADD': 0, 'CAINCOMETAX': -12832.93, 'CASDITAX': -1350.0, 'COMPANYSOCIAL': 9300.0, 'COMPANYMEDICARE': 2175.0, 'COMPANYFUTA': 420.0, 'COMPANYSUI': 119.0, 'COMPANYCAETT': 7.0, 'NET': 85393.57}
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()
        additional_line = payslip.line_ids.filtered(lambda l: l.code == "MEDICAREADD")
        self.assertEqual(additional_line.rate, -0.9)
        self.assertEqual(additional_line.amount, 0)

        payslip = self._generate_payslip(datetime.date(2023, 7, 1), datetime.date(2023, 12, 31))
        payslip_results = {'BASIC': 150000.0, 'GROSS': 150000.0, '401K': -4500.0, 'TAXABLE': 145500.0, 'FIT': -34448.5, 'SST': -632.4, 'MEDICARE': -2175.0, 'MEDICAREADD': -900.0, 'CAINCOMETAX': -12832.93, 'CASDITAX': -1350.0, 'COMPANYSOCIAL': 632.4, 'COMPANYMEDICARE': 2175.0, 'COMPANYFUTA': 0, 'COMPANYSUI': 0, 'COMPANYCAETT': 0, 'NET': 93161.17}
        self._validate_payslip(payslip, payslip_results)
        payslip.action_payslip_done()
        additional_line = payslip.line_ids.filtered(lambda l: l.code == "MEDICAREADD")
        self.assertEqual(additional_line.rate, -0.9)
        self.assertEqual(additional_line.amount, 100000.0)

    def test_012_benefits_matching_partial_cap(self):
        self.version.write({
            'schedule_pay': 'semi-monthly',
            'wage': '30000',
            'l10n_us_pre_retirement_amount': 4500.0,
            'l10n_us_pre_retirement_type': 'fixed',
            'l10n_us_pre_retirement_matching_amount': 50,
            'l10n_us_pre_retirement_matching_type': 'percent',
            'l10n_us_pre_retirement_matching_yearly_cap': 0.06,
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 30000.0, 'GROSS': 30000.0, '401K': -4500.0, '401KMATCHING': 900.0, 'TAXABLE': 25500.0, 'FIT': -7568.65, 'SST': -1860.0, 'MEDICARE': -435.0, 'MEDICAREADD': 0, 'CAINCOMETAX': -2652.39, 'CASDITAX': -270.0, 'COMPANYSOCIAL': 1860.0, 'COMPANYMEDICARE': 435.0, 'COMPANYFUTA': 420.0, 'COMPANYSUI': 119.0, 'COMPANYCAETT': 7.0, 'NET': 12713.96}
        self._validate_payslip(payslip, payslip_results)

    def test_013_state_tax_old_w4_use_case_1(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -463.29, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -289.33, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3319.88}
        self._validate_payslip(payslip, payslip_results)

    def test_013_state_tax_old_w4_use_case_2(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_w4_withholding_deduction_allowances': 1,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -426.17, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -278.61, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3367.72}
        self._validate_payslip(payslip, payslip_results)

    def test_014_state_tax_old_w4_use_case_3(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_w4_withholding_deduction_allowances': 2,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -404.67, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -268.01, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3399.83}
        self._validate_payslip(payslip, payslip_results)

    def test_015_state_tax_old_w4_use_case_4(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'separately',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -752.5, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -160.21, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3159.79}
        self._validate_payslip(payslip, payslip_results)

    def test_016_state_tax_old_w4_use_case_5(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_w4_withholding_deduction_allowances': 1,
            'l10n_us_filing_status': 'separately',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -709.5, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -151.02, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3211.98}
        self._validate_payslip(payslip, payslip_results)

    def test_017_state_tax_old_w4_use_case_6(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_w4_withholding_deduction_allowances': 2,
            'l10n_us_filing_status': 'separately',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -667.52, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -127.58, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3277.4}
        self._validate_payslip(payslip, payslip_results)

    def test_018_state_tax_old_w4_use_case_7(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'single',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -752.5, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -289.33, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3030.67}
        self._validate_payslip(payslip, payslip_results)

    def test_018_state_tax_old_w4_use_case_8(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_w4_withholding_deduction_allowances': 1,
            'l10n_us_filing_status': 'single',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -709.5, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -278.61, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3084.39}
        self._validate_payslip(payslip, payslip_results)

    def test_018_state_tax_old_w4_use_case_9(self):
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10,
            'l10n_us_pre_retirement_type': 'percent',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_w4_withholding_deduction_allowances': 2,
            'l10n_us_filing_status': 'single',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, '401K': -500.0, 'TAXABLE': 4500.0, 'FIT': -667.52, 'SST': -310.0, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -268.01, 'CASDITAX': -45.0, 'COMPANYSOCIAL': 310.0, 'COMPANYMEDICARE': 72.5, 'COMPANYFUTA': 300.0, 'COMPANYSUI': 85.0, 'COMPANYCAETT': 5.0, 'NET': 3136.97}
        self._validate_payslip(payslip, payslip_results)

    # https://edd.ca.gov/siteassets/files/pdf_pub_ctr/23methb.pdf
    def test_050_state_tax_example_a(self):
        self.version.write({
            'wage': 210,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'single',
            'l10n_us_state_filing_status': 'ca_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 210.0, 'GROSS': 210.0, 'TAXABLE': 210.0, 'FIT': -2.63, 'SST': -13.02, 'MEDICARE': -3.05, 'MEDICAREADD': 0, 'CAINCOMETAX': 0, 'CASDITAX': -1.89, 'COMPANYSOCIAL': 13.02, 'COMPANYMEDICARE': 3.05, 'COMPANYFUTA': 12.6, 'COMPANYSUI': 3.57, 'COMPANYCAETT': 0.21, 'NET': 189.41}
        self._validate_payslip(payslip, payslip_results)

    def test_051_state_tax_example_b(self):
        self.version.write({
            'wage': 1600,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_w4_withholding_deduction_allowances': 1,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 1600.0, 'GROSS': 1600.0, 'TAXABLE': 1600.0, 'FIT': -70.0, 'SST': -99.2, 'MEDICARE': -23.2, 'MEDICAREADD': 0, 'CAINCOMETAX': -5.18, 'CASDITAX': -14.4, 'COMPANYSOCIAL': 99.2, 'COMPANYMEDICARE': 23.2, 'COMPANYFUTA': 96.0, 'COMPANYSUI': 27.2, 'COMPANYCAETT': 1.6, 'NET': 1388.02}
        self._validate_payslip(payslip, payslip_results)

    def test_052_state_tax_example_c(self):
        self.version.write({
            'wage': 5100,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 5,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 5100.0, 'GROSS': 5100.0, 'TAXABLE': 5100.0, 'FIT': -212.33, 'SST': -316.2, 'MEDICARE': -73.95, 'MEDICAREADD': 0, 'CAINCOMETAX': -15.73, 'CASDITAX': -45.9, 'COMPANYSOCIAL': 316.2, 'COMPANYMEDICARE': 73.95, 'COMPANYFUTA': 306.0, 'COMPANYSUI': 86.7, 'COMPANYCAETT': 5.1, 'NET': 4435.88}
        self._validate_payslip(payslip, payslip_results)

    def test_053_state_tax_example_d(self):
        self.version.write({
            'wage': 800,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'head',
            'l10n_us_state_filing_status': 'ca_status_4',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 800.0, 'GROSS': 800.0, 'TAXABLE': 800.0, 'FIT': -49.88, 'SST': -49.6, 'MEDICARE': -11.6, 'MEDICAREADD': 0, 'CAINCOMETAX': -0.04, 'CASDITAX': -7.2, 'COMPANYSOCIAL': 49.6, 'COMPANYMEDICARE': 11.6, 'COMPANYFUTA': 48.0, 'COMPANYSUI': 13.6, 'COMPANYCAETT': 0.8, 'NET': 681.67}
        self._validate_payslip(payslip, payslip_results)

    def test_054_state_tax_example_e(self):
        self.version.write({
            'wage': 2100,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 4,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 2100.0, 'GROSS': 2100.0, 'TAXABLE': 2100.0, 'FIT': -76.67, 'SST': -130.2, 'MEDICARE': -30.45, 'MEDICAREADD': 0, 'CAINCOMETAX': -1.72, 'CASDITAX': -18.9, 'COMPANYSOCIAL': 130.2, 'COMPANYMEDICARE': 30.45, 'COMPANYFUTA': 126.0, 'COMPANYSUI': 35.7, 'COMPANYCAETT': 2.1, 'NET': 1842.07}
        self._validate_payslip(payslip, payslip_results)

    def test_055_state_tax_example_f(self):
        self.version.write({
            'wage': 57000,
            'schedule_pay': 'annually',
        })
        self.employee.write({
            'l10n_us_old_w4': True,
            'l10n_us_w4_allowances_count': 4,
            'l10n_us_w4_withholding_deduction_allowances': 0,
            'l10n_us_filing_status': 'jointly',
            'l10n_us_state_filing_status': 'ca_status_2',
        })

        payslip = self._generate_payslip(datetime.date(2023, 1, 1), datetime.date(2023, 1, 15))
        payslip_results = {'BASIC': 57000.0, 'GROSS': 57000.0, 'TAXABLE': 57000.0, 'FIT': -2560.0, 'SST': -3534.0, 'MEDICARE': -826.5, 'MEDICAREADD': 0, 'CAINCOMETAX': -186.94, 'CASDITAX': -513.0, 'COMPANYSOCIAL': 3534.0, 'COMPANYMEDICARE': 826.5, 'COMPANYFUTA': 420.0, 'COMPANYSUI': 119.0, 'COMPANYCAETT': 7.0, 'NET': 49379.56}
        self._validate_payslip(payslip, payslip_results)

    def test_056_tips(self):
        self.version.write({
            'wage': 3416.68,
            'schedule_pay': 'semi-monthly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip._set_input_values({
            'TIPS': 500,
            'ALLOCATEDTIPS': 300,
        })
        payslip.compute_sheet()

        payslip_results = {'BASIC': 3416.68, 'TIPS': 500.0, 'GROSS': 3916.68, 'TAXABLE': 3916.68, 'FIT': -539.19, 'MEDICARE': -56.79, 'MEDICAREADD': 0, 'SST': -242.83, 'CAINCOMETAX': -229.65, 'CASDITAX': -35.25, 'COMPANYFUTA': 235.0, 'COMPANYMEDICARE': 56.79, 'COMPANYSOCIAL': 242.83, 'COMPANYSUI': 66.58, 'COMPANYCAETT': 3.92, 'ALLOCATEDTIPS': 300.0, 'NET': 3112.96}
        self._validate_payslip(payslip, payslip_results)

    def test_057_ny_state_tax_single_example_1(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 7))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 400.0, 'GROSS': 400.0, 'TAXABLE': 400.0, 'FIT': -13.37, 'MEDICARE': -5.8, 'MEDICAREADD': 0, 'SST': -24.8, 'NYINCOMETAX': -8.2, 'NYSDITAX': -0.6, 'NYPFLTAX': -1.82, 'COMPANYFUTA': 24.0, 'COMPANYMEDICARE': 5.8, 'COMPANYSOCIAL': 24.8, 'COMPANYSUI': 12.52, 'COMPANYNYREEMPLOYMENT': 0.3, 'NET': 345.41}
        self._validate_payslip(payslip, payslip_results)

    def test_058_ny_state_tax_single_example_2(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, 'TAXABLE': 5000.0, 'FIT': -786.5, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'SST': -310.0, 'NYINCOMETAX': -263.19, 'NYSDITAX': -1.3, 'NYPFLTAX': -22.75, 'COMPANYFUTA': 300.0, 'COMPANYMEDICARE': 72.5, 'COMPANYSOCIAL': 310.0, 'COMPANYSUI': 156.5, 'COMPANYNYREEMPLOYMENT': 3.75, 'NET': 3543.76}
        self._validate_payslip(payslip, payslip_results)

    def test_059_ny_state_tax_single_example_3(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 50000,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 30))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 50000.0, 'GROSS': 50000.0, 'TAXABLE': 50000.0, 'FIT': -14767.29, 'MEDICARE': -725.0, 'MEDICAREADD': 0, 'SST': -3100.0, 'NYINCOMETAX': -3576.71, 'NYSDITAX': -2.6, 'NYPFLTAX': -227.5, 'COMPANYFUTA': 420.0, 'COMPANYMEDICARE': 725.0, 'COMPANYSOCIAL': 3100.0, 'COMPANYSUI': 384.99, 'COMPANYNYREEMPLOYMENT': 9.23, 'NET': 27600.9}
        self._validate_payslip(payslip, payslip_results)

    def test_060_ny_state_tax_single_example_4(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 750,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 3), datetime.date(2023, 4, 3))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 750.0, 'GROSS': 750.0, 'TAXABLE': 750.0, 'FIT': -141.83, 'MEDICARE': -10.88, 'MEDICAREADD': 0, 'SST': -46.5, 'NYINCOMETAX': -44.83, 'NYSDITAX': -0.09, 'NYPFLTAX': -3.41, 'COMPANYFUTA': 45.0, 'COMPANYMEDICARE': 10.88, 'COMPANYSOCIAL': 46.5, 'COMPANYSUI': 23.48, 'COMPANYNYREEMPLOYMENT': 0.56, 'NET': 502.47}
        self._validate_payslip(payslip, payslip_results)

    def test_061_ny_state_tax_married_example_1(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 4,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 7))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 400.0, 'GROSS': 400.0, 'TAXABLE': 400.0, 'FIT': 0, 'MEDICARE': -5.8, 'MEDICAREADD': 0, 'SST': -24.8, 'NYINCOMETAX': -6.86, 'NYSDITAX': -0.6, 'NYPFLTAX': -1.82, 'COMPANYFUTA': 24.0, 'COMPANYMEDICARE': 5.8, 'COMPANYSOCIAL': 24.8, 'COMPANYSUI': 12.52, 'COMPANYNYREEMPLOYMENT': 0.3, 'NET': 360.12}
        self._validate_payslip(payslip, payslip_results)

    def test_062_ny_state_tax_single_example_2(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 5000.0, 'GROSS': 5000.0, 'TAXABLE': 5000.0, 'FIT': -455.04, 'MEDICARE': -72.5, 'MEDICAREADD': 0, 'SST': -310.0, 'NYINCOMETAX': -252.68, 'NYSDITAX': -1.3, 'NYPFLTAX': -22.75, 'COMPANYFUTA': 300.0, 'COMPANYMEDICARE': 72.5, 'COMPANYSOCIAL': 310.0, 'COMPANYSUI': 156.5, 'COMPANYNYREEMPLOYMENT': 3.75, 'NET': 3885.73}
        self._validate_payslip(payslip, payslip_results)

    def test_063_ny_state_tax_single_example_3(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 50000,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 30))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 50000.0, 'GROSS': 50000.0, 'TAXABLE': 50000.0, 'FIT': -12007.83, 'MEDICARE': -725.0, 'MEDICAREADD': 0, 'SST': -3100.0, 'NYINCOMETAX': -3622.01, 'NYSDITAX': -2.6, 'NYPFLTAX': -227.5, 'COMPANYFUTA': 420.0, 'COMPANYMEDICARE': 725.0, 'COMPANYSOCIAL': 3100.0, 'COMPANYSUI': 384.99, 'COMPANYNYREEMPLOYMENT': 9.23, 'NET': 30315.06}
        self._validate_payslip(payslip, payslip_results)

    def test_064_ny_state_tax_single_example_4(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 750,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 3), datetime.date(2023, 4, 3))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 750.0, 'GROSS': 750.0, 'TAXABLE': 750.0, 'FIT': -105.47, 'MEDICARE': -10.88, 'MEDICAREADD': 0, 'SST': -46.5, 'NYINCOMETAX': -45.29, 'NYSDITAX': -0.09, 'NYPFLTAX': -3.41, 'COMPANYFUTA': 45.0, 'COMPANYMEDICARE': 10.88, 'COMPANYSOCIAL': 46.5, 'COMPANYSUI': 23.48, 'COMPANYNYREEMPLOYMENT': 0.56, 'NET': 538.37}
        self._validate_payslip(payslip, payslip_results)

    def test_065_ny_state_tax_common(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nys_123.pdf
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.version.write({
            'wage': 10000,
            'schedule_pay': 'semi-monthly',
            'l10n_us_pre_retirement_amount': 10.0,
            'l10n_us_pre_retirement_type': 'percent',
            'l10n_us_health_benefits_medical': 10.0,
            'l10n_us_health_benefits_dental': 10.0,
            'l10n_us_health_benefits_vision': 10.0,
            'l10n_us_health_benefits_hsa': 10.0,
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip.compute_sheet()

        payslip_results = {'BASIC': 10000.0, 'GROSS': 10000.0, '401K': -1000.0, 'DENTAL': -10.0, 'MEDICAL': -10.0, 'VISION': -10.0, 'MEDICALHSA': -10.0, 'TAXABLE': 8960.0, 'FIT': -1800.53, 'MEDICARE': -144.42, 'MEDICAREADD': 0, 'SST': -617.52, 'NYINCOMETAX': -545.04, 'NYSDITAX': -1.3, 'NYPFLTAX': -45.5, 'COMPANYFUTA': 420.0, 'COMPANYMEDICARE': 144.42, 'COMPANYSOCIAL': 617.52, 'COMPANYSUI': 313.0, 'COMPANYNYREEMPLOYMENT': 7.5, 'NET': 5805.68}
        self._validate_payslip(payslip, payslip_results)

    def test_066_al_state_tax_married_example_1(self):
        # Source https://www.revenue.alabama.gov/ultraviewer/viewer/basic_viewer/index.html?form=2023/01/whbooklet_0123.pdf.pdf
        self.work_address.state_id = self.env.ref('base.state_us_1')
        self.version.write({
            'wage': 850,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'al_status_4',
            'l10n_us_filing_status': 'jointly',
            'children': 2,
        })

        payslip = self._generate_payslip(datetime.date(2025, 4, 1), datetime.date(2025, 4, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 850.0,
            'GROSS': 850.0,
            'TAXABLE': 850.0,
            'FIT': -27.31,
            'MEDICARE': -12.33,
            'MEDICAREADD': 0,
            'SST': -52.7,
            'ALINCOMETAX': -29.98,
            'COMPANYFUTA': 51,
            'COMPANYMEDICARE': 12.33,
            'COMPANYSOCIAL': 52.7,
            'COMPANYSUI': 22.95,
            'COMPANYALESA': 0.51,
            'NET': 727.69,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_067_wa_state_example_1(self):
        # Source https://paidleave.wa.gov/app/uploads/2021/12/Employer-Wage-Reporting-and-Premiums-Toolkit-Version-20.1.pdf
        self.work_address.state_id = self.env.ref('base.state_us_48')
        self.version.write({
            'wage': 3500,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 3500.0,
            'GROSS': 3500.0,
            'TAXABLE': 3500.0,
            'FIT': -100.00,
            'MEDICARE': -50.75,
            'MEDICAREADD': 0.0,
            'SST': -217.0,
            'WACARESFUND': -20.3,
            'WAPFMLFAMILY': -15.53,
            'WAPFMLMEDICAL': -7.5,
            'COMPANYFUTA': 210.0,
            'COMPANYMEDICARE': 50.75,
            'COMPANYSOCIAL': 217.0,
            'COMPANYSUI': 43.75,
            'COMPANYWAPFML': 9.17,
            'COMPANYWAEAF': 1.05,
            'NET': 3088.92,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_068_co_state_example_1(self):
        self.work_address.state_id = self.env.ref('base.state_us_6')
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'monthly',
            'l10n_us_pre_retirement_amount': 500,
            'l10n_us_pre_retirement_type': 'fixed',
            'l10n_us_health_benefits_medical': 50,
        })
        self.employee.write({
            'l10n_us_filing_status': 'single',
            'l10n_us_state_filing_status': 'co_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 5000.0,
            'GROSS': 5000.0,
            '401K': -500.0,
            'MEDICAL': -50.0,
            'TAXABLE': 4450.0,
            'FIT': -364.13,
            'MEDICARE': -71.78,
            'MEDICAREADD': 0.0,
            'SST': -306.9,
            'COINCOMETAX': -177.47,
            'COFAMLI': -22.5,
            'COMPANYFUTA': 297.0,
            'COMPANYCOFAMLI': 22.5,
            'COMPANYMEDICARE': 71.78,
            'COMPANYSOCIAL': 306.9,
            'COMPANYSUI': 84.15,
            'COMPANYCOSOLVENCY': 6.68,
            'COMPANYCOSUPPORT': 8.42,
            'NET': 3507.23,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_069_bonus(self):
        self.version.write({
            'wage': 3416.68,
            'schedule_pay': 'semi-monthly',
        })

        payslip = self._generate_payslip(datetime.date(2023, 4, 1), datetime.date(2023, 4, 15))
        payslip._set_input_value('BONUS', 500)
        payslip.compute_sheet()

        payslip_results = {'BASIC': 3416.68, 'BONUS': 500.0, 'GROSS': 3916.68, 'TAXABLE': 3916.68, 'FIT': -539.19, 'MEDICARE': -56.79, 'MEDICAREADD': 0.0, 'SST': -242.83, 'CAINCOMETAX': -229.65, 'CASDITAX': -35.25, 'COMPANYFUTA': 235.0, 'COMPANYMEDICARE': 56.79, 'COMPANYSOCIAL': 242.83, 'COMPANYSUI': 66.58, 'COMPANYCAETT': 3.92, 'NET': 2812.96}
        self._validate_payslip(payslip, payslip_results)

    def test_070_ny_nyc_tax_single_example_1(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 400.0,
            'GROSS': 400.0,
            'TAXABLE': 400.0,
            'FIT': -9.04,
            'MEDICARE': -5.8,
            'MEDICAREADD': 0,
            'SST': -24.8,
            'NYINCOMETAX': -8.01,
            'NYNYCINCOMETAX': -6.11,
            'NYSDITAX': -0.6,
            'NYPFLTAX': -1.73,
            'COMPANYFUTA': 24.0,
            'COMPANYMEDICARE': 5.8,
            'COMPANYSOCIAL': 24.8,
            'COMPANYSUI': 22.32,
            'COMPANYNYREEMPLOYMENT': 0.3,
            'NET': 343.92,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_071_ny_nyc_tax_single_example_2(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 5000.0,
            'GROSS': 5000.0,
            'TAXABLE': 5000.0,
            'FIT': -732.08,
            'MEDICARE': -72.5,
            'MEDICAREADD': 0,
            'SST': -310.0,
            'NYINCOMETAX': -258.5,
            'NYNYCINCOMETAX': -188.8,
            'NYSDITAX': -1.3,
            'NYPFLTAX': -21.6,
            'COMPANYFUTA': 300.0,
            'COMPANYMEDICARE': 72.5,
            'COMPANYSOCIAL': 310.0,
            'COMPANYSUI': 279.0,
            'COMPANYNYREEMPLOYMENT': 3.75,
            'NET': 3415.22,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_072_ny_nyc_tax_single_example_3(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 50000,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 50000.0,
            'GROSS': 50000.0,
            'TAXABLE': 50000.0,
            'FIT': -14427.85,
            'MEDICARE': -725.0,
            'MEDICAREADD': 0,
            'SST': -3100.0,
            'NYINCOMETAX': -3576.63,
            'NYNYCINCOMETAX': -2070.5,
            'NYSDITAX': -2.6,
            'NYPFLTAX': -216.0,
            'COMPANYFUTA': 420.0,
            'COMPANYMEDICARE': 725.0,
            'COMPANYSOCIAL': 3100.0,
            'COMPANYSUI': 725.4,
            'COMPANYNYREEMPLOYMENT': 9.75,
            'NET': 25881.42,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_073_ny_nyc_tax_single_example_4(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 750,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 3), datetime.date(2026, 4, 3))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 750.0,
            'GROSS': 750.0,
            'TAXABLE': 750.0,
            'FIT': -136.67,
            'MEDICARE': -10.88,
            'MEDICAREADD': 0,
            'SST': -46.5,
            'NYINCOMETAX': -44.1,
            'NYNYCINCOMETAX': -29.51,
            'NYSDITAX': -0.09,
            'NYPFLTAX': -3.24,
            'COMPANYFUTA': 45.0,
            'COMPANYMEDICARE': 10.88,
            'COMPANYSOCIAL': 46.5,
            'COMPANYSUI': 41.85,
            'COMPANYNYREEMPLOYMENT': 0.56,
            'NET': 479.02,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_074_ny_nyc_tax_married_example_1(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 4,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 400.0,
            'GROSS': 400.0,
            'TAXABLE': 400.0,
            'FIT': 0,
            'MEDICARE': -5.8,
            'MEDICAREADD': 0,
            'SST': -24.8,
            'NYINCOMETAX': -6.69,
            'NYNYCINCOMETAX': -5.17,
            'NYSDITAX': -0.6,
            'NYPFLTAX': -1.73,
            'COMPANYFUTA': 24.0,
            'COMPANYMEDICARE': 5.8,
            'COMPANYSOCIAL': 24.8,
            'COMPANYSUI': 22.32,
            'COMPANYNYREEMPLOYMENT': 0.3,
            'NET': 355.21,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_075_ny_nyc_tax_married_example_2(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 5000.0,
            'GROSS': 5000.0,
            'TAXABLE': 5000.0,
            'FIT': -418.33,
            'MEDICARE': -72.5,
            'MEDICAREADD': 0,
            'SST': -310.0,
            'NYINCOMETAX': -248.12,
            'NYNYCINCOMETAX': -184.37,
            'NYSDITAX': -1.3,
            'NYPFLTAX': -21.6,
            'COMPANYFUTA': 300.0,
            'COMPANYMEDICARE': 72.5,
            'COMPANYSOCIAL': 310.0,
            'COMPANYSUI': 279.0,
            'COMPANYNYREEMPLOYMENT': 3.75,
            'NET': 3743.78,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_076_ny_nyc_tax_married_example_3(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 50000,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 50000.0,
            'GROSS': 50000.0,
            'TAXABLE': 50000.0,
            'FIT': -11355.71,
            'MEDICARE': -725.0,
            'MEDICAREADD': 0,
            'SST': -3100.0,
            'NYINCOMETAX': -3622.09,
            'NYNYCINCOMETAX': -2068.73,
            'NYSDITAX': -2.6,
            'NYPFLTAX': -216.0,
            'COMPANYFUTA': 420.0,
            'COMPANYMEDICARE': 725.0,
            'COMPANYSOCIAL': 3100.0,
            'COMPANYSUI': 725.4,
            'COMPANYNYREEMPLOYMENT': 9.75,
            'NET': 28909.87,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_077_ny_nyc_tax_married_example_4(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "New York"
        self.version.write({
            'wage': 750,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 3), datetime.date(2026, 4, 3))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 750.0,
            'GROSS': 750.0,
            'TAXABLE': 750.0,
            'FIT': -97.08,
            'MEDICARE': -10.88,
            'MEDICAREADD': 0,
            'SST': -46.5,
            'NYINCOMETAX': -44.58,
            'NYNYCINCOMETAX': -29.43,
            'NYSDITAX': -0.09,
            'NYPFLTAX': -3.24,
            'COMPANYFUTA': 45.0,
            'COMPANYMEDICARE': 10.88,
            'COMPANYSOCIAL': 46.5,
            'COMPANYSUI': 41.85,
            'COMPANYNYREEMPLOYMENT': 0.56,
            'NET': 518.21,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_078_ny_yonkers_tax_single_example_1(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 400.0,
            'GROSS': 400.0,
            'TAXABLE': 400.0,
            'FIT': -9.04,
            'MEDICARE': -5.8,
            'MEDICAREADD': 0,
            'SST': -24.8,
            'NYINCOMETAX': -8.01,
            'NYYONKERSINCOMETAX': -1.34,
            'NYSDITAX': -0.6,
            'NYPFLTAX': -1.73,
            'COMPANYFUTA': 24.0,
            'COMPANYMEDICARE': 5.8,
            'COMPANYSOCIAL': 24.8,
            'COMPANYSUI': 22.32,
            'COMPANYNYREEMPLOYMENT': 0.3,
            'NET': 348.69,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_079_ny_yonkers_tax_single_example_2(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 5000.0,
            'GROSS': 5000.0,
            'TAXABLE': 5000.0,
            'FIT': -732.08,
            'MEDICARE': -72.5,
            'MEDICAREADD': 0,
            'SST': -310.0,
            'NYINCOMETAX': -258.5,
            'NYYONKERSINCOMETAX': -43.3,
            'NYSDITAX': -1.3,
            'NYPFLTAX': -21.6,
            'COMPANYFUTA': 300.0,
            'COMPANYMEDICARE': 72.5,
            'COMPANYSOCIAL': 310.0,
            'COMPANYSUI': 279.0,
            'COMPANYNYREEMPLOYMENT': 3.75,
            'NET': 3560.71,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_080_ny_yonkers_tax_single_example_3(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 50000,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 50000.0,
            'GROSS': 50000.0,
            'TAXABLE': 50000.0,
            'FIT': -14427.85,
            'MEDICARE': -725.0,
            'MEDICAREADD': 0,
            'SST': -3100.0,
            'NYINCOMETAX': -3576.63,
            'NYYONKERSINCOMETAX': -599.08,
            'NYSDITAX': -2.6,
            'NYPFLTAX': -216.0,
            'COMPANYFUTA': 420.0,
            'COMPANYMEDICARE': 725.0,
            'COMPANYSOCIAL': 3100.0,
            'COMPANYSUI': 725.4,
            'COMPANYNYREEMPLOYMENT': 9.75,
            'NET': 27352.84,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_081_ny_yonkers_tax_single_example_4(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 750,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ny_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 3), datetime.date(2026, 4, 3))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 750.0,
            'GROSS': 750.0,
            'TAXABLE': 750.0,
            'FIT': -136.67,
            'MEDICARE': -10.88,
            'MEDICAREADD': 0,
            'SST': -46.5,
            'NYINCOMETAX': -44.1,
            'NYYONKERSINCOMETAX': -7.39,
            'NYSDITAX': -0.09,
            'NYPFLTAX': -3.24,
            'COMPANYFUTA': 45.0,
            'COMPANYMEDICARE': 10.88,
            'COMPANYSOCIAL': 46.5,
            'COMPANYSUI': 41.85,
            'COMPANYNYREEMPLOYMENT': 0.56,
            'NET': 501.14,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_082_ny_yonkers_tax_married_example_1(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 4,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 400.0,
            'GROSS': 400.0,
            'TAXABLE': 400.0,
            'FIT': 0,
            'MEDICARE': -5.8,
            'MEDICAREADD': 0,
            'SST': -24.8,
            'NYINCOMETAX': -6.69,
            'NYYONKERSINCOMETAX': -1.12,
            'NYSDITAX': -0.6,
            'NYPFLTAX': -1.73,
            'COMPANYFUTA': 24.0,
            'COMPANYMEDICARE': 5.8,
            'COMPANYSOCIAL': 24.8,
            'COMPANYSUI': 22.32,
            'COMPANYNYREEMPLOYMENT': 0.3,
            'NET': 359.26,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_083_ny_yonkers_tax_married_example_2(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 5000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 5000.0,
            'GROSS': 5000.0,
            'TAXABLE': 5000.0,
            'FIT': -418.33,
            'MEDICARE': -72.5,
            'MEDICAREADD': 0,
            'SST': -310.0,
            'NYINCOMETAX': -248.12,
            'NYYONKERSINCOMETAX': -41.56,
            'NYSDITAX': -1.3,
            'NYPFLTAX': -21.6,
            'COMPANYFUTA': 300.0,
            'COMPANYMEDICARE': 72.5,
            'COMPANYSOCIAL': 310.0,
            'COMPANYSUI': 279.0,
            'COMPANYNYREEMPLOYMENT': 3.75,
            'NET': 3886.59,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_084_ny_yonkers_tax_married_example_3(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 50000,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 1), datetime.date(2026, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 50000.0,
            'GROSS': 50000.0,
            'TAXABLE': 50000.0,
            'FIT': -11355.71,
            'MEDICARE': -725.0,
            'MEDICAREADD': 0,
            'SST': -3100.0,
            'NYINCOMETAX': -3622.09,
            'NYYONKERSINCOMETAX': -606.7,
            'NYSDITAX': -2.6,
            'NYPFLTAX': -216.0,
            'COMPANYFUTA': 420.0,
            'COMPANYMEDICARE': 725.0,
            'COMPANYSOCIAL': 3100.0,
            'COMPANYSUI': 725.4,
            'COMPANYNYREEMPLOYMENT': 9.75,
            'NET': 30371.9,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_085_ny_yonkers_tax_married_example_4(self):
        # Source https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_y.pdf (Revised 1/26)
        self.work_address.state_id = self.env.ref('base.state_us_27')
        self.work_address.city = "Yonkers"
        self.version.write({
            'wage': 750,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ny_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 4, 3), datetime.date(2026, 4, 3))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 750.0,
            'GROSS': 750.0,
            'TAXABLE': 750.0,
            'FIT': -97.08,
            'MEDICARE': -10.88,
            'MEDICAREADD': 0,
            'SST': -46.5,
            'NYINCOMETAX': -44.58,
            'NYYONKERSINCOMETAX': -7.47,
            'NYSDITAX': -0.09,
            'NYPFLTAX': -3.24,
            'COMPANYFUTA': 45.0,
            'COMPANYMEDICARE': 10.88,
            'COMPANYSOCIAL': 46.5,
            'COMPANYSUI': 41.85,
            'COMPANYNYREEMPLOYMENT': 0.56,
            'NET': 540.18,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_086_ia_state_tax_other_example_1(self):
        # Example 1 from https://revenue.iowa.gov/media/53/download?inline
        self.work_address.state_id = self.env.ref('base.state_us_16')
        self.version.write({
            'wage': 2100,
            'schedule_pay': 'bi-weekly',
            'l10n_us_state_withholding_allowance': 40,
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ia_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2100.0,
            'GROSS': 2100.0,
            'TAXABLE': 2100.0,
            'FIT': -168.15,
            'MEDICARE': -30.45,
            'MEDICAREADD': 0,
            'SST': -130.2,
            'IAINCOMETAX': -59.26,
            'COMPANYFUTA': 126.0,
            'COMPANYMEDICARE': 30.45,
            'COMPANYSOCIAL': 130.2,
            'COMPANYSUI': 21.0,
            'NET': 1711.93,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_087_ia_state_tax_married_example_2(self):
        # Example 2 from https://revenue.iowa.gov/media/53/download?inline
        self.work_address.state_id = self.env.ref('base.state_us_16')
        self.version.write({
            'wage': 2100,
            'schedule_pay': 'bi-weekly',
            'l10n_us_state_withholding_allowance': 80,
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ia_status_3',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2100.0,
            'GROSS': 2100.0,
            'TAXABLE': 2100.0,
            'FIT': -86.15,
            'MEDICARE': -30.45,
            'MEDICAREADD': 0,
            'SST': -130.2,
            'IAINCOMETAX': -38.72,
            'COMPANYFUTA': 126.0,
            'COMPANYMEDICARE': 30.45,
            'COMPANYSOCIAL': 130.2,
            'COMPANYSUI': 21.0,
            'NET': 1814.47,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_088_ga_state_tax_married_example_1(self):
        # Example 1 from https://dor.georgia.gov/document/document/2026-employers-tax-guide/download
        self.work_address.state_id = self.env.ref('base.state_us_11')
        self.version.write({
            'wage': 1470.83,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_state_filing_status': 'ga_status_3',
            'l10n_us_filing_status': 'jointly',
            'children': 1,
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 1470.83,
            'GROSS': 1470.83,
            'TAXABLE': 1470.83,
            'FIT': -12.92,
            'MEDICARE': -21.33,
            'MEDICAREADD': 0,
            'SST': -91.19,
            'GAINCOMETAX': -15.79,
            'COMPANYFUTA': 88.25,
            'COMPANYMEDICARE': 21.33,
            'COMPANYSOCIAL': 91.19,
            'COMPANYSUI': 39.71,
            'NET': 1329.61,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_089_ga_state_tax_head_of_household_example_2(self):
        # Example 2 from https://dor.georgia.gov/document/document/2026-employers-tax-guide/download
        self.work_address.state_id = self.env.ref('base.state_us_11')
        self.version.write({
            'wage': 730.77,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'ga_status_4',
            'l10n_us_filing_status': 'single',
            'children': 2,
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 730.77,
            'GROSS': 730.77,
            'TAXABLE': 730.77,
            'FIT': -11.15,
            'MEDICARE': -10.6,
            'MEDICAREADD': 0,
            'SST': -45.31,
            'GAINCOMETAX': 0,
            'COMPANYFUTA': 43.85,
            'COMPANYMEDICARE': 10.6,
            'COMPANYSOCIAL': 45.31,
            'COMPANYSUI': 19.73,
            'NET': 663.71,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_090_ms_state_tax_single_example_1(self):
        self.work_address.state_id = self.env.ref('base.state_us_37')
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ms_status_1',
            'l10n_us_filing_status': 'single',
            'l10n_us_state_withholding_allowance': 6000,
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'MSINCOMETAX': -52.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 20.0,
            'NET': 1638.85,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_091_nj_state_tax_rate_a_example_2(self):
        # Source https://www.nj.gov/treasury/taxation/pdf/current/njwt.pdf
        # Rate Table A, Example 2: Single, weekly $700, 1 allowance, tax = $11.84
        self.work_address.state_id = self.env.ref('base.state_us_25')
        self.version.write({
            'wage': 700,
            'schedule_pay': 'weekly',
            'l10n_us_nj_rate_table': 'A',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_state_filing_status': 'nj_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 700.0,
            'GROSS': 700.0,
            'TAXABLE': 700.0,
            'FIT': -42.08,
            'MEDICARE': -10.15,
            'MEDICAREADD': 0,
            'SST': -43.4,
            'NJINCOMETAX': -11.84,
            'NJSDITAX': -1.33,
            'NJFLITAX': -1.61,
            'NJSUITAX': -2.98,
            'COMPANYFUTA': 42.0,
            'COMPANYMEDICARE': 10.15,
            'COMPANYSOCIAL': 43.4,
            'COMPANYSUI': 19.6,
            'COMPANYNJ_HCS': 0,
            'COMPANYNJ_SDI': 3.5,
            'COMPANYNJ_WDSWF': 0.82,
            'NET': 586.61,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_092_nj_state_tax_rate_b_example_3(self):
        # Source https://www.nj.gov/treasury/taxation/pdf/current/njwt.pdf
        # Rate Table B, Example 3: Married/Civil Union, weekly $1400, 3 allowances, tax = $27.58
        self.work_address.state_id = self.env.ref('base.state_us_25')
        self.version.write({
            'wage': 1400,
            'schedule_pay': 'weekly',
            'l10n_us_nj_rate_table': 'B',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'nj_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 1400.0,
            'GROSS': 1400.0,
            'TAXABLE': 1400.0,
            'FIT': -84.15,
            'MEDICARE': -20.3,
            'MEDICAREADD': 0,
            'SST': -86.8,
            'NJINCOMETAX': -27.58,
            'NJSDITAX': -2.66,
            'NJFLITAX': -3.22,
            'NJSUITAX': -5.95,
            'COMPANYFUTA': 84.0,
            'COMPANYMEDICARE': 20.3,
            'COMPANYSOCIAL': 86.8,
            'COMPANYSUI': 39.2,
            'COMPANYNJ_HCS': 0,
            'COMPANYNJ_SDI': 7.0,
            'COMPANYNJ_WDSWF': 1.65,
            'NET': 1169.34,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_093_co_state_0_income(self):
        self.work_address.state_id = self.env.ref('base.state_us_6')
        self.version.wage = 0
        self.employee.l10n_us_state_withholding_allowance = 1000

        payslip = self._generate_payslip(datetime.date(2026, 3, 1), datetime.date(2026, 3, 31))
        payslip.compute_sheet()
        payslip_results = {
            'BASIC': 0,
            'COFAMLI': 0,
            'COINCOMETAX': 0,  # Should not be positive
            'COMPANYCOFAMLI': 0,
            'COMPANYCOSOLVENCY': 0,
            'COMPANYCOSUPPORT': 0,
            'COMPANYFUTA': 0,
            'COMPANYMEDICARE': 0,
            'COMPANYSOCIAL': 0,
            'COMPANYSUI': 0,
            'FIT': 0,
            'GROSS': 0,
            'MEDICARE': 0,
            'MEDICAREADD': 0,
            'NET': 0,
            'SST': 0,
            'TAXABLE': 0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_088_al_state_tax_0_income(self):
        self.work_address.state_id = self.env.ref('base.state_us_1')
        self.version.write({
            'wage': 0,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'al_status_4',
            'l10n_us_filing_status': 'jointly',
            'children': 2,
        })

        payslip = self._generate_payslip(datetime.date(2025, 4, 1), datetime.date(2025, 4, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 0,
            'GROSS': 0,
            'TAXABLE': 0,
            'FIT': 0,
            'MEDICARE': 0,
            'MEDICAREADD': 0,
            'SST': 0,
            'ALINCOMETAX': 0,
            'COMPANYFUTA': 0,
            'COMPANYMEDICARE': 0,
            'COMPANYSOCIAL': 0,
            'COMPANYSUI': 0,
            'COMPANYALESA': 0,
            'NET': 0,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_094_mi_state_income_tax(self):
        # Example from the Michigan Income Tax Withholding Guide (Form 446), 2026:
        # flat 4.25% rate, $5,900 annual personal exemption per allowance claimed.
        self.work_address.state_id = self.env.ref('base.state_us_35')
        self.version.write({
            'wage': 2500,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 1,
            'l10n_us_state_filing_status': 'mi_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2500.0,
            'GROSS': 2500.0,
            'TAXABLE': 2500.0,
            'FIT': -216.15,
            'MEDICARE': -36.25,
            'MEDICAREADD': 0,
            'SST': -155.0,
            'MIINCOMETAX': -96.61,
            'MICITYTAX': 0,
            'COMPANYFUTA': 150.0,
            'COMPANYMEDICARE': 36.25,
            'COMPANYSOCIAL': 155.0,
            'COMPANYSUI': 67.5,
            'NET': 1995.99,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_095_mi_city_tax_detroit_resident(self):
        # Employee lives and works in Detroit: pays the Detroit resident rate on all wages.
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_35').id,
            'city': 'Detroit',
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
            'private_city': 'Detroit',
            'private_state_id': self.env.ref('base.state_us_35').id,
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'mi_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'MIINCOMETAX': -85.0,
            'MICITYTAX': -48.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 54.0,
            'NET': 1557.85,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_096_mi_city_tax_detroit_nonresident(self):
        # Employee lives in Ann Arbor (no city tax) but works in Detroit: pays the
        # Detroit nonresident rate instead of the resident rate.
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_35').id,
            'city': 'Detroit',
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
            'private_city': 'Ann Arbor',
            'private_state_id': self.env.ref('base.state_us_35').id,
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'mi_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'MIINCOMETAX': -85.0,
            'MICITYTAX': -24.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 54.0,
            'NET': 1581.85,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_097_mo_state_income_tax(self):
        # Missouri Withholding Formula Example (spouse works, monthly):
        # annual gross $35,000, standard deduction $16,100, annual tax $707.81.
        self.work_address.state_id = self.env.ref('base.state_us_38')
        self.version.write({
            'wage': 2916.67,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'mo_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2916.67,
            'GROSS': 2916.67,
            'TAXABLE': 2916.67,
            'FIT': -23.33,
            'MEDICARE': -42.29,
            'MEDICAREADD': 0,
            'SST': -180.83,
            'MOINCOMETAX': -59.0,
            'COMPANYFUTA': 175.0,
            'COMPANYMEDICARE': 42.29,
            'COMPANYSOCIAL': 180.83,
            'COMPANYSUI': 69.3,
            'NET': 2611.21,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_098_mo_stlouis_earnings_tax(self):
        # Employee works in St. Louis: 1% city earnings tax on top of MO state tax.
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_38').id,
            'city': 'St. Louis',
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'mo_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'MOINCOMETAX': -58.0,
            'MOSTLOUISTAX': -20.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 47.52,
            'NET': 1612.85,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_099_mo_kc_earnings_tax(self):
        # Employee lives in Kansas City: 1% city earnings tax on top of MO state tax.
        self.work_address.state_id = self.env.ref('base.state_us_38')
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
            'private_city': 'Kansas City',
            'private_state_id': self.env.ref('base.state_us_38').id,
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'mo_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'MOINCOMETAX': -58.0,
            'MOKCTAX': -20.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 47.52,
            'NET': 1612.85,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_100_ky_state_income_tax(self):
        # 2026 example: monthly wages $3,270, $3,360 standard deduction, flat 3.5% rate.
        self.work_address.state_id = self.env.ref('base.state_us_18')
        self.version.write({
            'wage': 3270,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ky_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 3270.0,
            'GROSS': 3270.0,
            'TAXABLE': 3270.0,
            'FIT': -210.73,
            'MEDICARE': -47.42,
            'MEDICAREADD': 0,
            'SST': -202.74,
            'KYINCOMETAX': -104.65,
            'KYCOUNTYTAX': 0,
            'COMPANYFUTA': 196.2,
            'COMPANYMEDICARE': 47.42,
            'COMPANYSOCIAL': 202.74,
            'COMPANYSUI': 88.29,
            'NET': 2704.46,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_101_ky_state_income_tax_biweekly(self):
        # 2026 example: bi-weekly wages $1,500, $3,360 standard deduction, flat 3.5% rate.
        # The spec's own arithmetic states the result as $47, but $1,247.40 / 26 is $47.98.
        self.work_address.state_id = self.env.ref('base.state_us_18')
        self.version.write({
            'wage': 1500,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ky_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 1500.0,
            'GROSS': 1500.0,
            'TAXABLE': 1500.0,
            'FIT': -96.15,
            'MEDICARE': -21.75,
            'MEDICAREADD': 0,
            'SST': -93.0,
            'KYINCOMETAX': -47.98,
            'KYCOUNTYTAX': 0,
            'COMPANYFUTA': 90.0,
            'COMPANYMEDICARE': 21.75,
            'COMPANYSOCIAL': 93.0,
            'COMPANYSUI': 40.5,
            'NET': 1241.12,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_102_ut_state_income_tax_weekly_single(self):
        # Example 1: weekly/single, gross $400, allowance 9, threshold 180, tax = $11.66.
        self.work_address.state_id = self.env.ref('base.state_us_45')
        self.version.write({
            'wage': 400,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ut_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 400.0,
            'GROSS': 400.0,
            'TAXABLE': 400.0,
            'FIT': -9.04,
            'MEDICARE': -5.8,
            'MEDICAREADD': 0,
            'SST': -24.8,
            'UTINCOMETAX': -11.66,
            'COMPANYFUTA': 24.0,
            'COMPANYMEDICARE': 5.8,
            'COMPANYSOCIAL': 24.8,
            'COMPANYSUI': 4.0,
            'NET': 348.7,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_103_ut_state_income_tax_semimonthly_married(self):
        # Example 2: semi-monthly/married, gross $1,200, allowance 40, threshold 779, tax = $18.87.
        self.work_address.state_id = self.env.ref('base.state_us_45')
        self.version.write({
            'wage': 1200,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ut_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 1200.0,
            'GROSS': 1200.0,
            'TAXABLE': 1200.0,
            'FIT': 0.0,
            'MEDICARE': -17.4,
            'MEDICAREADD': 0,
            'SST': -74.4,
            'UTINCOMETAX': -18.87,
            'COMPANYFUTA': 72.0,
            'COMPANYMEDICARE': 17.4,
            'COMPANYSOCIAL': 74.4,
            'COMPANYSUI': 12.0,
            'NET': 1089.33,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_104_ut_state_income_tax_monthly_married(self):
        # Example 3: monthly/married, gross $7,800, allowance 81, threshold 1,558, tax = $347.10.
        self.work_address.state_id = self.env.ref('base.state_us_45')
        self.version.write({
            'wage': 7800,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ut_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 7800.0,
            'GROSS': 7800.0,
            'TAXABLE': 7800.0,
            'FIT': -572.67,
            'MEDICARE': -113.1,
            'MEDICAREADD': 0,
            'SST': -483.6,
            'UTINCOMETAX': -347.1,
            'COMPANYFUTA': 420.0,
            'COMPANYMEDICARE': 113.1,
            'COMPANYSOCIAL': 483.6,
            'COMPANYSUI': 78.0,
            'NET': 6283.53,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_105_ut_state_income_tax_daily_married(self):
        # Pub 14, "Example 6 - Use Schedule 8, Daily/Married" applies the daily/married
        # allowance of 4 and threshold of $72 to a gross of $175, which gives a $5.13 tax.
        self.work_address.state_id = self.env.ref('base.state_us_45')
        self.version.write({
            'wage': 175,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ut_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 2), datetime.date(2026, 1, 2))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 175.0,
            'GROSS': 175.0,
            'TAXABLE': 175.0,
            'FIT': -5.12,
            'MEDICARE': -2.54,
            'MEDICAREADD': 0,
            'SST': -10.85,
            'UTINCOMETAX': -5.13,
            'COMPANYFUTA': 10.5,
            'COMPANYMEDICARE': 2.54,
            'COMPANYSOCIAL': 10.85,
            'COMPANYSUI': 1.75,
            'NET': 151.37,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_106_sc_state_income_tax_weekly(self):
        # Example 1: weekly, gross $750, 3 allowances, tax = $10.58.
        self.work_address.state_id = self.env.ref('base.state_us_41')
        self.version.write({
            'wage': 750,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'sc_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 750.0,
            'GROSS': 750.0,
            'TAXABLE': 750.0,
            'FIT': -48.08,
            'MEDICARE': -10.88,
            'MEDICAREADD': 0,
            'SST': -46.5,
            'SCINCOMETAX': -10.58,
            'COMPANYFUTA': 45.0,
            'COMPANYMEDICARE': 10.88,
            'COMPANYSOCIAL': 46.5,
            'COMPANYSUI': 7.5,
            'NET': 633.97,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_107_sc_state_income_tax_biweekly(self):
        # Example 2: biweekly, gross $1,500, 2 allowances, tax = $32.69.
        self.work_address.state_id = self.env.ref('base.state_us_41')
        self.version.write({
            'wage': 1500,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 2,
            'l10n_us_state_filing_status': 'sc_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 1500.0,
            'GROSS': 1500.0,
            'TAXABLE': 1500.0,
            'FIT': -96.15,
            'MEDICARE': -21.75,
            'MEDICAREADD': 0,
            'SST': -93.0,
            'SCINCOMETAX': -32.69,
            'COMPANYFUTA': 90.0,
            'COMPANYMEDICARE': 21.75,
            'COMPANYSOCIAL': 93.0,
            'COMPANYSUI': 15.0,
            'NET': 1256.41,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_108_sc_state_income_tax_monthly_no_allowances(self):
        # Example 3: monthly, gross $7,800, 0 allowances, tax = $413.33.
        self.work_address.state_id = self.env.ref('base.state_us_41')
        self.version.write({
            'wage': 7800,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'sc_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 7800.0,
            'GROSS': 7800.0,
            'TAXABLE': 7800.0,
            'FIT': -980.17,
            'MEDICARE': -113.1,
            'MEDICAREADD': 0,
            'SST': -483.6,
            'SCINCOMETAX': -413.33,
            'COMPANYFUTA': 420.0,
            'COMPANYMEDICARE': 113.1,
            'COMPANYSOCIAL': 483.6,
            'COMPANYSUI': 78.0,
            'NET': 5809.81,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_109_ks_state_income_tax_semimonthly_married(self):
        # Spec example: semimonthly/married, gross $2,000, tax = $41. The 3 allowances
        # cover the filer, the spouse and a single dependent.
        self.work_address.state_id = self.env.ref('base.state_us_17')
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'semi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 3,
            'l10n_us_state_filing_status': 'ks_status_4',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 15))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -65.83,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'KSINCOMETAX': -41.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 35.0,
            'NET': 1740.17,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_110_ks_state_income_tax_weekly_single(self):
        # Table 1(a) Single: weekly, gross $600, no allowance claimed, tax = $28.
        self.work_address.state_id = self.env.ref('base.state_us_17')
        self.version.write({
            'wage': 600,
            'schedule_pay': 'weekly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'ks_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 7))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 600.0,
            'GROSS': 600.0,
            'TAXABLE': 600.0,
            'FIT': -30.08,
            'MEDICARE': -8.7,
            'MEDICAREADD': 0,
            'SST': -37.2,
            'KSINCOMETAX': -28.0,
            'COMPANYFUTA': 36.0,
            'COMPANYMEDICARE': 8.7,
            'COMPANYSOCIAL': 37.2,
            'COMPANYSUI': 10.5,
            'NET': 496.02,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_111_ky_county_tax_fayette(self):
        # Fayette county occupational tax is 2.25% (Kentucky Association of Counties).
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_18').id,
            'city_id': self.env.ref('l10n_us.city_us_132').id,
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ky_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'KYINCOMETAX': -65.48,
            'KYCOUNTYTAX': -45.0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 54.0,
            'NET': 1580.37,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_112_ky_county_tax_no_occupational_tax(self):
        # Anderson county doesn't levy an occupational tax on payroll.
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_18').id,
            'city_id': self.env.ref('l10n_us.city_us_3536').id,
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ky_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 2000.0,
            'GROSS': 2000.0,
            'TAXABLE': 2000.0,
            'FIT': -156.15,
            'MEDICARE': -29.0,
            'MEDICAREADD': 0,
            'SST': -124.0,
            'KYINCOMETAX': -65.48,
            'KYCOUNTYTAX': 0,
            'COMPANYFUTA': 120.0,
            'COMPANYMEDICARE': 29.0,
            'COMPANYSOCIAL': 124.0,
            'COMPANYSUI': 54.0,
            'NET': 1625.37,
        }
        self._validate_payslip(payslip, payslip_results)

    def test_113_mi_city_tax_same_city_name_other_state(self):
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_35').id,
            'city': 'Ann Arbor',
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
            'private_city_id': self.env.ref('l10n_us.city_us_18279').id,
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'mi_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        city_tax = payslip.line_ids.filtered(lambda line: line.code == 'MICITYTAX')
        self.assertEqual(city_tax.total, 0)

    def test_114_mo_city_tax_same_city_name_other_state(self):
        self.work_address.write({
            'state_id': self.env.ref('base.state_us_38').id,
            'city': 'Springfield',
        })
        self.version.write({
            'wage': 2000,
            'schedule_pay': 'bi-weekly',
            'private_city_id': self.env.ref('l10n_us.city_us_284').id,
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'mo_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 14))
        payslip.compute_sheet()

        self._validate_rule_computed(payslip, 'MOKCTAX', False)

    def test_115_ut_state_income_tax_bimonthly(self):
        self.work_address.state_id = self.env.ref('base.state_us_45')
        self.version.write({
            'wage': 15600,
            'schedule_pay': 'bi-monthly',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ut_status_2',
            'l10n_us_filing_status': 'jointly',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 2, 28))
        payslip.compute_sheet()

        income_tax = payslip.line_ids.filtered(lambda line: line.code == 'UTINCOMETAX')
        self.assertAlmostEqual(income_tax.total, -694.20, places=2)

    def test_116_ks_state_income_tax_bimonthly(self):
        self.work_address.state_id = self.env.ref('base.state_us_17')
        self.version.write({
            'wage': 6000,
            'schedule_pay': 'bi-monthly',
        })
        self.employee.write({
            'l10n_us_w4_allowances_count': 0,
            'l10n_us_state_filing_status': 'ks_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 2, 28))
        payslip.compute_sheet()

        income_tax = payslip.line_ids.filtered(lambda line: line.code == 'KSINCOMETAX')
        self.assertEqual(income_tax.total, -287)

    def test_117_ks_state_income_tax_allowance_steps(self):
        # Kansas allowance tables, monthly on a $10,000 gross: the first allowance is
        # worth $763.33 for everyone, the second one only for a joint filer, and any
        # further allowance is worth $193.33.
        self.work_address.state_id = self.env.ref('base.state_us_17')
        self.version.write({
            'wage': 10000,
            'schedule_pay': 'monthly',
        })
        for filing_status, us_status, allowances, expected in [
            ('ks_status_1', 'single', 0, -534),
            ('ks_status_1', 'single', 1, -491),
            ('ks_status_1', 'single', 2, -481),
            ('ks_status_1', 'single', 3, -470),
            ('ks_status_4', 'jointly', 0, -505),
            ('ks_status_4', 'jointly', 1, -463),
            ('ks_status_4', 'jointly', 2, -420),
            ('ks_status_4', 'jointly', 3, -409),
        ]:
            with self.subTest(filing_status=filing_status, allowances=allowances):
                self.employee.write({
                    'l10n_us_w4_allowances_count': allowances,
                    'l10n_us_state_filing_status': filing_status,
                    'l10n_us_filing_status': us_status,
                })
                payslip = self._generate_payslip(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
                payslip.compute_sheet()

                income_tax = payslip.line_ids.filtered(lambda line: line.code == 'KSINCOMETAX')
                self.assertEqual(income_tax.total, expected)

    def test_118_ut_state_income_tax_daily_single(self):
        # The daily/single allowance of 2 and threshold of $36 are half the daily/married
        # ones, so the $175 gross of test 105 is taxed $7.59 instead of $5.13.
        self.work_address.state_id = self.env.ref('base.state_us_45')
        self.version.write({
            'wage': 175,
            'schedule_pay': 'daily',
        })
        self.employee.write({
            'l10n_us_state_filing_status': 'ut_status_1',
            'l10n_us_filing_status': 'single',
        })

        payslip = self._generate_payslip(datetime.date(2026, 1, 2), datetime.date(2026, 1, 2))
        payslip.compute_sheet()

        income_tax = payslip.line_ids.filtered(lambda line: line.code == 'UTINCOMETAX')
        self.assertAlmostEqual(income_tax.total, -7.59, places=2)

    def test_089_or_state_fmli(self):
        self.work_address.state_id = self.env.ref('base.state_us_32')
        self.version.write({
            'wage': 3500,
            'schedule_pay': 'monthly',
        })
        self.employee.write({
            'l10n_us_filing_status': 'single',
            'l10n_us_state_filing_status': 'or_status_1',
        })

        payslip = self._generate_payslip(datetime.date(2025, 4, 1), datetime.date(2025, 4, 30))
        payslip.compute_sheet()

        payslip_results = {
            'BASIC': 3500.0,
            'GROSS': 3500.0,
            'TAXABLE': 3500.0,
            'FIT': -250.13,
            'MEDICARE': -50.75,
            'MEDICAREADD': 0.0,
            'SST': -217.0,
            'ORINCOMETAX': -259.17,
            'ORTRANSITTAX': -3.5,
            'ORWBF': -1.76,
            'ORFMLI': -21.0,
            'COMPANYFUTA': 210.0,
            'COMPANYMEDICARE': 50.75,
            'COMPANYSOCIAL': 217.0,
            'COMPANYSUI': 73.5,
            'COMPANYORWBF': 1.76,
            'COMPANYORFMLI': 14.0,
            'NET': 2696.69,
        }
        self._validate_payslip(payslip, payslip_results)
