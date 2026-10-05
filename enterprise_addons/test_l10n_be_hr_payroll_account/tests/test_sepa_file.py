# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


@tagged('post_install', '-at_install', 'sepa_file')
class TestSEPAFile(AccountTestInvoicingCommon, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].write({
            'iso20022_orgid_id': "123456789",
        })
        cls.company_data['company'].current_payroll_config_id.write({
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
        })

        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account') \
                                | cls.env.ref('hr.group_hr_user') \
                                | cls.env.ref('hr_payroll.group_hr_payroll_manager')

        cls.address_home = cls.env['res.partner'].create([{
            'name': "Test Employee",
            'company_id': cls.env.company.id,
        }])

        cls.company_bank_account = cls.env['res.partner.bank'].create({
            'account_number': "BE15001559627230",
            'bank_name': 'BNP Paribas',
            'bank_bic': 'GEBABEBB',
            'partner_id': cls.env.company.partner_id.id,
            'company_id': cls.env.company.id,
        })

        cls.bank_journal = cls.env['account.journal'].search([
            ('name', 'ilike', 'Bank'),
            ('company_id', '=', cls.env.company.id),
        ])

        cls.bank_journal.bank_account_id = cls.company_bank_account

        cls.sepa_payment_method_line = cls.bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.code == 'sepa_ct',
        )[:1]

        cls.bank_account = cls.env['res.partner.bank'].create({
            'account_number': "BE53485391778653",
            'bank_name': 'ING',
            'bank_bic': 'BBRUBEBB',
            'partner_id': cls.address_home.id,
            'company_id': cls.env.company.id,
        })

        cls.employee = cls.env['hr.employee'].sudo().create({
            'name': "Test Employee",
            'work_contact_id': cls.address_home.id,
            'bank_account_ids': [Command.link(cls.bank_account.id)],
            'resource_calendar_id': cls.company.resource_calendar_id.id,
            'company_id': cls.env.company.id,
            'distance_home_work': 75,
            'private_country_id': cls.env.ref('base.be').id,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date(2018, 12, 31),
            'contract_date_start': date(2018, 12, 31),
            'wage': 2400,
            'lang': 'fr_BE',
        }).sudo(False)

    def _create_validated_payslip_run(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2023-01-01',
            'date_end': '2023-01-31',
            'name': 'January Batch',
            'company_id': self.company.id,
            'structure_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        })
        self.employee.action_toggle_primary_bank_account_trust()
        payslip_run._generate_payslips()
        payslip_run.action_validate()
        return payslip_run

    def test_sepa_file_std(self):
        payslip_run = self._create_validated_payslip_run()
        sepa_wizard = self.env['hr.payroll.payment.report.wizard'].with_company(self.company).create({
            'payslip_ids': payslip_run.slip_ids.ids,
            'payslip_run_id': payslip_run.id,
            'export_format': 'sepa',
            'sepa_priority': 'std',
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })
        sepa_wizard.generate_payment_report()
        sepa_file_content = payslip_run.payment_report.decode()

        self.assertTrue('<InstrPrty>NORM</InstrPrty>' in sepa_file_content)
        self.assertTrue('<PmtMtd>TRF</PmtMtd>' in sepa_file_content)
        self.assertTrue("<Cd>SALA</Cd>" in sepa_file_content)
        self.assertTrue(f"<Ustrd>/A/ {payslip_run.slip_ids.id}" in sepa_file_content)
        self.assertTrue(f"<Ustrd>{payslip_run.slip_ids.id}" not in sepa_file_content)

    def test_sepa_file_high(self):
        payslip_run = self._create_validated_payslip_run()
        sepa_wizard = self.env['hr.payroll.payment.report.wizard'].with_company(self.company).create({
            'payslip_ids': payslip_run.slip_ids.ids,
            'payslip_run_id': payslip_run.id,
            'export_format': 'sepa',
            'sepa_priority': 'high',
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })
        sepa_wizard.generate_payment_report()
        sepa_file_content = payslip_run.payment_report.decode()

        self.assertTrue('<InstrPrty>HIGH</InstrPrty>' in sepa_file_content)
        self.assertTrue('<PmtMtd>TRF</PmtMtd>' in sepa_file_content)
        self.assertTrue("<Cd>SALA</Cd>" in sepa_file_content)
        self.assertTrue(f"<Ustrd>/A/ {payslip_run.slip_ids.id}" in sepa_file_content)
        self.assertTrue(f"<Ustrd>{payslip_run.slip_ids.id}" not in sepa_file_content)

    def test_sepa_file_sct(self):
        payslip_run = self._create_validated_payslip_run()
        sepa_wizard = self.env['hr.payroll.payment.report.wizard'].with_company(self.company).create({
            'payslip_ids': payslip_run.slip_ids.ids,
            'payslip_run_id': payslip_run.id,
            'export_format': 'sepa',
            'sepa_priority': 'sct',
            'payment_method_line_id': self.sepa_payment_method_line.id,
        })
        sepa_wizard.generate_payment_report()
        sepa_file_content = payslip_run.payment_report.decode()

        self.assertTrue('<InstrPrty>HIGH</InstrPrty>' in sepa_file_content)
        self.assertTrue('<PmtMtd>INST</PmtMtd>' in sepa_file_content)
        self.assertTrue("<Cd>SALA</Cd>" in sepa_file_content)
        self.assertTrue(f"<Ustrd>/A/ {payslip_run.slip_ids.id}" in sepa_file_content)
        self.assertTrue(f"<Ustrd>{payslip_run.slip_ids.id}" not in sepa_file_content)
