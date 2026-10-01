# -*- coding: utf-8 -*-

from freezegun import freeze_time

from odoo.addons.l10n_es_reports.tests.common import TestEsAccountReportsCommon
from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger
from odoo.tests.common import new_test_user


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBOEGeneration(TestEsAccountReportsCommon):
    """ Basic tests checking the generation of BOE files is still possible.
    """
    _test_user_groups = None  # FIXME list needed groups

    def _check_boe_111_to_303(self, modelo_number):
        self.init_invoice('out_invoice', partner=self.spanish_partner, amounts=[10000], invoice_date=fields.Date.today(), taxes=self.spanish_test_tax, post=True)
        self._check_boe_export(modelo_number)

    @freeze_time('2020-12-22')
    def test_boe_mod_111(self):
        self._check_boe_111_to_303('111')

    @freeze_time('2020-12-22')
    def test_boe_mod_115(self):
        self._check_boe_111_to_303('115')

    @freeze_time('2020-12-22')
    def test_boe_mod_130(self):
        self._check_boe_111_to_303('130')

    @freeze_time('2020-12-22')
    def test_boe_mod_115_no_company_write_access_required(self):
        """
        Generating a mod 115 BOE file should not require write access on res.company.
        """
        self._create_invoice(
            partner_id=self.spanish_partner,
            invoice_date=fields.Date.today(),
            invoice_line_ids=[self._prepare_invoice_line(price_unit=10000, tax_ids=self.spanish_test_tax)],
            post=True,
        )

        accountant = new_test_user(self.env, login='accountant_no_settings_access', groups='account.group_account_user')
        self.assertFalse(accountant.has_group('base.group_erp_manager'), "Test user should not have write access on res.company")

        account_return = self.env['account.return'].with_user(accountant).create({
            'name': 'Tax Return',
            'type_id': self.env.ref('l10n_es_reports.es_mod115_tax_return_type').id,
            'company_id': self.env.company.id,
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })
        wizard = self.env['l10n_es_reports.mod115.submission.wizard'].with_user(accountant).create({
            'return_id': account_return.id,
            # Mimics the value the web client sends back on save, since the field is
            # present (albeit invisible) in the wizard view.
            'company_partner_id': self.env.company.partner_id.id,
        })
        with self.allow_pdf_render():
            account_return.with_user(accountant).action_submit()
            wizard.with_user(accountant).action_proceed_with_submission()

        boe_file = account_return.attachment_ids.filtered(lambda a: a.name.endswith(".txt"))
        self.assertTrue(boe_file.raw.size, "Empty BOE")

    @freeze_time('2020-12-22')
    def test_boe_mod_303(self):
        self._check_boe_111_to_303('303')

    @freeze_time('2020-12-22')
    def test_boe_mod_347(self):
        invoice = self.init_invoice('out_invoice', partner=self.spanish_partner, amounts=[10000], invoice_date=fields.Date.today())
        invoice.l10n_es_reports_mod347_invoice_type = 'regular'
        invoice._post()
        spanish_partner_2 = self.env['res.partner'].create({
            # ES Partner with vat not starting with 'ES', should still be included in 347
            'name': 'Partner 2',
            'street': "Avenida de los Informes Financieros, 43",
            'zip': 4242,
            'city': "Madrid",
            'country_id': self.env.ref('base.es').id,
            'state_id': self.env.ref('base.state_es_m').id,
            'vat': '74280274A',
        })
        invoice_2 = self.init_invoice('out_invoice', partner=spanish_partner_2, amounts=[5000], invoice_date=fields.Date.today())
        invoice_2.action_post()
        invoice_3 = self.init_invoice('out_invoice', partner=spanish_partner_2, amounts=[4000], invoice_date=fields.Date.today())
        invoice_3.l10n_es_reports_mod347_invoice_type = 'insurance'
        invoice_3._post()
        boe_file = self._check_boe_export(347)

        # Check file content
        expected = [
            # For information about data position, see page 7 & 16 of
            # https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos/347.pdf
            # 1,347,year,company vat
            "13472020A12345674COMPANY_1_DATA                          T         BECAUSE I AM ACCOUNTMAN!                3470000000001  0000000000000000000002 000000001900000000000000 000000000000000                                                                                                                                                                                                                                                                                                                           ",
            # 2,347,year,company vat,partner vat
            "23472020A1234567474280274A         PARTNER 2                               D28   B 000000000400000X 000000000000000 0000000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000400000 000000000000000                     000000000000000000000                                                                                                                                                                                                   ",
            "23472020A12345674A12345674         BERNARDO GANADOR                        D28   B 000000001000000  000000000000000 0000000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000001000000 000000000000000                     000000000000000000000                                                                                                                                                                                                   ",
            "23472020A1234567474280274A         PARTNER 2                               D28   B 000000000500000  000000000000000 0000000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000000000 000000000500000 000000000000000                     000000000000000000000                                                                                                                                                                                                   ",
        ]
        for generated_line, expected_line in zip(boe_file.raw.decode('utf-8').splitlines(), expected):
            self.assertEqual(generated_line, expected_line)

        boe_file = self._check_boe_export(
            347,
            wizard_values={
                'complementary_declaration': True,
                'substitutive_declaration': True,
            }
        )
        header_line = boe_file.raw.decode('utf-8').splitlines()[0]
        self.assertEqual('C', header_line[120], "Complementary declaration should use 'C'")
        self.assertEqual('S', header_line[121], "Substitutive declaration should use 'S'")

    @freeze_time('2020-12-22')
    def test_boe_mod_349(self):
        self.partner_a.write({
            'country_id': self.env.ref('base.be').id,
            'vat': "BE0477472701",
        })
        tax_eu_sale_e = self.env['account.tax'].search([
            ('name', '=', '0% EU S'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        invoice = self.init_invoice('out_invoice', partner=self.partner_a, amounts=[10000], taxes=tax_eu_sale_e, invoice_date=fields.Date.today())
        invoice._post()
        self._check_boe_export(349)

    @freeze_time('2020-12-22')
    def test_boe_mod_390(self):
        self._check_boe_export(390, additional_context={
            'default_physical_person_name': "Bernard Gagnant",
            'default_principal_activity': "Selling",
            'default_principal_iae_epigrafe': "EAAA",
            'default_principal_code_activity': "AAA",
            'default_judicial_person_name': "Bebert",
            'default_judicial_person_nif': "123",
            'default_judicial_person_procuration_date': '2020-01-01',
            'default_judicial_person_notary': "Maître Gagnant",
        })

    @freeze_time('2020-12-22')
    def test_boe_mod_347_with_cash_payment(self):
        cash_journal = self.env['account.journal'].create({
            'name': 'Cash Journal Test',
            'type': 'cash',
            'company_id': self.company_data['company'].id,
            'code': 'CASHBOE',
        })
        invoice = self.init_invoice('out_invoice', partner=self.spanish_partner, amounts=[1000], invoice_date=fields.Date.today())
        invoice.l10n_es_reports_mod347_invoice_type = 'regular'
        invoice._post()
        self.env['account.payment.register'].with_context(active_ids=invoice.ids, active_model='account.move').create({
            'amount': 1000,
            'payment_date': invoice.date,
            'journal_id': cash_journal.id,
        })._create_payments()

        other_spanish_partner = self.env['res.partner'].create({
            'name': "Other Partner",
            'state_id': self.env.ref('base.state_es_m').id,
            'country_id': self.env.ref('base.es').id,
            'vat': "ESA12345674",
        })
        other_invoice = self.init_invoice('out_invoice', partner=other_spanish_partner, amounts=[4000], invoice_date=fields.Date.today())
        other_invoice.l10n_es_reports_mod347_invoice_type = 'regular'
        other_invoice._post()
        self.env['account.payment.register'].with_context(active_ids=other_invoice.ids, active_model='account.move').create({
            'amount': 4000,
            'payment_date': other_invoice.date,
            'journal_id': cash_journal.id,
        })._create_payments()

        report = self.env.ref('l10n_es_reports.mod_347')
        options = self._generate_options(report, '2020-01-01', '2020-12-31')
        boe_file = self._get_report_boe(report, 347, options)

        self.assertTrue(self.spanish_partner.name.upper() not in boe_file['file_content'])
        # Only the other partner is above the 3 005,06 € threshold must be reported
        self.assertIn(other_spanish_partner.name.upper(), boe_file['file_content'])

    @freeze_time('2025-05-15')
    @mute_logger('odoo.addons.account.models.partner')
    def test_boe_includes_null_lines_mod_349(self):
        """
        Test that the mod 349 boe report contains the rectification lines even when the total rectification sum to 0
        """
        partner = self.env['res.partner'].create({
            'name': 'Test',
            'company_id': self.company_data['company'].id,
            'country_id': self.env['res.country'].search([('code', '=', 'BE')]).id,
            'vat': 'ESV77577963',
        })
        tax_eu_0_sale = self.env['account.tax'].search([
            ('name', '=', '0% EU S'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        invoice = self.init_invoice('out_invoice', partner=partner, amounts=[999999], invoice_date='2025-03-15', taxes=tax_eu_0_sale)
        invoice.action_post()

        credit_note_wizard = self.env['account.move.reversal'].with_context({
            'active_ids': invoice.id,
            'active_id': invoice.id,
            'active_model': 'account.move',
        }).create({
            'reason': 'modify',  # 'reason' can still be used to indicate purpose
            'journal_id': invoice.journal_id.id,
        })
        credit_note_wizard.modify_moves()

        report = self.env.ref('l10n_es_reports.mod_349')
        options = self._generate_options(report, '2025-05-01', '2025-05-31')
        boe_file = self._get_report_boe(report, 349, options)
        #  The original amount should be in the BOE file, even though it has been entirely refunded.
        self.assertIn('99999', boe_file['file_content'])

    @freeze_time('2025-05-15')
    @mute_logger('odoo.addons.account.models.partner')
    def test_only_include_credit_note_in_rectification_mod_349(self):
        """
        Test that in model 349 only the credit notes are included in the computation of the rectification line
        """
        partner = self.env['res.partner'].create({
            'name': 'Test',
            'company_id': self.company_data['company'].id,
            'country_id': self.env['res.country'].search([('code', '=', 'BE')]).id,
            'vat': 'ESV77577963',
        })
        tax_eu_0_sale = self.env['account.tax'].search([
            ('name', '=', '0% EU S'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        invoice = self.init_invoice('out_invoice', partner=partner, amounts=[99999], invoice_date='2025-03-15', taxes=tax_eu_0_sale)
        invoice.action_post()

        reversal_wizard = self.env['account.move.reversal'].with_context({
            'active_ids': invoice.id,
            'active_model': 'account.move',
        }).create({
            'reason': 'refund',
            'date': '2025-03-31',
            'journal_id': invoice.journal_id.id,
        })
        reversal = reversal_wizard.reverse_moves()
        refund = self.env['account.move'].browse(reversal.get('res_id'))
        refund.line_ids.write({'price_unit': 11111.0})
        refund.action_post()

        self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'amount': 22222.0,
        })._create_payments()

        report = self.env.ref('l10n_es_reports.mod_349')
        options = self._generate_options(report, '2025-03-01', '2025-03-31')
        boe_file = self._get_report_boe(report, 349, options)
        boe_file_content = boe_file['file_content']

        # The rectiffied value should be in the BOE file
        self.assertIn('88888', boe_file_content)
        # The non-rectified value should not be there
        self.assertNotIn('99999', boe_file_content)
        # Neither should the original value - the payment
        self.assertNotIn('77777', boe_file_content)
        # Nor the corrected value - the payment
        self.assertNotIn('66666', boe_file_content)

    @freeze_time('2025-05-15')
    @mute_logger('odoo.addons.account.models.partner')
    def test_boe_excludes_current_period_rectification_lines(self):
        """
        Test that moves from the current period are not included as rectification lines in the boe report
        """
        partner = self.env['res.partner'].create({
            'name': 'Test',
            'company_id': self.company_data['company'].id,
            'country_id': self.env['res.country'].search([('code', '=', 'BE')]).id,
            'vat': 'ESV77577963',
        })
        previous_period_invoice = self.init_invoice('out_invoice', partner=partner, amounts=[1000], invoice_date='2025-03-15')
        previous_period_invoice.action_post()

        credit_note_wizard_previous = self.env['account.move.reversal'].with_context({
            'active_ids': previous_period_invoice.id,
            'active_id': previous_period_invoice.id,
            'active_model': 'account.move',
        }).create({
            'reason': 'modify',
            'journal_id': previous_period_invoice.journal_id.id,
        })
        credit_note_wizard_previous.reverse_moves()

        current_period_invoice = self.init_invoice('out_invoice', partner=partner, amounts=[1000], invoice_date='2025-05-15')
        current_period_invoice.action_post()

        credit_note_wizard_current = self.env['account.move.reversal'].with_context({
            'active_ids': current_period_invoice.id,
            'active_id': current_period_invoice.id,
            'active_model': 'account.move',
        }).create({
            'reason': 'modify',
            'journal_id': current_period_invoice.journal_id.id,
        })
        credit_note_wizard_current.reverse_moves()

        report = self.env.ref('l10n_es_reports.mod_349')
        options = self._generate_options(report, '2025-05-01', '2025-05-31')
        boe_file = self._get_report_boe(report, 349, options)

        # This string represents a rectification record included in the BOE export.
        # It contains:
        # - the year (2025),
        # - the period (here 5 which is the current period),
        # - the rectified tax base (0.00),
        # - and the previously declared tax base (1000.00).
        # Under REGISTRO DE RECTIFICACIONES https://www.boe.es/buscar/doc.php?id=BOE-A-2010-5098
        self.assertNotIn('20250500000000000000000000100000', boe_file['file_content'])
