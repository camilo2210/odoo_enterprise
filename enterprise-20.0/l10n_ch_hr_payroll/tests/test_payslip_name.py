from odoo import fields
from odoo.tests.common import tagged

from .common import TestSwissdecCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayslipName(TestSwissdecCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ch_company = cls.env['res.company'].create({
            'name': "CH Company",
            'country_id': cls.env.ref('base.ch').id,
        })

        cls.ch_employee = cls.env['hr.employee'].create({
            'name': "Test",
            'company_id': cls.ch_company.id,
        })

        cls.ch_contract = cls.ch_employee.create_version({
            'contract_date_start': fields.Date.today(),
            'contract_date_end': False,
            'date_version': fields.Date.today(),
        })

    def test_employee_legal_name_on_payslip(self):
        payslip = self._l10n_ch_generate_swissdec_demo_payslip(
            self.ch_contract,
            fields.Date.today(),
            fields.Date.today(),
            self.ch_company.id,
        )
        self.ch_employee.write({
            'l10n_ch_legal_first_name': "First",
            'l10n_ch_legal_last_name': "Last",
        })
        self.assertEqual(self.ch_employee.legal_name, "First Last")
        self.assertIn("First Last", payslip.name)

        self.ch_employee.write({
            'l10n_ch_legal_first_name': "NewFirst",
        })
        self.assertEqual(self.ch_employee.legal_name, "NewFirst Last")
        self.assertIn("NewFirst Last", payslip.name)

        self.ch_employee.write({
            'l10n_ch_legal_last_name': "NewLast",
        })
        self.assertEqual(self.ch_employee.legal_name, "NewFirst NewLast")
        self.assertIn("NewFirst NewLast", payslip.name)
