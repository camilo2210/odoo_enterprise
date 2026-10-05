# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo import fields
from odoo.fields import Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.l10n_ar.tests.common import TestArCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestArDailyBook(TestArCommon, TestAccountReportsCommon):
    """ Tests for the Argentinian "Daily Book" (Libro Diario) XLSX export built on
    top of the General Ledger report. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Scope the report to a single company so the options (and thus the export) are not
        # polluted by the other companies set up by the report/AR test commons.
        cls.report = cls.env.ref('account_reports.general_ledger_report').with_context(
            allowed_company_ids=cls.company_ri.ids)
        cls.report_handler = cls.env['account.general.ledger.report.handler']

        cls.account_x = cls.company_data['default_account_revenue']   # shared account
        cls.account_y = cls.company_data['default_account_expense']

        # Journal group configuration
        cls.group_sales = cls.env['account.journal.group'].create({'name': 'Sales (Test)'})
        cls.journal_a = cls._create_journal('Sales A', 'DBTA', cls.group_sales)
        cls.journal_b = cls._create_journal('Sales B', 'DBTB', cls.group_sales)
        cls.journal_c = cls._create_journal('Misc', 'DBTC', journal_group=False)

        # Grouped journals A and B, both posting to Account X in January -> one summary entry.
        cls._post_move(cls.journal_a, '2026-01-15', debit=cls.account_y, credit=cls.account_x, amount=100.0)
        cls._post_move(cls.journal_b, '2026-01-20', debit=cls.account_y, credit=cls.account_x, amount=60.0)
        # Ungrouped journal C -> one detailed entry, kept on its own.
        cls._post_move(cls.journal_c, '2026-01-10', debit=cls.account_y, credit=cls.account_x, amount=30.0)

        cls.options = cls._generate_options(
            cls.report,
            fields.Date.from_string('2026-01-01'),
            fields.Date.from_string('2026-01-31'),
        )
        cls.company_ri.l10n_ar_daily_book_start_entry_number = 5

    @classmethod
    def _create_journal(cls, name, code, journal_group):
        return cls.env['account.journal'].create({
            'name': name,
            'code': code,
            'type': 'general',
            'company_id': cls.company_ri.id,
            'journal_group_id': journal_group and journal_group.id,
        })

    @classmethod
    def _post_move(cls, journal, move_date, debit, credit, amount):
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'company_id': cls.company_ri.id,
            'date': move_date,
            'partner_id': cls.partner_a.id,
            'line_ids': [
                Command.create({'account_id': debit.id, 'debit': amount, 'credit': 0.0}),
                Command.create({'account_id': credit.id, 'debit': 0.0, 'credit': amount}),
            ],
        })
        move.action_post()
        return move

    def _get_entries(self):
        company = self.report._get_sender_company_for_export(self.options)
        domain = self.report._get_options_domain(self.options, 'strict_range')
        start = company.l10n_ar_daily_book_start_entry_number
        return self.report_handler._l10n_ar_reports_get_daily_book_entries(company, domain, start)

    def _get_entry_lines(self, entry, account):
        code = account.with_company(self.company_ri).code
        return [line for line in entry['lines'] if line['account_code'] == code]

    # ------------------------------------------------------------------
    # Entry building
    # ------------------------------------------------------------------
    def test_entries_summary_and_detail_split(self):
        """ Test that grouped journals collapse into a monthly summary while ungrouped stays detailed. """
        entries = self._get_entries()
        # 1 summary entry (group Ventas / January) + 1 detail entry (journal C move).
        self.assertEqual(len(entries), 2)

        detail_entry, summary_entry = entries  # sorted by date: Jan 10 then Jan 31
        # The detail entry keeps the move date; the summary is stamped on the month's last day.
        self.assertEqual(detail_entry['date'], date(2026, 1, 10))
        self.assertEqual(summary_entry['date'], date(2026, 1, 31))
        self.assertEqual(summary_entry['description'], self.group_sales.name)

    def test_summary_entry_aggregates(self):
        """ Test that account X used by both grouped journals appears once with the summed amounts. """
        summary_entry = self._get_entries()[1]

        x_lines = self._get_entry_lines(summary_entry, self.account_x)
        self.assertEqual(len(x_lines), 1, "Account X must appear exactly once in the summary")
        self.assertEqual(x_lines[0]['credit'], 160.0)  # 100 + 60
        self.assertEqual(x_lines[0]['debit'], 0.0)

        y_lines = self._get_entry_lines(summary_entry, self.account_y)
        self.assertEqual(len(y_lines), 1)
        self.assertEqual(y_lines[0]['debit'], 160.0)

    def test_detail_entry(self):
        """ Test that the ungrouped journal move is exported as its own entry with its own lines. """
        detail_entry = self._get_entries()[0]
        self.assertEqual(len(detail_entry['lines']), 2)
        self.assertEqual(self._get_entry_lines(detail_entry, self.account_x)[0]['credit'], 30.0)
        self.assertEqual(self._get_entry_lines(detail_entry, self.account_y)[0]['debit'], 30.0)

    def test_entry_number_sequencing(self):
        """ Test that entries get an unbroken sequence starting at the company's start number. """
        entries = self._get_entries()
        self.assertEqual([e['sequence'] for e in entries], [5, 6])

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def test_diary_book_export(self):
        """ Tests that the export works."""
        result = self.report_handler.l10n_ar_reports_export_daily_book(self.options)
        self.assertEqual(result['file_type'], 'xlsx')
        self.assertTrue(result['file_content'], "The generated file should not be empty")
        # XLSX files are zip archives and starts with the "PK" magic bytes.
        self.assertEqual(result['file_content'][:2], b'PK')

    # ------------------------------------------------------------------
    # Entry numbering
    # ------------------------------------------------------------------
    def test_export_advances_start_entry_number(self):
        """ Test that generating the export moves the company's start number past the last entry. """
        self.report_handler.l10n_ar_reports_export_daily_book(self.options)
        # start=5 with two entries -> sequences 5 and 6 --> next export starts at 7.
        self.assertEqual(self.company_ri.l10n_ar_daily_book_start_entry_number, 7)

    def test_start_entry_number_default(self):
        """ Test that a company that never generated a Daily Book starts numbering at 1. """
        company = self.env['res.company'].create({'name': 'AR Co Without History'})
        self.assertEqual(company.l10n_ar_daily_book_start_entry_number, 1)

    def test_export_on_branch_same_cuit(self):
        """ Test that a branch sharing its parent's CUIT files the Daily Book under the parent.
        It should use the parent's entry numbering and advances the parent's counter, while
        the branch's own counter stays untouched. """
        # Create branch with same CUIT as parent
        branch = self.env['res.company'].create({
            'name': 'RI Branch',
            'parent_id': self.company_ri.id,
            'country_id': self.company_ri.country_id.id,
            'currency_id': self.company_ri.currency_id.id,
        })
        branch.account_fiscal_country_id = self.company_ri.account_fiscal_country_id
        branch.partner_id.write({
            'vat': self.company_ri.partner_id.vat,
        })

        # Create a move for detailed entry to export
        branch_journal = self.env['account.journal'].create({
            'name': 'Branch Misc',
            'code': 'DBBR',
            'type': 'general',
            'company_id': branch.id,
        })
        self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': branch_journal.id,
            'company_id': branch.id,
            'date': '2026-01-12',
            'partner_id': self.partner_a.id,
            'line_ids': [
                Command.create({'account_id': self.account_y.id, 'debit': 25.0, 'credit': 0.0}),
                Command.create({'account_id': self.account_x.id, 'debit': 0.0, 'credit': 25.0}),
            ],
        }).action_post()

        # Options scoped to the branch alone (its own journals, so its move is in range).
        branch_report = self.report.with_context(allowed_company_ids=branch.ids)
        branch_options = self._generate_options(
            branch_report,
            fields.Date.from_string('2026-01-01'),
            fields.Date.from_string('2026-01-31'),
        )

        self.assertEqual(
            branch_report._get_sender_company_for_export(branch_options)._l10n_ar_reports_get_daily_book_company(),
            self.company_ri,
        )

        self.company_ri.l10n_ar_daily_book_start_entry_number = 42

        # The branch's single entry is numbered from the parent's start (42), advancing it to 43.
        self.report_handler.l10n_ar_reports_export_daily_book(branch_options)
        self.assertEqual(self.company_ri.l10n_ar_daily_book_start_entry_number, 43)
        self.assertEqual(branch.l10n_ar_daily_book_start_entry_number, 1)

    # ------------------------------------------------------------------
    # Guard rails
    # ------------------------------------------------------------------
    def test_export_rejected(self):
        """ Test that companies filing under different CUITs cannot share one Daily Book. """
        mixed_options = {'companies': [
            {'id': self.company_ri.id},
            {'id': self.company_mono.id},
        ]}
        with self.assertRaises(UserError):
            self.report_handler._l10n_ar_reports_check_daily_book_export(mixed_options)
