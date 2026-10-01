# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo.tests import Command, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nCoReportsLibroDiario(TestAccountReportsCommon):
    @classmethod
    @TestAccountReportsCommon.setup_country('co')
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('l10n_co_reports.l10n_co_reports_libro_diario')

    def _get_libro_diario_sort_key(self, line):
        # Only date is guaranteed by the report; move_id/balance just make the test reproducible.
        line_id = self.report._get_model_info_from_id(line.id)[1]
        move_line = self.env['account.move.line'].browse(line_id)
        return (move_line.date, move_line.move_id.id, move_line.balance)

    def test_libro_diario_includes_entries_without_partner(self):
        """
        Journal entries without a partner (e.g. misc operations, payroll, bank fees, opening
        balance) must appear alongside invoices/bills, and must not break the column headers.
        """
        misc_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.company_data['default_journal_misc'].id,
            'date': '2025-01-03',
            'line_ids': [
                Command.create({'account_id': self.company_data['default_account_revenue'].id, 'credit': 100.0}),
                Command.create({'account_id': self.company_data['default_account_expense'].id, 'debit': 100.0}),
            ],
        })
        invoice = self._create_invoice_one_line(price_unit=300, invoice_date='2025-01-02')
        bill = self._create_invoice_one_line(price_unit=200, move_type='in_invoice', invoice_date='2025-01-01')
        (misc_move + invoice + bill).action_post()

        options = self._generate_options(self.report, '2025-01-01', '2025-01-03')
        lines = self.report._get_lines(options)
        lines.sort(key=self._get_libro_diario_sort_key, reverse=True)

        # Check the labels are correct, as a None value on line 0 makes the header disappear
        # (header.js matches columns back to their header by column_group_index/expression_label)
        expected_expression_labels = [c['expression_label'] for c in options['columns']]
        for line in lines:
            self.assertEqual(
                [column.expression_label for column in line.columns],
                expected_expression_labels,
            )

        # DATE, MOVE, (ACCOUNT), PARTNER, (LABEL), DEBIT, CREDIT
        self.assertLinesValues(
            lines,
            [1, 2, 4, 6, 7],
            [
                # Sorted by date DESC; ties within a move are broken by balance for reproducibility
                # only (see _get_libro_diario_sort_key) - the report itself makes no such guarantee.
                ('01/03/2025', misc_move.name,   '',                  100.0,    0.0),
                ('01/03/2025', misc_move.name,   '',                    0.0,  100.0),
                ('01/02/2025', invoice.name,     self.partner_a.name, 300.0,    0.0),
                ('01/02/2025', invoice.name,     self.partner_a.name,   0.0,  300.0),
                ('01/01/2025', bill.name,        self.partner_a.name, 200.0,    0.0),
                ('01/01/2025', bill.name,        self.partner_a.name,   0.0,  200.0),
            ],
            options,
        )

    def test_libro_diario_multiple_column_groups_union(self):
        """
        The UNION ALL query must not error out with more than one column group (e.g. period
        comparison), forced here since filter_period_comparison is off by default on this report.
        """
        move = self._create_invoice_one_line(price_unit=500, invoice_date='2025-01-15')
        move.action_post()

        self.report.filter_period_comparison = True
        options = self._generate_options(
            self.report, '2025-01-01', '2025-01-31',
            default_options={'comparison': {'filter': 'previous_period', 'number_period': 1}},
        )
        self.assertEqual(len(options['column_groups']), 2)
        lines = self.report._get_lines(options)
        self.assertTrue(lines)
