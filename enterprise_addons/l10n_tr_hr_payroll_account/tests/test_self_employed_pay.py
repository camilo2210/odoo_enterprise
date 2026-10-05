# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestSelfEmployedPayslipValidation(TestPayslipValidationCommon):

    @classmethod
    @TestPayslipValidationCommon.setup_country('tr')
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_common(
            country=cls.env.ref('base.tr'),
            structure=cls.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_type_self_employed_tr'),
            structure_type=cls.env.ref('l10n_tr_hr_payroll.structure_type_self_employed_tr'),
            version_fields={
                'wage': 50000,
                'l10n_tr_is_net_to_gross': False,
                'contract_date_start': date(2026, 1, 1),
            },
        )

        cls.self_employed_pay_structure = cls.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_type_self_employed_tr')

    def test_self_employed_payslip(self):
        # Create an self-employed pay entry
        self_employed_payslip = self._generate_payslip(date(2026, 9, 1), date(2026, 9, 30), self.self_employed_pay_structure.id)
        self_employed_payslip.compute_sheet()
        expected_payslip_results = {'YTDGROSS': 0, 'ACTD': 0, 'BASIC': 50000, 'GROSS': 50000, 'CURTAXABLE': 50000, 'TAXB': 50000, 'TOTTB': 7500, 'BTAXNET': 7500, 'BTNET': -2545.5, 'STAX': -166.41, 'NETTAX': -2711.91, 'EXPNET': 47288.09, 'FDALW': 0, 'NET': 47288.09}
        self._validate_payslip(self_employed_payslip, expected_payslip_results)
        self_employed_payslip.action_payslip_done()
        self.assertEqual(self_employed_payslip.state, 'validated', "Payslip was not validated successfully.")
