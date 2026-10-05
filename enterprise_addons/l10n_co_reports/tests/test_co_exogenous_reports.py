# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv

from odoo import Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from datetime import date
from io import StringIO


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nCoReportsExogenous(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_chart_template('co')
    @TestAccountReportsCommon.setup_country('co')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_partner = cls.env['res.partner'].create({
            'name': 'Test CO Company',
            'street': 'CL 88A',
            'city_id': cls.env.ref('l10n_co_edi.city_co_150').id,
            'state_id': cls.env.ref('base.state_co_03').id,
            'country_id': cls.env.ref('base.co').id,
            'country_code': 'CO',
            'vat': '111111111-9',
        })
        cls.company = cls.company_data['company']
        cls.company.partner_id = cls.company_partner.id
        cls.branch_company = cls._create_company(
            name='Test CO Company - Branch',
            parent_id=cls.company.id,
        )

        cls.foreign_business_partner = cls.env['res.partner'].create({
            'name': 'Foreign Business Partner',
            'street': '77 Santa Barbara Rd',
            'state_id': cls.env.ref('base.state_us_5').id,
            'country_id': cls.env.ref('base.us').id,
            'vat': 'US88888888',
        })
        cls.consumidor_final_partner = cls.env.ref('l10n_co_edi.consumidor_final_customer')
        cls.co_business_partner = cls.env['res.partner'].create({
            'name': 'CO Business Partner',
            'street': 'CL 12A',
            'city_id': cls.env.ref('l10n_co_edi.city_co_150').id,
            'state_id': cls.env.ref('base.state_co_01').id,
            'country_id': cls.env.ref('base.co').id,
            'vat': '213123432-1',
        })
        cls.tri_name_partner = cls.env['res.partner'].create({
            'name': 'Jane Lee Doe',
            'street': 'CL 13A',
            'city_id': cls.env.ref('l10n_co_edi.city_co_150').id,
            'state_id': cls.env.ref('base.state_co_03').id,
            'country_id': cls.env.ref('base.co').id,
            'additional_identifiers': {'CO_CC': '333333333'},
        })
        cls.quad_name_partner = cls.env['res.partner'].create({
            'name': 'James Jameson Lee Doe',
            'street': 'CL 14A',
            'city_id': cls.env.ref('l10n_co_edi.city_co_150').id,
            'state_id': cls.env.ref('base.state_co_03').id,
            'country_id': cls.env.ref('base.co').id,
            'additional_identifiers': {'CO_CC': '444444444'},
        })

        cls.general_ledger_report = cls.env.ref('account_reports.general_ledger_report')
        cls.general_ledger_report_handler = cls.env[cls.general_ledger_report.custom_handler_model_name]

    def _get_report_csv_data(self, report_type, allowed_companies=False):
        '''
        Return the exogenous report data with the specified options

        :param report_type: the report type
        :param allowed_companies: a recordset of self.env['res.company']
        '''
        options = self._generate_options(self.general_ledger_report, date(2026, 1, 1), date(2026, 1, 31))
        options['exogenous_report_type'] = report_type
        if allowed_companies:
            options['companies'] = [{'name': company.name, 'id': company.id, 'currency_id': company.currency_id.id} for company in allowed_companies]
        file_content = self.general_ledger_report_handler.l10n_co_reports_exogenous_report_csv_file_generator(options)['file_content']
        file = StringIO(file_content)
        reader = csv.reader(file, delimiter=',')
        return list(reader)

    def _create_move(self, company, move_type, partner, price_unit, account=False, tax=False):
        line_vals = {
            'quantity': 1.0,
            'name': 'product test 1',
            'price_unit': price_unit,
            'company_id': company.id,
        }
        if account:
            line_vals['account_id'] = account.id
        if tax:
            line_vals['tax_ids'] = [tax.id]

        move = self.env['account.move'].create({
            'company_id': company.id,
            'partner_id': partner.id,
            'move_type': move_type,
            'invoice_date': '2026-01-28',
            'invoice_line_ids': [
                Command.create(line_vals),
            ],
        })
        move.action_post()
        move.line_ids.flush_recordset()
        return move

    def _create_no_partner_entries(self, company, account, debit=0, credit=0):
        line_vals = {
            'account_id': account.id,
            'debit': debit,
            'credit': credit,
        }
        balancing_line_vals = {
            'credit': debit if debit else 0,
            'debit': credit if credit else 0,
            'account_id': self.consumidor_final_partner.property_account_receivable_id.id if credit else self.consumidor_final_partner.property_account_payable_id.id,
        }
        entry = self.env['account.move'].create({
            'date': '2026-01-28',
            'company_id': company.id,
            'line_ids': [
                Command.create(line_vals),
                Command.create(balancing_line_vals),
            ]
        })
        entry.action_post()
        entry.line_ids.flush_recordset()
        return entry

    def test_1_report_1009(self):
        '''
        Test report 1009 with minor amounts
        Payable Accounts (regularly in Vendor Bills and defined on the Partner)
        Default payable on partners uses account 220500 that's mapped to exogenous_categ_1009_01
        Minor Amount Rule:
            - Any move lines using account with exogenous category, exogenous_categ_1009_01,
            whose balance is less than 12 UVT or partner is Consumidor Final
        '''
        move_type = 'in_invoice'
        company = self.company
        # Minor amount lines
        self._create_move(company, move_type, self.consumidor_final_partner, 1000)  # Consumidor Final is minor amount
        self._create_move(company, move_type, self.tri_name_partner, 4)  # Minor amount if less than 12 UVT (assumed 1 COP : 1 UVT for tests)
        # Regular lines
        self._create_move(company, move_type, self.quad_name_partner, 400.50)  # Round up
        foreign_business_partner = self.foreign_business_partner
        foreign_business_partner.property_account_payable_id = self.env.ref(f"account.{self.company.id}_co_puc_221000").id
        self._create_move(company, move_type, foreign_business_partner, 302.40)  # Foreign Partner using account 221000 and round down
        self._create_move(company, move_type, self.co_business_partner, 800)  # Business Partner with VD
        data = self._get_report_csv_data('1009')
        self.assertEqual(len(data), 5, 'Expected 5 lines in CSV')
        self.assertEqual(len(data[0]), 14, 'Wrong amount of columns for report 1009')
        self.assertEqual(
            sorted(data[1:]),
            [
                # ['CONCEPT', 'IDENTIFICATION TYPE', 'VAT', 'VD', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'ADDRESS', 'STATE CODE', 'CITY CODE', 'COUNTRY CODE', 'ACCOUNTS PAYABLE BALANCE AS OF 31-12'],
                ['2201', '13', '444444444', '', 'Lee', 'Doe', 'James', 'Jameson', '', 'CL 14A', '11', '001', '169', '401.0'],
                ['2201', '31', '213123432', '1', '', '', '', '', 'CO Business Partner', 'CL 12A', '05', '001', '169', '800.0'],
                ['2201', '42', 'US88888888', '', '', '', '', '', 'Foreign Business Partner', '', '', '', '249', '302.0'],
                ['2201', '43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', 'CL 88A', '11', '001', '169', '1004.0'],
            ],
            'Report 1009 csv output did not match expected output'
        )

    def test_2_report_1008(self):
        '''
        Test report 1008 without minor amounts
        Receivable Accounts usually defined on the partner's receivable
        (regularly in Customer Invoices)
        '''
        move_type = 'out_invoice'
        company = self.company
        tri_name_partner = self.tri_name_partner
        concept_1315_account = self.env.ref(f"account.{company.id}_co_puc_130500")
        concept_1316_account = self.env.ref(f"account.{company.id}_co_puc_131500")
        concept_1317_account = self.env.ref(f"account.{company.id}_co_puc_132800")
        tri_name_partner.property_account_receivable_id = concept_1315_account.id
        self._create_move(company, move_type, tri_name_partner, 1315)
        tri_name_partner.property_account_receivable_id = concept_1316_account.id
        self._create_move(company, move_type, tri_name_partner, 1316)
        tri_name_partner.property_account_receivable_id = concept_1317_account.id
        self._create_move(company, move_type, tri_name_partner, 1317)
        # Content validation
        data = self._get_report_csv_data('1008')
        self.assertEqual(len(data), 4, 'Expected 4 lines in csv file for report 1008')
        self.assertEqual(len(data[0]), 14, 'Wrong amount of columns for report 1008')
        self.assertEqual(
            sorted(data[1:]),
            [
                # ['CONCEPT', 'IDENTIFICATION TYPE', 'VAT', 'VD', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'ADDRESS', 'STATE CODE', 'CITY CODE', 'COUNTRY CODE', 'ACCOUNTS RECEIVABLE BALANCE AS OF 31-12'],
                ['1315', '13', '333333333', '', 'Doe', 'Lee', 'Jane', '', '', 'CL 13A', '11', '001', '169', '1315.0'],
                ['1316', '13', '333333333', '', 'Doe', 'Lee', 'Jane', '', '', 'CL 13A', '11', '001', '169', '1316.0'],
                ['1317', '13', '333333333', '', 'Doe', 'Lee', 'Jane', '', '', 'CL 13A', '11', '001', '169', '1317.0'],
            ],
            'Report 1008 csv output does not match expected output.'
        )

    def test_3_report_1007(self):
        '''
        Test report 1007 with only minor amounts and concepts
        Income Accounts (regularly in Customer Invoices and Customer Credit Notes)
        Minor Amount Rule:
            - Any move lines with either no partner or Consumidor Final
            using accounts with exogenous category, exogenous_categ_1007_01
        '''
        company = self.company
        concept_4003_account = self.env.ref(f"account.{company.id}_co_puc_421005")
        concept_4001_account = self.env.ref(f"account.{company.id}_co_puc_410500")
        # Minor amounts
        self._create_no_partner_entries(company, concept_4003_account, credit=50)
        self._create_no_partner_entries(company, concept_4001_account, credit=35)
        self._create_move(company, 'out_invoice', self.consumidor_final_partner, 20, concept_4003_account)
        # Content Validation
        data = self._get_report_csv_data('1007')
        self.assertEqual(len(data), 3, 'Expected 3 lines in csv file for report 1007')
        self.assertEqual(len(data[0]), 11, 'Wrong amount of columns for report 1007')
        self.assertEqual(
            sorted(data[1:]),
            [
                # ['CONCEPT', 'IDENTIFICATION TYPE', 'VAT', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'COUNTRY CODE', 'GROSS INCOME RECEIVED', 'RETURNS, ALLOWANCES, AND DISCOUNTS'],
                ['4001', '43', '222222222', '', '', '', '', 'CUANTIAS MENORES', '169', '35.0', '0.0'],
                ['4003', '43', '222222222', '', '', '', '', 'CUANTIAS MENORES', '169', '70.0', '0.0'],
            ],
            'Report 1007 csv output does not match expected output.'
        )

    def test_4_report_1006(self):
        '''
        Test report 1006 with minor amounts and no concepts
        Discountable VAT and INC accounts usually set on purchase taxes
        (regularly Vendor Bills)
        Minor Amount Rule:
            - Any move lines with either no partner or Consumidor Final
            using accounts with exogenous category, exogenous_categ_1006_02
            - Vendor bills' credit note refunds with the set tax and account
        '''
        company = self.company
        account = self.env.ref(f"account.{company.id}_co_puc_240810")  # Uses both credit and debit 1006 categories
        purchase_tax = self.env.ref(f"account.{company.id}_l10n_co_tax_1")
        # Minor amounts
        self._create_no_partner_entries(company, account, credit=13)
        self._create_move(company, 'in_invoice', self.consumidor_final_partner, 1000, tax=purchase_tax)
        self._create_move(company, 'in_refund', self.consumidor_final_partner, 1000, tax=purchase_tax)
        # Non minor amounts
        self._create_move(company, 'in_invoice', self.co_business_partner, 100, tax=purchase_tax)
        # Content Validation
        data = self._get_report_csv_data('1006')
        self.assertEqual(len(data), 3, 'Expected 3 lines in csv file for report 1006')
        self.assertEqual(len(data[0]), 11, 'Wrong amount of columns for report 1006')
        self.assertEqual(
            sorted(data[1:]),
            [
                # ['IDENTIFICATION TYPE', 'VAT', 'VD', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'GENERATED TAX', 'VAT RECOVERED FROM RETURNS ON CANCELED, RESCINDED, OR TERMINATED PURCHASES', 'CONSUMPTION TAX'],
                ['31', '213123432', '1', '', '', '', '', 'CO Business Partner', '19.0', '0.0', '0.0'],
                ['43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', '190.0', '203.0', '0.0'],
            ],
            'Report 1006 csv output does not match expected output.'
        )

    def test_5_report_1005(self):
        '''
        Test report 1005 with minor amount and multiple categories
        Accrued VAT accounts usually set on sale taxes
        (regularly Customer Invoices)
        Minor Amount Rule:
            - Any move lines with either no partner or Consumidor Final
            using accounts with multiple exogenous categories
                - exogenous_categ_1005_01
                - exogenous_categ_1005_02
            - Both customer invoices and credit notes
        '''
        company = self.company
        account = self.env.ref(f"account.{company.id}_co_puc_240805")  # Uses both credit and debit 1005 categories
        sale_tax = self.env.ref(f"account.{company.id}_l10n_co_tax_8")
        # Minor amounts
        self._create_move(company, 'out_invoice', self.consumidor_final_partner, 67, tax=sale_tax)
        self._create_move(company, 'out_refund', self.consumidor_final_partner, 2000, tax=sale_tax)
        self._create_no_partner_entries(company, account, credit=13)
        # Content Validation
        data = self._get_report_csv_data('1005')
        self.assertEqual(len(data), 2, 'Expected 2 lines in csv file for report 1005')
        self.assertEqual(len(data[0]), 11, 'Wrong amount of columns for report 1005')
        self.assertEqual(
            data[1:],
            [
                # ['IDENTIFICATION TYPE', 'VAT', 'VD', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'DEDUCTIBLE TAX', 'VAT RESULTING FROM RETURNS ON CANCELED, RESCINDED, OR TERMINATED SALES', 'VAT TREATED AS A HIGHER COST OR EXPENSE (ART. 490 TAX CODE)'],
                ['43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', '26.0', '380.0', '0.0'],
            ],
            'Report 1005 csv output does not match expected output.'
        )

    def test_6_report_1003(self):
        '''
        Test report 1003
        Income Accounts and Current Assets Accounts usually set on sale taxes
        (regularly income and withholding lines on Customer Invoices)
        Usually added as in the taxes field of customer invoices lines (Rte)
        Minor Amount Rule:
            - Any move lines using account with exogenous category, exogenous_categ_1003_01,
            whose balance is less than 3 UVT or partner is Consumidor Final
        '''
        company = self.company
        # Credit accounts - Income accounts
        concept_1309_1302_account = self.env.ref(f"account.{company.id}_co_puc_413000")  # Account is mapped to multiple exogenous categories with different concepts
        concept_1302_account = self.env.ref(f"account.{company.id}_co_puc_420500")
        # Debit accounts - Withholding Tax
        sale_tax = self.env.ref(f"account.{company.id}_l10n_co_tax_53")
        # Minor Amount
        move_type = 'out_invoice'
        self._create_move(company, move_type, self.consumidor_final_partner, 90, account=concept_1309_1302_account)
        self._create_move(company, move_type, self.foreign_business_partner, 1.99, account=concept_1302_account)
        # Non-minor amount
        self._create_move(company, move_type, self.tri_name_partner, 168.88, account=concept_1302_account, tax=sale_tax)
        # Content Validation
        data = self._get_report_csv_data('1003')
        self.assertEqual(len(data), 4, 'Expected 4 lines in csv file for report 1003')
        self.assertEqual(len(data[0]), 14, 'Wrong amount of columns for report 1003')
        self.assertEqual(
            sorted(data[1:]),
            [
                # ['CONCEPT', 'IDENTIFICATION TYPE', 'VAT', 'VD', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'ADDRESS', 'STATE CODE', 'CITY CODE', 'ACCUMULATED AMOUNT OF PAYMENT OR CREDIT SUBJECT TO WITHHOLDING AT SOURCE', 'WITHHOLDING TAX APPLIED TO YOU'],
                ['1302', '13', '333333333', '', 'Doe', 'Lee', 'Jane', '', '', 'CL 13A', '11', '001', '169.0', '4.0'],
                ['1302', '43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', 'CL 88A', '11', '001', '92.0', '0.0'],
                ['1309', '43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', 'CL 88A', '11', '001', '90.0', '0.0'],
            ],
            'Report 1003 csv output does not match expected output.'
        )

    def test_7_report_1001(self):
        '''
        Test report 1001
        Expense Accounts and Current Liabilities Accounts usually added in purchases taxes (Rte)
        (regularly the expense and withholding lines in Vendor Bills)
        Minor Amount Rule:
            - Any move lines using account with exogenous category, exogenous_categ_1001_01,
            whose balance is less than 3 UVT or partner is Consumidor Final
        '''
        company = self.company
        # Debit Accounts - Expense accounts
        concept_5004_account = self.env.ref(f"account.{company.id}_co_puc_513500")
        concept_5002_account = self.env.ref(f"account.{company.id}_co_puc_511000")
        # Credit Accounts - Withholding tax
        purchase_tax = self.env.ref(f"account.{company.id}_l10n_co_tax_23")
        # Minor Amounts
        move_type = 'in_invoice'
        self._create_move(company, move_type, self.consumidor_final_partner, 100, account=concept_5004_account, tax=purchase_tax)
        self._create_move(company, move_type, self.tri_name_partner, 3, account=concept_5004_account, tax=purchase_tax)
        # Non Minor Amounts
        self._create_move(company, move_type, self.co_business_partner, 1000, account=concept_5002_account)
        # Content Validation
        data = self._get_report_csv_data('1001')
        self.assertEqual(len(data), 4, 'Expected 4 lines in csv file for report 1001')
        self.assertEqual(len(data[0]), 20, 'Wrong amount of columns for report 1001')
        self.assertEqual(
            sorted(data[1:]),
            [
                # ['CONCEPT', 'IDENTIFICATION TYPE', 'VAT', 'PARTNER FIRST LAST NAME', 'PARTNER SECOND LAST NAME', 'PARTNER FIRST NAME', 'PARTNER OTHER NAME', 'BUSINESS NAME', 'ADDRESS', 'STATE CODE', 'CITY CODE', 'COUNTRY CODE', 'DEDUCTIBLE PAYMENT OR CREDIT TO ACCOUNT', 'PAYMENT OR ACCOUNT CREDIT NOT DEDUCTIBLE', 'VAT AS A HIGHER COST OR EXPENSE, DEDUCTIBLE', 'VAT AS A HIGHER COST OR EXPENSE, NOT DEDUCTIBLE', 'WITHHOLDING TAX APPLIED ON INCOME', 'WITHHOLDING TAX ASSUMED ON INCOME', 'WITHHOLDING TAX APPLIED ON VAT TO VAT-LIABLE ENTITIES', 'WITHHOLDING TAX APPLIED ON VAT TO NON-RESIDENTS OR NON-DOMICILED ENTITIES'],
                ['5002', '31', '213123432', '', '', '', '', 'CO Business Partner', 'CL 12A', '05', '001', '169', '1000.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0'],
                ['5004', '13', '333333333', 'Doe', 'Lee', 'Jane', '', '', 'CL 13A', '11', '001', '169', '3.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0'],
                ['5004', '43', '222222222', '', '', '', '', 'CUANTIAS MENORES', 'CL 88A', '11', '001', '169', '100.0', '0.0', '0.0', '0.0', '4.0', '0.0', '0.0', '0.0'],
            ],
            'Report 1001 csv output does not match expected output.'
        )

    def test_8_report_1009_with_branch(self):
        '''
        Test the report when only a branch company is selected
        - Root company address should be used for minor amount rows
        '''
        move_type = 'in_invoice'
        company = self.branch_company
        # Minor amount lines
        self._create_move(company, move_type, self.consumidor_final_partner, 1009)  # Consumidor Final is minor amount
        self._create_move(company, move_type, self.tri_name_partner, 4)
        data = self._get_report_csv_data('1009', company)
        self.assertEqual(len(data), 2, 'Expected 2 lines in csv file for report 1009')
        self.assertEqual(
            data[1:],
            [
                ['2201', '43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', 'CL 88A', '11', '001', '169', '1013.0'],
            ],
            'CSV output does not match expected output'
        )

    def test_9_report_1005_with_company_and_branch(self):
        '''
        Test the report when both parent company and its branches are selected
        - Parent company should be used for minor amount rows
        - the report should contain data from both company and branch
        '''
        branch_company = self.branch_company
        parent_company = self.company
        sale_tax = self.env.ref(f"account.{parent_company.id}_l10n_co_tax_8")
        # Minor amounts
        self._create_move(parent_company, 'out_invoice', self.consumidor_final_partner, 67, tax=sale_tax)
        self._create_move(branch_company, 'out_refund', self.consumidor_final_partner, 2000, tax=sale_tax)
        data = self._get_report_csv_data('1005', [parent_company, branch_company])
        self.assertEqual(len(data), 2, 'Expected 2 lines in csv file for report 1009')
        self.assertEqual(
            data[1:],
            [
                ['43', '222222222', '', '', '', '', '', 'CUANTIAS MENORES', '13.0', '380.0', '0.0'],
            ],
            'CSV output does not match expected output'
        )

    def test_10_no_exog_report_data(self):
        '''
        Test for error when there's no exogenous report data to export
        '''
        with self.assertRaises(ValidationError):
            self._get_report_csv_data('1009')

    def test_11_multiple_companies_selected(self):
        '''
        Test for error when multiple companies are selected
        '''
        unimportant_company = self._create_company(name='Unimportant Company')
        with self.assertRaises(UserError):
            options = self._generate_options(self.general_ledger_report, date(2026, 1, 1), date(2026, 1, 31))
            options['companies'] = [{'name': company.name, 'id': company.id, 'currency_id': company.currency_id.id} for company in [unimportant_company, self.company]]
            self.general_ledger_report_handler.l10n_co_reports_open_exogenous_report_wizard(options)

    def test_12_validate_allowed_accounts(self):
        '''
        Test for error when an account with the wrong type is added to a 1008 or 1009 config
        '''
        expense_account_id = self.env.ref(f"account.{self.company.id}_co_puc_511000").id
        with self.assertRaises(ValidationError):
            self.env.ref('l10n_co_reports.exogenous_config_1009_01_2201_balance').account_ids = [(4, expense_account_id)]
        with self.assertRaises(ValidationError):
            self.env.ref('l10n_co_reports.exogenous_config_1008_01_1317_balance').account_ids = [(4, expense_account_id)]
