# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestBaseImport(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        coa_file = "account_base_import/static/src/xls/coa_import.xlsx"
        coa_file_with_code_mapping = "account_base_import/static/src/csv/coa_import_with_code_mapping.csv"
        coa_file_with_code_mapping_and_no_code = "account_base_import/static/src/csv/coa_import_with_code_mapping_and_no_code.csv"
        journal_items_file = "account_base_import/static/src/xls/journal_items_import.xlsx"
        duplicate_journals_file = "account_base_import/static/src/xls/duplicate_journals_import.xlsx"
        cls.coa_file_content = cls.file_read(coa_file)
        cls.coa_file_with_code_mapping_content = cls.file_read(coa_file_with_code_mapping)
        cls.coa_file_with_code_mapping_and_no_code_content = cls.file_read(coa_file_with_code_mapping_and_no_code)
        cls.journal_items_file_content = cls.file_read(journal_items_file)
        cls.duplicate_journals_file_content = cls.file_read(duplicate_journals_file)

    def _create_save_import(self, res_model, file, companies=None, is_csv=False):
        if companies is None:
            companies = self.env.company

        import_wizard = self.env["base_import.import"].with_context(allowed_company_ids=companies.ids).create({
            "res_model": res_model,
            "file": file,
            "file_type": "application/vnd.ms-excel" if not is_csv else "text/csv",
        })
        preview = import_wizard.parse_preview({
            "has_headers": True,
            "quoting": '"',
        })
        preview["options"]["name_create_enabled_fields"] = {
            "journal_id": True,
            "account_id": True,
            "partner_id": True,
        }

        return import_wizard.with_context(allowed_company_ids=companies.ids).execute_import(
            preview["headers"],
            preview["headers"],
            preview["options"]
        )

    def _create_records(self, res_model, amount=1):
        vals = []
        for i in range(amount):
            match res_model:
                case 'account.account':
                    vals.append({'code': f"9999{i}", 'name': f"Test Account {i}"})
                case 'account.journal':
                    vals.append({'code': f"TBNK{i}", 'name': f"Test Journal {i}", 'type': 'bank'})
                case 'account.move':
                    vals.append({'move_type': 'entry', 'name': f"Test Move {i}"})
                case 'res.partner':
                    vals.append({'name': f"Test Partner {i}"})
                case 'account.tax':
                    vals.append({'name': f"Test Tax {i}"})
                case _:
                    raise
        return self.env[res_model].create(vals)

    def test_account_xlsx_import(self):
        existing_id = self.env["account.account"].with_context(import_file=True).create({"code":"550003", "name": "Existing Account"}).id

        result = self._create_save_import("account.account", self.coa_file_content)
        self.cr.precommit.run()
        self.env.company.account_opening_move_id.action_post()

        self.assertEqual(result["messages"], [], "The import should have been successful without error")

        existing_account = self.env["account.account"].browse(existing_id)
        self.assertEqual(len(result["ids"]), 14, "14 Accounts should have been imported")
        self.assertEqual(existing_account.name, "Bank", "The existing account should have been updated")
        self.assertEqual(existing_account.current_balance, -3500.0, "The balance should have been updated")

    def test_account_xlsx_import_fresh_company(self):
        """ Test importing new accounts in a fresh company with nothing but a MISC journal. """
        new_company = self.env['res.company'].create({'name': 'New Test Company'})

        self.env['account.journal'].create({
            'name': 'Miscellaneous',
            'code': 'MISC',
            'type': 'general',
            'company_id': new_company.id,
        })

        result = self._create_save_import('account.account', self.coa_file_content, companies=new_company)
        self.cr.precommit.run()
        new_company.account_opening_move_id.action_post()

        self.assertEqual(result['messages'], [], "The import should have been successful without error")
        self.assertEqual(len(result['ids']), 14, "14 Accounts should have been imported")

        bank_account = self.env['account.account'].with_company(new_company).search([
            *self.env['account.account']._check_company_domain(new_company),
            ('code', '=', '550003'),
        ])
        self.assertRecordValues(bank_account, [{
            'name': "Bank",
            'current_balance': -3500,
        }])

        # Check that there are now 15 accounts in the company: 14 imported + the unaffected earnings account.
        num_accounts = self.env['account.account'].with_company(new_company).search_count([
            *self.env['account.account']._check_company_domain(new_company),
        ])
        self.assertEqual(num_accounts, 15)

    def test_account_csv_import_with_code_mapping(self):
        # Create other companies referenced in the imported XLSX
        company_2, company_3 = self.env['res.company'].create([
            {'name': 'Company 2'},
            {'name': 'Company 3'},
        ])

        existing_id = self.env['account.account'].with_context(import_file=True).create({'code': '550003', 'name': "Existing Account"}).id

        result = self._create_save_import('account.account', self.coa_file_with_code_mapping_content, is_csv=True)
        self.assertEqual(result['messages'], [], "The import should have been successful without error")
        self.assertEqual(len(result['ids']), 14, "14 Accounts should have been imported")

        first_account = self.env['account.account'].browse(result['ids'][0])
        self.assertRecordValues(first_account, [{
            'company_ids': self.company_data['company'].ids,
            'code': '100000',
        }])
        self.assertRecordValues(first_account.with_company(company_2.id), [{'code': '100001'}])
        self.assertRecordValues(first_account.with_company(company_3.id), [{'code': '100002'}])

        existing_account = self.env['account.account'].browse(existing_id)
        self.assertEqual(existing_account.name, "Bank", "The existing account should have been updated")
        self.assertRecordValues(existing_account.with_company(company_2.id), [{'code': '550004'}])
        self.assertRecordValues(existing_account.with_company(company_3.id), [{'code': '550005'}])

    def test_account_csv_import_with_code_mapping_and_no_code(self):
        # Create other companies referenced in the imported XLSX
        company_2 = self.env['res.company'].create([{'name': "Company 2"}])

        result = self._create_save_import(
            'account.account',
            self.coa_file_with_code_mapping_and_no_code_content,
            companies=(self.company_data['company'] | company_2),
            is_csv=True,
        )
        self.assertEqual(result['messages'], [], "The import should have been successful without error")
        self.assertEqual(len(result['ids']), 15, "15 Accounts should have been imported")

        first_account = self.env['account.account'].browse(result['ids'][0])
        self.assertRecordValues(first_account, [{
            'company_ids': (self.company_data['company'] | company_2).ids,
            'code': '100000',
        }])
        self.assertRecordValues(first_account.with_company(company_2.id), [{'code': '100001'}])

    def test_account_move_line_xlsx_import(self):
        result = self._create_save_import("account.move.line", self.journal_items_file_content)

        account_move_lines = self.env["account.move.line"].browse(result["ids"])
        self.assertEqual(len(account_move_lines.mapped("move_id").ids), 4, "4 moves should have been created")
        self.assertEqual(account_move_lines.mapped("journal_id.code"), ["MISC", "SAL", "BNK1"], "The journals should be set correctly")
        self.assertEqual(account_move_lines.mapped("account_id.code"), ["700200", "400000", "455000", "620200"], "The accounts should be set correctly")
        account_move_lines.move_id.action_post()
        self.assertTrue(account_move_lines.full_reconcile_id)

    def test_duplicate_journals_import(self):
        existing_journal = self.env["account.journal"].with_context(import_file=True).create({"name": "OD26_18"})
        self.assertEqual(existing_journal.code, 'OD26_18')

        result = self._create_save_import("account.move.line", self.duplicate_journals_file_content)

        account_move_lines = self.env["account.move.line"].browse(result["ids"])
        self.assertEqual(len(account_move_lines.mapped("move_id").ids), 3, "3 moves should have been created")
        self.assertEqual(sorted(account_move_lines.mapped("journal_id.code")), ["OD26_19", "OD_BLABLA", "OD_BLABLU"], "The journals should be set correctly")

    def test_import_summary_fields(self):
        import_summary = self.env['account.import.summary'].create({
            'import_summary_account_ids': self._create_records('account.account', 3),
            'import_summary_journal_ids': self._create_records('account.journal', 5),
            'import_summary_move_ids': self._create_records('account.move', 2),
            'import_summary_partner_ids': self._create_records('res.partner', 4),
            'import_summary_tax_ids': self._create_records('account.tax', 6),
        })
        self.assertRecordValues(import_summary, [{
            'import_summary_len_account': 3,
            'import_summary_len_journal': 5,
            'import_summary_len_move': 2,
            'import_summary_len_partner': 4,
            'import_summary_len_tax': 6,
            'import_summary_have_data': True,
        }])

    def test_import_summary_have_data(self):
        import_summary = self.env['account.import.summary'].create({})
        self.assertFalse(import_summary.import_summary_have_data)
        import_summary = self.env['account.import.summary'].create({'import_summary_move_ids': self._create_records('account.move')})
        self.assertTrue(import_summary.import_summary_have_data)

    def test_journal_name_preserved_on_import(self):
        """Test that existing journal names are not overwritten when importing journal items."""
        misc_journal = self.env["account.journal"].search([('code', '=', 'MISC'), ('company_id', '=', self.env.company.id)], limit=1)
        original_name = misc_journal.name

        result = self._create_save_import("account.move.line", self.journal_items_file_content)

        misc_journal.invalidate_recordset()
        self.assertEqual(misc_journal.name, original_name, "Existing journal name should not be overwritten")
        self.assertEqual(result["messages"], [], "The import should have been successful without error")
