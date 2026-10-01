import csv
import io
import zipfile

from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nTrELedgerExport(TestAccountReportsCommon):
    """The e-Ledger is filed monthly but numbered per fiscal period: LineNumber starts at 1 on the
    first journal item of the fiscal year and runs unbroken until its end."""

    @classmethod
    @TestAccountReportsCommon.setup_chart_template('tr')
    def setUpClass(cls):
        super().setUpClass()

        cls.report = cls.env.ref('account_reports.general_ledger_report')
        cls.handler = cls.env[cls.report.custom_handler_model_name]

        columns = cls.handler._l10n_tr_reports_csv_columns()
        cls.line_number_col = columns.index('LineNumber')
        cls.entry_number_col = columns.index('EntryNumber')
        cls.entry_counter_col = columns.index('EntryNumberCounter')

        # Created out of chronological order on purpose: the export must order by date, not by id.
        # The 2023 invoice lies outside every 2024 range below, it only serves the fiscal year test.
        cls.moves = cls.env['account.move']
        for invoice_date in ('2024-03-05', '2024-01-10', '2023-11-15', '2024-02-07', '2024-01-25'):
            cls.moves |= cls.init_invoice(
                'out_invoice',
                invoice_date=invoice_date,
                amounts=[100.0],
                taxes=[],  # keeps every move at two journal items, so row counts are predictable
                post=True,
            )

    def _export_rows(self, date_from, date_to):
        """Return the rows of the e-Ledger CSV exported for a date range, header excluded."""
        options = self._generate_options(self.report, date_from, date_to)
        file_content = self.handler.l10n_tr_reports_export_general_ledger_csv(options)['file_content']
        file_name = self.handler._l10n_tr_reports_format_file_name(options['date'])
        with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
            self.assertEqual(archive.namelist(), [f'{file_name}.csv'])
            csv_content = archive.read(f'{file_name}.csv')

        rows = list(csv.reader(io.StringIO(csv_content.decode()), delimiter=';'))
        self.assertEqual(rows[0], self.handler._l10n_tr_reports_csv_columns())
        return rows[1:]

    def _line_numbers(self, rows):
        return [row[self.line_number_col] for row in rows]

    def test_line_number_runs_unbroken_over_the_fiscal_period(self):
        """Monthly exports number from 1 at the start of the fiscal year and never restart."""
        offset = 0
        for date_from, date_to in (
            ('2024-01-01', '2024-01-31'),
            ('2024-02-01', '2024-02-29'),
            ('2024-03-01', '2024-03-31'),
        ):
            with self.subTest(period=date_from):
                rows = self._export_rows(date_from, date_to)

                self.assertTrue(rows, "the monthly export should not be empty")
                self.assertEqual(
                    self._line_numbers(rows),
                    [str(number) for number in range(offset + 1, offset + len(rows) + 1)],
                )
                offset += len(rows)

    def test_entries_are_numbered_from_the_oldest(self):
        """The rows follow the entry dates, and the move counter follows the rows."""
        rows = self._export_rows('2024-01-01', '2024-12-31')
        moves = self.moves.filtered(lambda move: move.date.year == 2024).sorted(lambda move: (move.date, move.name))

        self.assertEqual(self._line_numbers(rows)[0], '1')
        self.assertEqual(
            [row[self.entry_number_col] for row in rows],
            [move.name for move in moves for _line in move.line_ids],
        )
        # The counter identifies the move, so it is shared by its journal items and starts at the oldest.
        self.assertEqual(
            [int(row[self.entry_counter_col]) for row in rows],
            [counter for counter, move in enumerate(moves, start=1) for _line in move.line_ids],
        )

    def test_line_number_follows_the_fiscal_year_not_the_calendar_year(self):
        """The offset is counted from the start of the fiscal year, wherever the company sets it."""
        self.env.company.fiscalyear_last_day = 30
        self.env.company.fiscalyear_last_month = '6'  # fiscal year running from July to June

        previous_rows = self._export_rows('2023-07-01', '2023-12-31')
        rows = self._export_rows('2024-01-01', '2024-01-31')

        self.assertEqual(self._line_numbers(previous_rows)[0], '1')
        self.assertEqual(self._line_numbers(rows)[0], str(len(previous_rows) + 1))

    def test_csv_row_line_number_is_optional(self):
        """Overrides written against the previous signature of the row builder keep working."""
        row = self.handler._prepare_l10n_tr_reports_csv_row(self.moves[0].line_ids[0], 1)

        self.assertIsNone(row[self.line_number_col])
