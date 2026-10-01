from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.hr_payroll.tests.common import TestPayrollBase
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'gift_vouchers')
class TestPayrollGiftVouchers(TestPayrollBase, TestBelgiumCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        resource_calendar = cls.env['resource.calendar'].create({
            'name': 'Test Calendar',
            'attendance_ids': [(5, 0, 0),
                (0, 0, {'dayofweek': '0', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 7.6, 'hour_from': 0, 'hour_to': 0}),
            ]
        })
        resource_calendar.reference_calendar_id = resource_calendar
        cls._setup_common(
            country=cls.env.ref('base.be'),
            structure=cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary'),
            structure_type=cls.env.ref('hr.structure_type_employee_cp200'),
            resource_calendar=resource_calendar,
            version_fields={
                'name': 'A',
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
                'wage': 3000.0,
                'l10n_be_worker_code_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
            }
        )

    @freeze_time('2025-01-25')
    def test_gift_voucher_no_onss_no_pp(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_value('GIFT_VOUCHER_NO_ONSS_NO_PP', 500.0)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 3000.0, 'DH_BASIC': 0.0, 'BONUS_SALARY': 0.0, 'EMP_BONUS_SALARY': 3000.0, 'SALARY': 3000.0, 'DH_SALARY': 0.0, 'ONSS_BASE_TOTAL': 3000.0, 'ONSS': -392.1, 'EmpBonus.A': 50.66, 'EmpBonus.B': 0.0, 'EmpBonus.1': 50.66, 'EmpBonus.1.STD': 50.66, 'EmpBonus.1.FALLBACK': 0.0, 'ONSS_DOUBLE_HOLIDAY': 0.0, 'ONSSTOTAL': 341.44, 'WITHHOLDING_BASE_TOTAL': 2658.56, 'DH_GROSS': 0.0, 'GROSS': 2658.56, 'GROSS.M': 2658.56, 'GROSS.Y': 31902.72, 'F_PROFESSIONAL_FEES': -5930.0, 'TRANSPORT_TAX_DED': 0.0, 'GROSS.NET.Y': 25972.72, 'Y.P.P': 8498.57, 'P.P.MARITAL.DED': -2915.75, 'P.P.FAMILY.DED': 0.0, 'P.P': -465.23, 'BONUS_PP': 0.0, 'DH_PP': 0.0, 'P.P.DED': 16.79, 'PPTOTAL': 448.44, 'M.ONSS': -19.24, 'GIFT_VOUCHER_NO_ONSS_NO_PP': 500.0, 'NET_TO_RECOVER': 0.0, 'NET': 2690.88, 'REMUNERATION': 3000.0, 'ONSSEMPLOYERBASIC': 750.0, 'ONSSEMPLOYER_255': 0.6, 'ONSSEMPLOYER_256': 0.3, 'ONSSEMPLOYER_809': 10.2, 'ONSSEMPLOYER_810': 3.0, 'ONSSEMPLOYER_831': 6.9, 'ONSSEMPLOYER_859': 3.0, 'ONSS_STRUCTURAL': -145.92, 'ONSSEMPLOYER': 628.08, 'HOLIDAY_TAX_PROV_BASE': 3000.0, 'HOLIDAY_TAX_PROV': 546.0, 'REP.FEES': 0.0, 'REP.FEES.VOLATILE': 0.0}
        self._validate_payslip(payslip, payslip_results)

    @freeze_time('2025-01-25')
    def test_gift_voucher_no_onss(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_value('GIFT_VOUCHER_NO_ONSS', 500.0)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 3000.0, 'DH_BASIC': 0.0, 'BONUS_SALARY': 0.0, 'EMP_BONUS_SALARY': 3000.0, 'SALARY': 3000.0, 'DH_SALARY': 0.0, 'ONSS_BASE_TOTAL': 3000.0, 'ONSS': -392.1, 'EmpBonus.A': 50.66, 'EmpBonus.B': 0.0, 'EmpBonus.1': 50.66, 'EmpBonus.1.STD': 50.66, 'EmpBonus.1.FALLBACK': 0.0, 'ONSS_DOUBLE_HOLIDAY': 0.0, 'ONSSTOTAL': 341.44, 'GIFT_VOUCHER_NO_ONSS': 500.0, 'WITHHOLDING_BASE_TOTAL': 3158.56, 'DH_GROSS': 0.0, 'GROSS': 3158.56, 'GROSS.M': 3158.56, 'GROSS.Y': 37902.72, 'F_PROFESSIONAL_FEES': -5930.0, 'TRANSPORT_TAX_DED': 0.0, 'GROSS.NET.Y': 31972.72, 'Y.P.P': 11236.84, 'P.P.MARITAL.DED': -2915.75, 'P.P.FAMILY.DED': 0.0, 'P.P': -693.42, 'BONUS_PP': 0.0, 'DH_PP': 0.0, 'P.P.DED': 16.79, 'PPTOTAL': 676.63, 'M.ONSS': -19.24, 'NET_TO_RECOVER': 0.0, 'NET': 2462.69, 'REMUNERATION': 3000.0, 'ONSSEMPLOYERBASIC': 750.0, 'ONSSEMPLOYER_255': 0.6, 'ONSSEMPLOYER_256': 0.3, 'ONSSEMPLOYER_809': 10.2, 'ONSSEMPLOYER_810': 3.0, 'ONSSEMPLOYER_831': 6.9, 'ONSSEMPLOYER_859': 3.0, 'ONSS_STRUCTURAL': -145.92, 'ONSSEMPLOYER': 628.08, 'HOLIDAY_TAX_PROV_BASE': 3000.0, 'HOLIDAY_TAX_PROV': 546.0, 'REP.FEES': 0.0, 'REP.FEES.VOLATILE': 0.0}
        self._validate_payslip(payslip, payslip_results)

    @freeze_time('2025-01-25')
    def test_gift_voucher_onss_pp(self):
        payslip = self._generate_payslip(date(2025, 1, 1), date(2025, 1, 31))
        payslip._set_input_value('GIFT_VOUCHER_ONSS_PP', 500.0)
        payslip.compute_sheet()
        payslip_results = {'BASIC': 3000.0, 'DH_BASIC': 0.0, 'GIFT_VOUCHER_ONSS_PP': 500.0, 'BONUS_SALARY': 0.0, 'EMP_BONUS_SALARY': 3500.0, 'SALARY': 3500.0, 'DH_SALARY': 0.0, 'ONSS_BASE_TOTAL': 3500.0, 'ONSS': -457.45, 'EmpBonus.1.STD': 0.0, 'EmpBonus.1.FALLBACK': 0.0, 'ONSS_DOUBLE_HOLIDAY': 0.0, 'ONSSTOTAL': 457.45, 'WITHHOLDING_BASE_TOTAL': 3042.55, 'DH_GROSS': 0.0, 'GROSS': 3042.55, 'GROSS.M': 3042.55, 'GROSS.Y': 36510.6, 'F_PROFESSIONAL_FEES': -5930.0, 'TRANSPORT_TAX_DED': 0.0, 'GROSS.NET.Y': 30580.6, 'Y.P.P': 10566.54, 'P.P.MARITAL.DED': -2915.75, 'P.P.FAMILY.DED': 0.0, 'P.P': -637.56, 'BONUS_PP': 0.0, 'DH_PP': 0.0, 'PPTOTAL': 637.56, 'M.ONSS': -24.74, 'NET_TO_RECOVER': 0.0, 'NET': 2380.25, 'REMUNERATION': 3000.0, 'ONSSEMPLOYERBASIC': 875.0, 'ONSSEMPLOYER_255': 0.7, 'ONSSEMPLOYER_256': 0.35, 'ONSSEMPLOYER_809': 11.9, 'ONSSEMPLOYER_810': 3.5, 'ONSSEMPLOYER_831': 8.05, 'ONSSEMPLOYER_859': 3.5, 'ONSS_STRUCTURAL': -64.1, 'ONSSEMPLOYER': 838.9, 'HOLIDAY_TAX_PROV_BASE': 3500.0, 'HOLIDAY_TAX_PROV': 637.0, 'REP.FEES': 0.0, 'REP.FEES.VOLATILE': 0.0}
        self._validate_payslip(payslip, payslip_results)
