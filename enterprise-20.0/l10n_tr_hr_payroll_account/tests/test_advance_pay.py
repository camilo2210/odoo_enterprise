# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests.common import tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestAdvancePayslipValidation(TestPayslipValidationCommon):

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
            },
        )

        cls.input_advance_recovery_rule_id = cls.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary_salary_advance_recovery')
        cls.input_salary_advance_rule_id = cls.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_salary_advance')
        cls.sick_leave_adv_rule_id = cls.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_sick_leave')
        cls.annual_leave_adv_rule_id = cls.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay_annual_leave')

        cls.advance_pay_structure = cls.env.ref('l10n_tr_hr_payroll.l10n_tr_advance_pay')

    def test_advance_pay_payslip(self):
        # Create an advance pay entry
        advance_payslip = self._generate_payslip(date(2024, 1, 1), date(2024, 1, 31), self.advance_pay_structure.id)

        self.assertEqual(self._get_payslip_property_amount(advance_payslip, self.input_salary_advance_rule_id.code), 0)
        self.assertEqual(self._get_payslip_property_amount(advance_payslip, self.sick_leave_adv_rule_id.code), 0)
        self.assertEqual(self._get_payslip_property_amount(advance_payslip, self.annual_leave_adv_rule_id.code), 0)

        advance_payslip._set_input_value(self.input_salary_advance_rule_id.code, 500)

        advance_payslip.compute_sheet()
        payslip_results = {'SALARYADV': 500, 'NET': 500}
        self._validate_payslip(advance_payslip, payslip_results)
        advance_payslip.action_payslip_done()

        payslip1 = self._generate_payslip(date(2024, 2, 1), date(2024, 2, 29))
        payslip1._compute_input_line_ids()
        self.assertEqual(self._get_payslip_property_amount(payslip1, self.input_advance_recovery_rule_id.code), 500)
        payslip1._set_input_value(self.input_advance_recovery_rule_id.code, 300)
        payslip1.compute_sheet()
        self._validate_payslip(payslip1, {'SALARYADVREC': 300}, skip_lines=True)
        payslip1.action_payslip_done()

        payslip2 = self._generate_payslip(date(2024, 3, 1), date(2024, 3, 31))
        payslip2._compute_input_line_ids()
        self.assertEqual(self._get_payslip_property_amount(payslip2, self.input_advance_recovery_rule_id.code), 200)
        payslip2.compute_sheet()
        self._validate_payslip(payslip2, {'SALARYADVREC': 200}, skip_lines=True)
        payslip2.action_payslip_done()

        payslip3 = self._generate_payslip(date(2024, 4, 1), date(2024, 4, 30))
        payslip3._compute_input_line_ids()
        self.assertEqual(self._get_payslip_property_amount(payslip3, self.input_advance_recovery_rule_id.code), 0)
        payslip3.compute_sheet()
        self.assertNotIn('SALARYADVREC', payslip3.line_ids.mapped('code'))
