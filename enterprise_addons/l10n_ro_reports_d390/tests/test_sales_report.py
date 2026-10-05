import json
from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import file_open
from odoo.tools.misc import NON_BREAKING_SPACE

from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class RomanianSalesReportTest(AccountSalesReportCommon):
    @classmethod
    @AccountSalesReportCommon.setup_country('ro')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_b.update({
            'country_id': cls.env.ref('base.be').id,
            'vat': "BE0477472701",
        })
        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.ro').id,
            'vat': 'RO65379',
            'account_opening_date': fields.Date.from_string('2025-01-01')
        })

        cls.l_tax = cls.env.ref(f'account.{cls.env.company.id}_tvati_intrab')
        cls.t_tax = cls.env.ref(f'account.{cls.env.company.id}_tvati_intrat')
        cls.p_tax = cls.env.ref(f'account.{cls.env.company.id}_tvati_intras')
        cls.a_21_tax = cls.env.ref(f'account.{cls.env.company.id}_tvati_intrap21b')
        cls.s_21_tax = cls.env.ref(f'account.{cls.env.company.id}_tvati_intrap21s')

        cls.report = cls.env.ref('l10n_ro_reports_d390.romanian_ec_sales_report')
        cls.return_type = cls.env.ref('l10n_ro_reports_d390.ro_ec_sales_list_return_type')
        cls.L10n_RoEcSalesReportHandler = cls.env[cls.report.custom_handler_model_name]

    def _create_l10n_ro_invoices(self, data):
        move_vals_list = []
        for partner, tax, price_unit, date, move_type in data:
            move_vals_list.append({
                'move_type': move_type,
                'partner_id': partner.id,
                'invoice_date': fields.Date.from_string(date),
                'invoice_line_ids': [
                    Command.create({
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(tax.ids)],
                    }),
                ],
            })
        moves = self.env['account.move'].create(move_vals_list)
        moves.action_post()

    def _get_ro_ec_sales_list_return(self, date_from, date_to, **kw):
        wizard = self.env['account.return.creation.wizard'].create([{
            'date_from': date_from,
            'date_to': date_to,
            'return_type_id': self.return_type.id,
            **kw,
        }])
        wizard.action_create_manual_account_returns()

        return self.env['account.return'].search([('type_id', '=', self.return_type.id)], limit=1)

    @freeze_time('2025-10-31')
    def test_l10n_ro_generate_regular_d390_report(self):
        self._create_l10n_ro_invoices([
            (self.partner_a, self.l_tax, 400, '2025-10-15', 'out_invoice'),
            (self.partner_a, self.t_tax, 900, '2025-10-17', 'out_invoice'),
            (self.partner_b, self.p_tax, 500, '2025-10-17', 'out_invoice'),
            (self.partner_b, self.p_tax, 300, '2025-10-18', 'out_refund'),
            (self.partner_a, self.s_21_tax, 700, '2025-10-19', 'in_invoice'),
            (self.partner_b, self.a_21_tax, 600, '2025-10-20', 'in_invoice'),
            (self.partner_a, self.s_21_tax, 300, '2025-10-20', 'in_refund'),
        ])

        return_record = self._get_ro_ec_sales_list_return('2025-10-01', '2025-10-31')
        options = self.report.get_options({'date': {'default_opening_date': 'this_month'}})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Partner               country code,           VAT Number,             Tax  Amount
            [   0,                    1,                      2,                      3,   4],
            [
                ('EC Sales Report',   '',                     '',                     '',  f'500.00{NON_BREAKING_SPACE}lei'),
                (self.partner_a.name, self.partner_a.vat[:2], self.partner_a.vat[2:], 'L', f'400.00{NON_BREAKING_SPACE}lei'),
                (self.partner_a.name, self.partner_a.vat[:2], self.partner_a.vat[2:], 'S', f'-400.00{NON_BREAKING_SPACE}lei'),
                (self.partner_a.name, self.partner_a.vat[:2], self.partner_a.vat[2:], 'T', f'900.00{NON_BREAKING_SPACE}lei'),
                (self.partner_b.name, self.partner_b.vat[:2], self.partner_b.vat[2:], 'A', f'-600.00{NON_BREAKING_SPACE}lei'),
                (self.partner_b.name, self.partner_b.vat[:2], self.partner_b.vat[2:], 'P', f'200.00{NON_BREAKING_SPACE}lei'),
            ],
            options,
        )

        options.update({'return_id': return_record.id})
        # Expect UserError because declarantion information (like: 'First Name', 'Middle Name', 'Job Position') are missing in return_record
        with self.assertRaises(UserError):
            self.L10n_RoEcSalesReportHandler.export_to_xml_sales_report(options)['file_content']

        # Add the necessary details in return
        return_record.write({
            'l10n_ro_declarant_surname': 'Marc',
            'l10n_ro_declarant_name': 'Demo',
            'l10n_ro_declarant_role': 'Accountant',
            'l10n_ro_fiscal_address': 'Some Street 12, Bucharest',
            'l10n_ro_fax': '+40 21 220 3063',
        })

        # Now, the XML generation should work fine
        generated_xml = self.L10n_RoEcSalesReportHandler.export_to_xml_sales_report(options)['file_content']
        self.assertTrue(generated_xml)

        with file_open("l10n_ro_reports_d390/tests/mock_xmls/expected_d390_regular_return.xml", "rt") as f:
            expected_xml = self.get_xml_tree_from_string(f.read().encode())
        self.assertXmlTreeEqual(self.get_xml_tree_from_string(generated_xml), expected_xml)

    @freeze_time('2025-10-31')
    def test_l10n_ro_d390_report_with_no_operations(self):
        options = self.report.get_options({'date': {'default_opening_date': 'this_month'}})
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Partner               country code,           VAT Number,             Tax  Amount
            [   0,                    1,                      2,                      3,   4],
            [
                ('EC Sales Report',   '',                     '',                     '',  f'0.00{NON_BREAKING_SPACE}lei'),
            ],
            options,
        )

        return_with_no_op = self._get_ro_ec_sales_list_return('2025-10-01', '2025-10-31')
        # validating the return with no operations should raise UserError
        return_with_no_op.check_ids.result = 'reviewed'
        with self.assertRaises(UserError):
            return_with_no_op.action_validate()

    @freeze_time('2025-10-31')
    def test_l10n_ro_d390_report_modification_in_declaration(self):
        """
            Test that modifications in the return declaration are correctly handled in the Romanian EC Sales List D390 report.
            The test covers the following flow:
                1. On return validate action, Romanian EC Sales Report Generation Wizard will open first.
                2. In which user have to fill declarantion information (we ask for the return being correction or not at this stage).
                3. The collected data from that wizard will be saved on respective return and will be fetched in D390 XML report generator.
                4. The 'Download XML (D390)' action will download the generated D390 XML report and proceed with locking the return.
        """
        self._create_l10n_ro_invoices([
            (self.partner_a, self.l_tax, 1400, '2025-10-15', 'out_invoice'),
            (self.partner_b, self.p_tax, 330, '2025-10-17', 'out_invoice'),
        ])

        return_record = self._get_ro_ec_sales_list_return('2025-10-01', '2025-10-31')

        # validate the return
        return_record.check_ids.result = 'reviewed'
        with self.allow_pdf_render():
            action_generate_report = return_record.action_validate()
            generate_wizard = self.env[action_generate_report['res_model']].browse(action_generate_report['res_id'])
            generate_wizard.write({
                'l10n_ro_declarant_surname': 'Marc',
                'l10n_ro_declarant_name': 'Demo',
                'l10n_ro_declarant_role': 'Accountant',
                'l10n_ro_fiscal_address': 'Some Street 12, Bucharest',
                'l10n_ro_d390_corrective_declaration': True,  # indicate that this is a corrective declaration
            })
            # Romanian EC Sales List D390 XML report generation action
            action_report_download = generate_wizard.generate_xml()

        options_from_generation_wizard = json.loads(action_report_download.get('data', {}).get('options') or '{}')
        generated_xml = self.L10n_RoEcSalesReportHandler.export_to_xml_sales_report(options_from_generation_wizard)['file_content']
        self.assertTrue(generated_xml)

        self.assertEqual(return_record.state, 'reviewed')

        with file_open("l10n_ro_reports_d390/tests/mock_xmls/expected_d390_modified_return.xml", "rt") as f:
            expected_xml = self.get_xml_tree_from_string(f.read().encode())
        self.assertXmlTreeEqual(self.get_xml_tree_from_string(generated_xml), expected_xml)

        # proceed with submission
        with self.allow_pdf_render():
            action_submission_wizard = return_record.action_submit()
            submission_wizard = self.env[action_submission_wizard['res_model']].browse(action_submission_wizard['res_id'])
            submission_wizard.action_proceed_with_submission()
            self.assertTrue(return_record.is_completed)
