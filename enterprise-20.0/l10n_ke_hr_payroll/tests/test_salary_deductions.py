# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestKeSalaryDeductions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_ke = cls.env['res.company'].create({
            'name': 'KE Test Co',
            'country_id': cls.env.ref('base.ke').id,
        })
        cls.employee = cls.env['hr.employee'].with_company(cls.company_ke).create({
            'name': 'KE Test Employee',
            'company_id': cls.company_ke.id,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'wage': 100000,
        })

    def test_stopping_nssf_deductions_after_60(self):
        """After a month of being 60 years-old, the NSSF Tier 1-2 deductions should stop"""

        # Test-1: 60 years is okay and the payslip is in the next month (in March), no further NSSF deduction
        self.employee.write({
            'birthday': '1966-02-28',
            'l10n_ke_is_secondary': False,
        })
        payslip = self.env['hr.payslip'].with_company(self.company_ke).create({
            'name': 'Test Payslip',
            'employee_id': self.employee.id,
            'date_from': date(2026, 3, 18),
            'date_to': date(2026, 4, 17),
        })
        payslip.compute_sheet()
        NSSF_tier_line_ids = payslip.line_ids.filtered(lambda l: l.code in ['NSSF_EMPLOYEE_TIER_1', 'NSSF_EMPLOYEE_TIER_2', 'NSSF_AMOUNT', 'NSSF_EMP'])
        self.assertFalse(NSSF_tier_line_ids)

        # Test-2: 60 years is okay but the deduction stop will be start from April, (it is deducted in March payslips)
        self.employee.write({'birthday': '1966-03-10'})

        payslip.compute_sheet()
        codes = payslip.line_ids.mapped('code')
        self.assertIn('NSSF_EMPLOYEE_TIER_1', codes)
        self.assertIn('NSSF_EMPLOYEE_TIER_2', codes)
        self.assertIn('NSSF_AMOUNT', codes)
        self.assertIn('NSSF_EMP', codes)
