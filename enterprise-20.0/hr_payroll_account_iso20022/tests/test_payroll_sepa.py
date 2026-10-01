# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo import Command
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests.common import test_xsd
from odoo.tests import tagged


class TestPayrollSEPACreditTransferCommon(TestPayslipBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.currency_id = cls.env.ref('base.USD')
        cls.env.user.company_id.write({
            'iso20022_orgid_id': "0468651441",
            'country_id': cls.env.ref('base.us').id,
        })

        cls.work_contact = cls.env['res.partner'].create({
            'name': 'Richard Parker',
            'email': 'richard@example.com',
            'country_id': cls.env.ref('base.us').id,
        })
        cls.richard_emp.work_contact_id = cls.work_contact

        cls.res_partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'BE32707171912447',
            'partner_id': cls.work_contact.id,
            'bank_name': 'BNP',
            'bank_bic': 'GEBABEBB',
        })

        cls.bank_partner = cls.env['res.partner.bank'].create({
            'account_number': 'BE84567968814145',
            'partner_id': cls.company_us.partner_id.id,
            'bank_name': 'BNP',
            'bank_bic': 'GEBABEBB',
        })

        cls.richard_emp.bank_account_ids = [Command.link(cls.res_partner_bank.id)]

        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Bank',
            'code': 'BNK',
            'type': 'bank',
            'bank_account_id': cls.bank_partner.id,
        })
        cls.sepa_payment_method_line = cls.bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.code == 'sepa_ct',
        )[:1]
        cls.sepa_payment_method_line.sepa_pain_version = 'pain.001.001.09'

        cls.payroll_structure = cls.env['hr.payroll.structure'].create({
            'name': 'Monthly Salary - Test',
            'type_id': cls.structure_type.id,
        })

        cls.payslip_run = cls.env['hr.payslip.run'].create({
            'name': 'November Payroll',
            'date_start': '2025-11-01',
            'date_end': '2025-11-30',
            'structure_id': cls.payroll_structure.id,
        })

        cls.hr_payslip_richard = cls.env['hr.payslip'].create({
            'name': 'Payslip - Richard',
            'employee_id': cls.richard_emp.id,
            'struct_id': cls.payroll_structure.id,
            'date_from': '2025-11-01',
            'date_to': '2025-11-30',
        })


@tagged('post_install', '-at_install')
class TestPayrollSEPACreditTransfer(TestPayrollSEPACreditTransferCommon):
    def test_00_hr_payroll_account_iso20022(self):
        """ Checking the process of payslip when you create a SEPA payment. """

        # I verify if the payslip has not already a payslip run.
        self.assertFalse(self.hr_payslip_richard.payslip_run_id, 'There is already a payslip run!')

        # I validate the payslip.
        self.hr_payslip_richard.action_payslip_done()

        # I verify the payslip is in validated state.
        self.assertEqual(self.hr_payslip_richard.state, 'validated', 'State not changed!')

        # I make the SEPA payment.
        file = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.hr_payslip_richard.ids,
            'export_format': 'sepa',
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })._create_sepa_binary()

        # I verify if a file is created.
        self.assertTrue(file, 'SEPA payment has not been created!')

        # I verify the payslip is in validated state.
        self.assertEqual(self.hr_payslip_richard.state, 'validated')

    def test_01_hr_payroll_account_iso20022(self):
        """ Checking the process of payslip run when you create a SEPA payment. """
        # I verify the payslip run is in draft state.
        self.assertEqual(self.payslip_run.state, '00_draft', 'State not changed!')

        # I create a payslip employee.
        self.payslip_run._generate_payslips()
        self.assertEqual(self.payslip_run.state, '01_ready', 'Pay Run has draft payslips')

        # I verify if the payslip run has payslip(s).
        self.assertTrue(len(self.payslip_run.slip_ids) > 0, 'Payslip(s) not added!')

        # I confirm the payslip run.
        self.payslip_run.action_validate()

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, '02_close', 'State not changed!')

        # I make the SEPA payment.
        file = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.payslip_run.slip_ids.ids,
            'payslip_run_id': self.payslip_run.id,
            'export_format': 'sepa',
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })._create_sepa_binary()

        # I verify if a file is created for the payslip run.
        self.assertTrue(file, 'SEPA payment has not been created!')

        # I verify the payslip is in paid state.
        self.assertEqual(self.payslip_run.state, '02_close')

    def test_02_hr_payroll_account_iso20022_ch(self):
        self.assertEqual(self.payslip_run.state, '00_draft')

        # I create a payslip employee.
        self.payslip_run._generate_payslips()
        self.assertEqual(self.payslip_run.state, '01_ready', 'Pay Run has draft payslips')

        self.assertTrue(len(self.payslip_run.slip_ids) > 0)

        self.payslip_run.action_validate()

        self.assertEqual(self.payslip_run.state, '02_close')

        file = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.payslip_run.slip_ids.ids,
            'payslip_run_id': self.payslip_run.id,
            'export_format': 'iso20022_ch',
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })._create_sepa_binary()

        self.assertTrue(file)
        self.assertEqual(self.payslip_run.state, '02_close')

    def test_sepa_export_multi_bank_account_instr_id_uniqueness(self):
        """ Test that a payslip split across multiple bank accounts generates unique SEPA InstrId (slip.id-bank_account.id) """

        other_partner_bank = self.env['res.partner.bank'].create({
            'account_number': 'BE32707171912490',
            'partner_id': self.work_contact.id,
            'bank_name': 'BNP',
            'bank_bic': 'OTHERBANK',
        })

        self.richard_emp.bank_account_ids = [Command.link(other_partner_bank.id)]
        self.richard_emp.write({
            'bank_account_ids': [Command.link(other_partner_bank.id)],
            'salary_distribution': {
                str(self.res_partner_bank.id): {'sequence': 1, 'amount': 50.0, 'amount_is_percentage': True},
                str(other_partner_bank.id): {'sequence': 2, 'amount': 50.0, 'amount_is_percentage': True},
            }
        })

        self.payslip_run._generate_payslips()
        self.payslip_run.action_validate()
        file = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.payslip_run.slip_ids.ids,
            'payslip_run_id': self.payslip_run.id,
            'export_format': 'sepa',
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })._create_sepa_binary()

        self.assertTrue(file)
        xml_content = file.decode('utf-8')

        payslip = self.payslip_run.slip_ids
        self.assertEqual(len(payslip), 1)

        expected_id_1 = f'<InstrId>{payslip.id}-{self.res_partner_bank.id}</InstrId>'
        expected_id_2 = f'<InstrId>{payslip.id}-{other_partner_bank.id}</InstrId>'

        self.assertIn(expected_id_1, xml_content, f'Missing unique InstrId: {expected_id_1}')
        self.assertIn(expected_id_2, xml_content, f'Missing unique InstrId: {expected_id_2}')


@tagged('external_l10n', 'post_install', '-at_install', '-standard')
class TestPayrollSEPACreditTransferXmlValidity(TestPayrollSEPACreditTransferCommon):

    @test_xsd(path='account_sepa/schemas/pain.001.001.03.xsd')
    def test_00_hr_payroll_account_iso20022(self):
        """ Checking the process of payslip when you create a SEPA payment. """

        self.hr_payslip_richard.action_payslip_done()
        file = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.hr_payslip_richard.ids,
            'payslip_run_id': self.hr_payslip_richard.payslip_run_id.id,
            'export_format': 'sepa',
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })._create_sepa_binary()
        return etree.fromstring(file)

    @test_xsd(path='account_sepa/schemas/pain.001.001.03.xsd')
    def test_01_hr_payroll_account_iso20022(self):
        """ Checking the process of payslip run when you create a SEPA payment. """

        self.payslip_run._generate_payslips()
        self.payslip_run.action_validate()
        file = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.payslip_run.slip_ids.ids,
            'payslip_run_id': self.payslip_run.id,
            'export_format': 'sepa',
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })._create_sepa_binary()

        return etree.fromstring(file)
