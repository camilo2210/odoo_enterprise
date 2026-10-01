
from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_payslip_with_dmfa_languages')
class TestPayrollPayslipWithDmfaLanguages(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a L10n_BeDmfaLocationUnit
        working_address = cls.env['res.partner'].create({'name': 'Working Address'})
        # Activate French and Dutch
        cls.env['res.lang']._activate_lang('fr_BE')
        cls.env['res.lang']._activate_lang('nl_BE')

        cls.env['hr.work.location'].create({
            'bce_code': '8888887654',
            'location_type': 'dmfa_unit',
            'company_id': cls.belgian_company.id,
            'address_id': working_address.id,
        })

        cls.employee_georges.address_id = working_address.id
        cls.env.user.lang = 'en_US'

    def test_payslip_with_dmfa_languages(self):
        Payslip = self.env['hr.payslip']
        payslip = Payslip.create({
            'name': "Payslip",
            'employee_id': self.employee_georges.id,
            'version_id': self.employee_georges.version_id.id,
        })

        french_lang = self.env['res.lang'].search([('code', '=', 'fr_BE')], limit=1)
        dutch_lang = self.env['res.lang'].search([('code', '=', 'nl_BE')], limit=1)
        english_lang = self.env['res.lang'].search([('code', '=', 'en_US')], limit=1)

        self.employee_georges.lang = english_lang.code
        dmfa_location_unit = self.env["hr.work.location"].search(
            [("address_id", "=", self.employee_georges.address_id.id), ("location_type", "=", "dmfa_unit")], limit=1)
        dmfa_location_unit.payslip_language_id = english_lang.id

        # -------- CASE 1 --------
        # en_US → expect (en_US, None)
        lang_map = payslip._get_payslips_pdf_lang()
        main, secondary = lang_map[payslip]
        self.assertEqual(main, 'en_US')
        self.assertIsNone(secondary)

        # -------- CASE 2 --------
        # fr_BE → expect (fr_BE, en_US)
        dmfa_location_unit.payslip_language_id = french_lang.id

        self.env.invalidate_all()
        payslip = Payslip.browse(payslip.id)
        lang_map = payslip._get_payslips_pdf_lang()
        main, secondary = lang_map[payslip]
        self.assertEqual(main, 'fr_BE')
        self.assertEqual(secondary, 'en_US')

        # -------- CASE 3 --------
        # nl_BE → expect (nl_BE, en_US)
        dmfa_location_unit.payslip_language_id = dutch_lang.id

        self.env.invalidate_all()
        payslip = Payslip.browse(payslip.id)
        lang_map = payslip._get_payslips_pdf_lang()
        main, secondary = lang_map[payslip]
        self.assertEqual(main, 'nl_BE')
        self.assertEqual(secondary, 'en_US')
