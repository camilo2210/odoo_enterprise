# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time
from odoo import Command, fields, tools
from odoo.addons.account_saft.tests.common import TestSaftReport
from odoo.tests import tagged


class TestBgSaftReportEmptyNoBank(TestSaftReport):
    @classmethod
    @TestSaftReport.setup_country('bg')
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].write({
            'city': 'Varna',
            'zip': '01000',
            'phone': '0 11 11 11 11',
            'vat': 'BG949170611',
            'additional_identifiers': {'BG_CN': '7777777777'},
            'l10n_bg_saft_tax_accounting_basis': 'A',
            'l10n_bg_saft_ownership_structure': '1',
            'bank_ids': False,  # Cannot delete bank account afterwards, test first without it
        })

        cls.company_partner = cls.env['res.partner'].create({
            'name': 'John the Bossman',
            'phone': '+370 11 11 12 34',
            'parent_id': cls.company_data['company'].partner_id.id,
            'function': 'CEO',
            'email': 'john_the_bossman@big-company.com',
        })

    def _generate_xml(self):
        options = self._generate_options(fields.Date.from_string('2021-01-01'), fields.Date.from_string('2021-12-31'))
        return self.report_handler.l10n_bg_export_saft_to_xml(options)['file_content']


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBgSaftReportEmptyNoBankValues(TestBgSaftReportEmptyNoBank):
    def test_l10n_bg_saft_errors_bank_accounts(self):
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'company_bank_account_missing',
        })

    def test_l10n_bg_saft_no_error_with_bank_account(self):
        self.partner_bank_bg_iban = self.env['res.partner.bank'].create({
            'partner_id': self.company_data['company'].partner_id.id,
            'allow_out_payment': True,
            'account_number': 'BG88BNBG96618000195001',  # account_type is inferred not assigned : iban
            'bank_name': 'bank_bg',
        })
        self.company_data['company'].write({
            'bank_ids': self.partner_bank_bg_iban,
        })
        self._generate_xml()


class TestBgSaftReportEmpty(TestBgSaftReportEmptyNoBank):
    @classmethod
    @TestSaftReport.setup_country('bg')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_bank_bg_iban = cls.env['res.partner.bank'].create({
            'partner_id': cls.company_data['company'].partner_id.id,
            'allow_out_payment': True,
            'account_number': 'BG88BNBG96618000195001',  # account_type is inferred not assigned : iban
            'bank_name': 'bank_bg',
        })

        cls.company_data['company'].write({
            'bank_ids': [
                cls.partner_bank_bg_iban.id,
            ],
        })

    def _generate_xml(self):
        options = self._generate_options(fields.Date.from_string('2021-01-01'), fields.Date.from_string('2021-12-31'))
        return self.report_handler.l10n_bg_export_saft_to_xml(options)['file_content']


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBgSaftReportEmptyValues(TestBgSaftReportEmpty):
    @freeze_time('2022-01-01')
    def test_l10n_bg_saft_values(self):
        with tools.file_open("l10n_bg_saft/tests/expected_xmls/saft_report_empty.xml", "rb") as expected_xml:
            self.assertXmlTreeEqual(
                self.get_xml_tree_from_string(self._generate_xml()),
                self.get_xml_tree_from_string(expected_xml.read()),
            )


class TestBgSaftReportCommon(TestBgSaftReportEmpty):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_a.write({
            'city': 'Varna',
            'zip': '8353',
            'country_id': cls.env.ref('base.bg').id,
            'vat': 'BG999985497',
            'function': 'CFO',
        })
        cls.partner_b.write({
            'city': 'Varna',
            'zip': '8353',
            'country_id': cls.env.ref('base.bg').id,
            'vat': 'BG123456124',
            'function': 'CTO',
        })

        # partner_c is both a supplier and a customer
        cls.partner_c = cls.env['res.partner'].create({
            'name': 'partner_c',
            'city': 'Varna',
            'zip': '8353',
            'country_id': cls.env.ref('base.bg').id,
            'vat': 'BG456123123',
            'function': 'CMO',
        })

        cls.partner_bank_at_not_iban = cls.env['res.partner.bank'].create({
            'partner_id': cls.company_data['company'].partner_id.id,
            'allow_out_payment': True,
            'account_number': '00000000',  # account_type is inferred not assigned : not iban
            'l10n_bg_saft_registration_number': 'REGNUM2AUS',

            'bank_name': 'Austrian General Bank',
            'bank_bic': 'AUSBNKNK',
            'country_id': cls.env.ref('base.at').id,
        })

        cls.company_ultimate_owner_bg = cls.env['res.partner'].create({
            'name': 'Фирма 1',
            'country_id': cls.env.ref('base.bg').id,
            'vat': 'BG5678912325',
        })
        cls.company_ultimate_owner_foreign = cls.env['res.partner'].create({
            'name': 'Company 2',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BG2345678924',
        })
        cls.company_related_partner = cls.env['res.partner'].create({
            'name': 'Фирма 3',
            'country_id': cls.env.ref('base.bg').id,
            'city': 'Varna',
            'zip': '01000',
            'vat': 'BG6789123452',
        })

        cls.company_beneficial_owner_bg = cls.env['res.partner'].create({
            'name': 'Франк, Действителният Собственик',
            'country_id': cls.env.ref('base.bg').id,
            'additional_identifiers': {'BG_CN': '567867867'},
        })
        cls.company_beneficial_owner_foreign = cls.env['res.partner'].create({
            'name': 'Bill the Beneficial Owner',
            'country_id': cls.env.ref('base.fr').id,
        })

        cls.company_data['company'].write({
            'l10n_bg_saft_ownership_structure': '4',
            'bank_ids': [
                cls.partner_bank_bg_iban.id,
                cls.partner_bank_at_not_iban.id,
            ],
            'l10n_bg_saft_ultimate_owner_ids': [
                cls.company_ultimate_owner_bg.id,
                cls.company_ultimate_owner_foreign.id,
            ],
            'l10n_bg_saft_beneficial_owner_ids': [
                cls.company_beneficial_owner_bg.id,
                cls.company_beneficial_owner_foreign.id,
            ],
            'l10n_bg_saft_related_partner_ids': [
                cls.company_related_partner.id,
            ],
        })

        cls.self_billing_journal_id = cls.env['account.journal'].create({
            'name': 'Self Billing Journal',
            'code': 'SELFB',
            'type': 'purchase',
            'company_id': cls.company.id,
            'is_self_billing': True,
        })

        cls.product_a.default_code = 'PA'
        cls.product_b.default_code = 'PB'
        cls.product_a.intrastat_code_id = cls.env.ref('account_intrastat.commodity_code_2018_1012100')
        cls.product_b.intrastat_code_id = cls.env.ref('account_intrastat.commodity_code_2018_1012910')

        cls.product_uom_1 = cls.env['uom.uom'].create({
            'name': 'Pack of 24',
            'relative_factor': 24,
            'relative_uom_id': cls.env.ref('uom.product_uom_unit').id,
            'l10n_bg_saft_uom_code': 'DZN',
            'l10n_bg_saft_uom_description': "дузина / dozen",
            'l10n_bg_saft_uom_conversion_factor': 2,
        })

        cls.product_uom_2 = cls.env['uom.uom'].create({
            'name': 'Pallet',
            'relative_factor': 10,
            'relative_uom_id': cls.env.ref('uom.product_uom_unit').id,
            'l10n_bg_saft_uom_code': 'XPK',
            'l10n_bg_saft_uom_description': "Пакет / Package",
            'l10n_bg_saft_uom_conversion_factor': 1,
        })

        cls.product_b.uom_id = cls.product_uom_1.id

        invoices = cls.env['account.move'].create([{
                'move_type': 'out_invoice',
                'invoice_date': '2021-01-01',
                'date': '2021-01-01',
                'partner_id': cls.partner_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 5.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_sale'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2021-03-01',
                'date': '2021-03-01',
                'partner_id': cls.company_data['company'].partner_id.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 2.0,
                        'price_unit': 1500.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_sale'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_refund',
                'invoice_date': '2021-03-01',
                'date': '2021-03-01',
                'partner_id': cls.partner_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 3.0,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_sale'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2021-06-30',
                'date': '2021-06-30',
                'partner_id': cls.partner_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_b.id,
                        'product_uom_id': cls.product_uom_1.id,
                        'quantity': 10.0,
                        'price_unit': 800.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2021-06-30',
                'date': '2021-06-30',
                'partner_id': cls.partner_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_b.id,
                        'quantity': 10.0,
                        'product_uom_id': cls.product_uom_2.id,
                        'price_unit': 800.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2021-06-15',
                'date': '2021-06-15',
                'partner_id': cls.company_related_partner.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 5.0,
                        'product_uom_id': cls.product_uom_1.id,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2021-03-15',
                'date': '2021-03-15',
                'partner_id': cls.partner_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 5.0,
                        'product_uom_id': cls.product_uom_1.id,
                        'price_unit': 100.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'out_invoice',
                'invoice_date': '2021-03-17',
                'date': '2021-03-17',
                'partner_id': cls.partner_c.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_b.id,
                        'quantity': 5.0,
                        'product_uom_id': cls.product_uom_1.id,
                        'price_unit': 200.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
            {  # self bill
                'move_type': 'in_invoice',
                'invoice_date': '2021-03-18',
                'date': '2021-03-18',
                'partner_id': cls.partner_c.id,
                'journal_id': cls.self_billing_journal_id.id,
                'name': 'SELFB/2021/03/0001',  # Prevent the self billing journal from prepending a client id for sequencing
                'invoice_line_ids': [
                    Command.create({
                        'product_id': cls.product_a.id,
                        'quantity': 5.0,
                        'product_uom_id': cls.product_uom_1.id,
                        'price_unit': 200.0,
                        'tax_ids': [Command.set(cls.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
        ])

        invoices.action_post()

        cls.env['account.bank.statement'].create({
            'name': 'test_statement',
            'line_ids': [
                Command.create({
                    'date': '2021-03-01',
                    'payment_ref': 'Payment Ref',
                    'partner_id': cls.partner_a.id,
                    'journal_id': cls.company_data['default_journal_bank'].id,
                    'foreign_currency_id': cls.env.ref('base.EUR').id,
                    'amount': 1250.0,
                    'amount_currency': 250.0,
                }),
            ],
        })


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBgSaftReport(TestBgSaftReportCommon):
    @freeze_time('2022-01-01')
    def test_l10n_bg_saft_values(self):
        with tools.file_open("l10n_bg_saft/tests/expected_xmls/saft_report.xml", "rb") as expected_xml:
            self.assertXmlTreeEqual(
                self.get_xml_tree_from_string(self._generate_xml()),
                self.get_xml_tree_from_string(expected_xml.read()),
            )

    def test_l10n_bg_saft_ensure_all_taxes_are_mapped(self):
        """Tests that all the tax are mapped to a SAF-T tax code"""

        company = self.company_data['company']

        # The Armageddon Tax is a tax created for testing purposes and does not have a mapping
        armageddon_tax_group = self.env['account.tax'].with_company(company).search([
            ('name', '=', 'complex_tax (group)'),
        ])
        armageddon_tax_group_id = armageddon_tax_group.tax_group_id

        taxes_missing_saft_code = self.env['account.tax'].with_company(company).search([
            ('l10n_bg_saft_tax_code', '=', False),
            ('tax_group_id', '!=', armageddon_tax_group_id.id),
        ])

        self.assertEqual(len(taxes_missing_saft_code), 0)

    def test_l10n_bg_saft_ensure_all_accounts_are_mapped(self):
        """Tests that all the accounts are mapped to a SAF-T code"""

        company = self.company_data['company']

        # These journals and their default accounts are created after the company
        # creation in the testing env, they won't have a saft code assigned to them
        accounts_created_afterwards = self.env['account.journal'].with_company(company).search([
            ('code', 'in', ['CASH1', 'CCD1']),
        ]).default_account_id

        irrelevant_accounts = accounts_created_afterwards + self.garbage_account

        accounts_missing_saft_code = self.env['account.account'].with_company(company).search([
            *self.env['account.account']._check_company_domain(company),
            ('l10n_bg_saft_account_code', '=', False),
            ('id', 'not in', (irrelevant_accounts).ids),
        ])
        self.assertEqual(len(accounts_missing_saft_code), 0)

    def test_l10n_bg_saft_ensure_all_account_type_are_handled(self):
        report = self.env.ref('account_reports.general_ledger_report')
        account_selection = [selection[0] for selection in self.env["account.account"]._fields["account_type"].selection]
        for account_type in account_selection:
            self.env[report.custom_handler_model_name]._saft_get_account_type(account_type)

    def test_l10n_bg_saft_errors_header(self):
        self.company_data['company'].write({
            'l10n_bg_saft_tax_accounting_basis': False,
            'l10n_bg_saft_ownership_structure': False,
            'l10n_bg_saft_tax_entity_type': False,
            'vat': False,
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'settings_accounting_basis_missing',
            'settings_ownership_structure_missing',
            'company_tax_entity_type_missing',
            'company_vat_number_missing',

            # As the vat is not set anymore, the company partner is no longer
            # recognized as a company and thus becomes its own main contact. As
            # those fields are not defined on that partner they raise errors as well
            'missing_partner_function',
            'missing_partner_email',
            'missing_partner_last_name',
        })

    def test_l10n_bg_saft_errors_ultimate_owners_missing(self):
        self.company_data['company'].write({
            'l10n_bg_saft_ultimate_owner_ids': False,
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'ultimate_owners_missing',
        })

    def test_l10n_bg_saft_errors_ultimate_owners(self):
        self.company_ultimate_owner_bg.write({
            'vat': False,  # proxy for is_company: False
            'country_id': False,
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'ultimate_owners_not_company',
            'ultimate_owners_missing_country',
        })

    def test_l10n_bg_saft_errors_ultimate_owners_bg(self):
        self.company_ultimate_owner_bg.write({
            'name': 'Jack the Ultimate Owner',
            'vat': False,  # proxy for is_company: False
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'bg_ultimate_owners_missing_cyrillic_name',
            'bg_ultimate_owners_missing_vat',
            'ultimate_owners_not_company',
        })

    def test_l10n_bg_saft_errors_beneficial_owners(self):
        self.company_beneficial_owner_bg.write({
            'country_code': False,
            'vat': 'BG1234567892',  # proxy for is_company: True
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'beneficial_owners_missing_country',
            'beneficial_owners_not_person',
        })

    def test_l10n_bg_saft_errors_beneficial_owners_bg(self):
        self.company_beneficial_owner_bg.write({
            'name': 'Frank the Beneficial Owner',
            'additional_identifiers': {},
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'bg_beneficial_owners_missing_cyrillic_name',
            'bg_beneficial_owners_missing_egn',
        })

    def test_l10n_bg_saft_errors_beneficial_owners_foreign(self):
        self.company_beneficial_owner_foreign.write({
            'name': 'Бил действителният собственик',
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'foreign_beneficial_owners_missing_latin_name',
        })

    def test_l10n_bg_saft_errors_bank_account(self):
        self.partner_bank_at_not_iban.write({
            'bank_name': False,
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'bank_account_with_missing_bank_name',
        })

    def test_l10n_bg_saft_errors_bank_registration(self):
        self.partner_bank_at_not_iban.write({
            'l10n_bg_saft_registration_number': False,
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'bank_account_with_missing_registration_number',
        })

    def test_l10n_bg_saft_errors_bank_country(self):
        self.partner_bank_at_not_iban.write({
            'country_id': False,
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'bank_account_with_missing_country',
        })

    def test_l10n_bg_saft_errors_company_partner(self):
        self.company_partner.write({
            'phone': False,
            'function': False,
            'email': False,
            'name': "fullnamewithnospace",
        })
        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'missing_partner_phone_number',
            'missing_partner_function',
            'missing_partner_email',
            'missing_partner_last_name',
        })

    def test_l10n_bg_saft_errors_customer_supplier_code(self):

        report = self.env.ref('account_reports.general_ledger_report')

        def check_customer_supplier_code(code, country_code=False, egn=False, vat=False, is_company=True):
            self.assertEqual(
                code,
                get_customer_supplier_code(country_code, egn, vat, is_company),
            )

        def check_customer_supplier_code_startswith(code, country_code=False, egn=False, vat=False, is_company=True):
            self.assertTrue(get_customer_supplier_code(country_code, egn, vat, is_company).startswith(code))

        parent_partner = self.env['res.partner'].create({
            'name': 'parent_partner',
            'country_id': self.env.ref('base.bg').id,
            'vat': 'BG1234567892',
        })

        def get_customer_supplier_code(country_code, egn, vat, is_company):
            return self.env[report.custom_handler_model_name]._l10n_bg_saft_fill_customer_supplier_code(
                self.env['res.partner'].create({
                    'name': 'partnerX',
                    'additional_identifiers': {'BG_CN': egn} if egn else {},
                    'country_id': self.env.ref('base.' + country_code).id if country_code else False,
                    'vat': vat,

                    # Proxy for is_company. Case where not a company but has valid VAT
                    'parent_id': parent_partner.id if not is_company and vat else False,
                }))

        check_customer_supplier_code('131234567892', country_code='bg', egn='1234567892', vat=False, is_company=False)
        check_customer_supplier_code('131234567892', country_code='bg', egn=False, vat='1234567892', is_company=False)
        check_customer_supplier_code('131234567892', country_code='bg', egn=False, vat='BG1234567892', is_company=False)
        check_customer_supplier_code('131234567892', country_code=False, egn=False, vat='BG1234567892', is_company=False)
        check_customer_supplier_code('131234567892', country_code=False, egn=False, vat='bG1234567892', is_company=False)

        # Cannot be a company without a valid VAT number
        check_customer_supplier_code('101234567892', country_code='bg', egn=False, vat='1234567892')
        check_customer_supplier_code('101234567892', country_code='bg', egn=False, vat='BG1234567892')
        check_customer_supplier_code('101234567892', country_code=False, egn=False, vat='BG1234567892')

        check_customer_supplier_code('11FR23334175221', country_code='fr', egn=False, vat='FR23334175221')
        check_customer_supplier_code('12US1234567892', country_code='us', egn=False, vat='1234567892')
        check_customer_supplier_code('12US1234567892', country_code='us', egn=False, vat='US1234567892')
        check_customer_supplier_code('12uS1234567892', country_code='us', egn=False, vat='uS1234567892')
        check_customer_supplier_code('12USSDRFtj567', country_code='us', egn=False, vat='SDRFtj567')
        check_customer_supplier_code_startswith('14', country_code='us', egn=False, vat=False)

        check_customer_supplier_code_startswith('15', country_code=False, egn=False, vat=False)

    def test_l10n_bg_saft_errors_product_uom(self):
        self.product_uom_3 = self.env['uom.uom'].create({
            'name': 'handful',
            'relative_factor': 5,
            'relative_uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        self.product_c = self.env['product.product'].create({
            'name': 'prod C',
            'uom_id': self.product_uom_3.id,
            'standard_price': 50,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'invoice_date': '2021-06-25',
            'date': '2021-06-25',
            'partner_id': self.partner_b.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_c.id,
                    'quantity': 10.0,
                    'tax_ids': [Command.set(self.company_data['default_tax_purchase'].ids)],
                }),
            ],
        })
        invoice.action_post()

        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'uom_with_missing_saft_code',
            'uom_with_missing_saft_description',
            'product_intrastat_code_missing',
            'product_internal_reference_missing',
        })

    def test_l10n_bg_saft_errors_product_duplicate_ref(self):
        self.product_c = self.env['product.product'].create({
            'name': 'prod C',
            'default_code': 'REF12345',
            'standard_price': 50,
            'intrastat_code_id': self.env.ref('account_intrastat.commodity_code_2018_1012100').id,
        })
        self.product_d = self.env['product.product'].create({
            'name': 'prod D',
            'default_code': 'REF12345',
            'standard_price': 100,
            'intrastat_code_id': self.env.ref('account_intrastat.commodity_code_2018_1012910').id,
        })
        invoice = self.env['account.move'].create([
            {
                'move_type': 'in_invoice',
                'invoice_date': '2021-06-25',
                'date': '2021-06-25',
                'partner_id': self.partner_b.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product_c.id,
                        'quantity': 10.0,
                        'tax_ids': [Command.set(self.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
            {
                'move_type': 'in_invoice',
                'invoice_date': '2021-06-26',
                'date': '2021-06-26',
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product_d.id,
                        'quantity': 3.0,
                        'tax_ids': [Command.set(self.company_data['default_tax_purchase'].ids)],
                    }),
                ],
            },
        ])
        invoice.action_post()

        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'product_internal_reference_duplicated',
        })

    def test_l10n_bg_saft_check_cyrillic_name(self):
        report = self.env.ref('account_reports.general_ledger_report')
        customer_handler = self.env[report.custom_handler_model_name]

        def check_name(name, boolean):
            self.assertEqual(customer_handler._check_cyrillic_name(name), boolean)

        check_name('Бил', True)
        check_name('Bill', False)
        check_name('Фирма', True)
        check_name('Company', False)
        check_name('Фирма Mix Name', True)
        check_name('Бил 129', True)

    def _remove_account_code(self):
        income_account_id = self.company_data['company'].income_account_id
        income_account_id.l10n_bg_saft_account_code = False

    def test_l10n_bg_saft_errors_missing_account_code(self):
        self._remove_account_code()

        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'accounts_missing_saft_code',
        })

    def test_l10n_bg_saft_errors_missing_account_code_reload_not_overwriting(self):
        self._remove_account_code()

        company = self.company_data['company']

        # Pressing the Reload button in the settings
        self.env['account.chart.template'].try_loading(company.chart_template, company=company)

        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'accounts_missing_saft_code',
        })

    def _remove_tax_code(self):
        default_tax_sale_ids = self.company_data['default_tax_sale'].ids
        first_tax = self.env['account.tax'].browse(default_tax_sale_ids[0])
        first_tax.l10n_bg_saft_tax_code = False

    def test_l10n_bg_saft_errors_missing_tax_code(self):
        self._remove_tax_code()

        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'taxes_missing_saft_code',
        })

    def test_l10n_bg_saft_errors_missing_tax_code_reload_not_overwriting(self):
        """test that the Chart of Account reload does not re-add the missing tax codes"""
        self._remove_tax_code()

        company = self.company_data['company']

        # Pressing the Reload button in the settings
        self.env['account.chart.template'].try_loading(company.chart_template, company=company)

        with self.assertRaises(self.ReportException) as cm:
            self._generate_xml()
        self.assertEqual(set(cm.exception.errors), {
            'taxes_missing_saft_code',
        })
