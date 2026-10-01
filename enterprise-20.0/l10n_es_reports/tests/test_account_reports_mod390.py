from odoo import Command
from odoo.tools import file_open
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAccountReportsModelo390(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('es')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].country_id = cls.env.ref('base.be').id
        cls.company_data['company'].currency_id = cls.env.ref('base.EUR').id
        cls.company_data['currency'] = cls.env.ref('base.EUR')

        cls.es_company = cls.env['res.company'].search([('partner_id.country_id.code', '=', 'ES')], limit=1)
        cls.es_company.name = 'ES COMPANY'
        cls.es_company.partner_id.vat = 'ESA12345674'
        cls.env.user.write({
            'company_ids': [Command.link(cls.es_company.id)],
        })

        cls.es_partner = cls.env['res.partner'].with_company(cls.es_company).create({
            'name': 'ES Partner',
            'company_id': cls.es_company.id,
            'country_id': cls.es_company.country_id.id,
        })

        cls.es_product = cls.env['product.product'].with_company(cls.es_company).create({
            'name': 'ES Product',
            'lst_price': 100.0
        })

        cls.tax_sale_21 = cls.env['account.tax'].search([
            ('name', '=', '21% G'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.es_company.id),
        ], limit=1)
        cls.tax_purchase_21 = cls.env['account.tax'].search([
            ('name', '=', '21% G'),
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', cls.es_company.id),
        ], limit=1)

        cls.report = cls.env.ref('l10n_es.mod_390')

    def _generate_mod_390_boe(self, year, wizard_context):
        account_return = self.env['account.return'].create({
            'name': 'Tax Return',
            'type_id': self.env.ref('l10n_es_reports.es_mod390_tax_return_type').id,
            'company_id': self.company.id,
            'date_from': f'{year}-01-01',
            'date_to': f'{year}-12-31',
        })
        context = wizard_context or {}
        wizard = self.env['l10n_es_reports.mod390.submission.wizard'].with_context(**context).create({
            'return_id': account_return.id
        })
        with self.allow_pdf_render():
            account_return.action_submit()
            wizard.action_proceed_with_submission()
        return account_return.attachment_ids.filtered(lambda a: a.name.endswith(".txt"))

    def _verify_mod_390_boe(self, boe_file, expected_content):
        """
        Verify the structure and full content based on an expected content String and a BOE file
        """
        boe_file_content = boe_file.raw.content.decode("ascii")
        # Copy odoo version from the BOE file to the expected content
        boe_file_version = boe_file_content[92:96]
        expected_content = expected_content[:92] + boe_file_version + expected_content[96:]
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(boe_file_content),
            self.get_xml_tree_from_string(expected_content)
        )
        self.assertEqual(boe_file_content, expected_content)

    def test_export_boe_mod_390_structure(self):
        """
        Ensure that the BOE export for Modelo 390 generates the expected XML
        structure and exact fixed-length content.

        There is no official offline validator provided by the Spanish tax
        authorities for Modelo 390. This test therefore acts as a golden-file
        regression test: any change in the generated output (including spaces
        and field positions) may invalidate the BOE file.

        The BOE file layout is strictly defined with fixed-length fields.
        The official field specifications can be found in the Spanish tax
        authorities documentation:
        https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_25/dr390e2025.xlsx
        """
        self.env.user.company_id = self.es_company

        wizard_context = {
            'default_physical_person_name': "Bernard Gagnant",
            'default_principal_activity': "Selling",
            'default_principal_iae_epigrafe': "EAAA",
            'default_principal_code_activity': "AAA",
            'default_judicial_person_name': "Bebert",
            'default_judicial_person_nif': "123",
            'default_judicial_person_procuration_date': '2020-01-01',
            'default_judicial_person_notary': "Maître Gagnant",
        }
        boe_file = self._generate_mod_390_boe(2020, wizard_context)

        expected_content = ''
        # The spaces are required to be exact to have a valid file
        with file_open('l10n_es_reports/tests/data/mod_390_structure.txt') as f:
            expected_content = f.read().replace('\n', '')

        self._verify_mod_390_boe(boe_file, expected_content)

    def test_export_boe_mod_390_date_range(self):
        """
        Ensure the range for the data are the one in the selected report
        """
        self.env.user.company_id = self.es_company

        self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': '2020-12-01',
            'partner_id': self.es_partner.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.es_product.id,
                    'quantity': 1,
                    'price_unit': 200,
                    'tax_ids': [Command.set([self.tax_sale_21.id])],
                }),
            ]
        }).action_post()
        self.env['account.move'].create({
            'ref': 'EDI valid ref',
            'move_type': 'in_invoice',
            'invoice_date': '2020-12-01',
            'partner_id': self.es_partner.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.es_product.id,
                    'quantity': 1,
                    'price_unit': 100,
                    'tax_ids': [Command.set([self.tax_purchase_21.id])],
                }),
            ]
        }).action_post()

        wizard_context = {
            'default_physical_person_name': "Test",
            'default_principal_activity': "Testing",
            'default_principal_code_activity': "TEST",
        }
        boe_file = self._generate_mod_390_boe(2020, wizard_context)

        expected_content = ''
        # The spaces are required to be exact to have a valid file
        with file_open('l10n_es_reports/tests/data/mod_390_with_account_move.txt') as f:
            expected_content = f.read().replace('\n', '')

        self._verify_mod_390_boe(boe_file, expected_content)

    def test_export_boe_mod_390_negative_values(self):
        """
        Ensure the negative values on the required fields is indicated with N
        """
        self.env.user.company_id = self.es_company

        self.env['account.move'].create({
            'ref': 'EDI valid ref',
            'move_type': 'in_invoice',
            'invoice_date': '2020-12-01',
            'partner_id': self.es_partner.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.es_product.id,
                    'quantity': 1,
                    'price_unit': 100,
                    'tax_ids': [Command.set([self.tax_purchase_21.id])],  # This tax will give negative value to 65
                }),
            ]
        }).action_post()

        wizard_context = {
            'default_physical_person_name': "Test",
            'default_principal_activity': "Testing",
            'default_principal_code_activity': "TEST",
        }
        boe_file = self._generate_mod_390_boe(2020, wizard_context)

        expected_content = ''
        # The spaces are required to be exact to have a valid file
        with file_open('l10n_es_reports/tests/data/mod_390_with_negative_values.txt') as f:
            expected_content = f.read().replace('\n', '')

        self._verify_mod_390_boe(boe_file, expected_content)
