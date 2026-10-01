# -*- coding: utf-8 -*-
import csv
import itertools
import zipfile
from io import BytesIO, TextIOWrapper, StringIO

from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import tagged, Form
from odoo.addons.account.tests.common import AccountTestInvoicingCommon



@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDatevCSV(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template('de_skr03')
    def setUpClass(cls):
        super().setUpClass()

        cls.account_3400 = cls.env['account.account'].search([
            ('code', '=', 3400),
            ('company_ids', '=', cls.company_data['company'].id),
        ], limit=1)
        cls.account_4980 = cls.env['account.account'].search([
            ('code', '=', 4980),
            ('company_ids', '=', cls.company_data['company'].id),
        ], limit=1)
        cls.account_1500 = cls.env['account.account'].search([
            ('code', '=', 1500),
            ('company_ids', '=', cls.company_data['company'].id),
        ], limit=1)
        cls.tax_19 = cls.env['account.tax'].search([
            ('name', '=', '19% I'),
            ('company_id', '=', cls.company_data['company'].id),
        ], limit=1)
        cls.tax_7 = cls.env['account.tax'].search([
            ('name', '=', '7% I'),
            ('company_id', '=', cls.company_data['company'].id),
        ], limit=1)

    def _setup_three_currency_test(self, date='2020-12-01'):
        usd = self.setup_other_currency('USD', rates=[(date, 50)])
        aed = self.setup_other_currency('AED', rates=[(date, 30)])
        bank_journal = self.env['account.journal'].create({
            'name': 'Three Currency Bank',
            'code': '3CUR',
            'type': 'bank',
            'currency_id': aed.id,
            'company_id': self.company_data['company'].id,
        })

        return {
            'usd': usd,
            'aed': aed,
            'bank_journal': bank_journal,
            'bank_account': bank_journal.default_account_id,
            'ar_account': self.company_data['default_account_receivable'],
            'ap_account': self.company_data['default_account_payable'],
        }

    def _create_three_currency_transaction(self, journal_id, amount, invoice_values, date='2020-12-01'):
        statement = self.env['account.bank.statement'].create({
            'line_ids': [
                Command.create({
                    'journal_id': journal_id,
                    'date': date,
                    'amount': amount,
                    'payment_ref': 'Three currency test',
                    'partner_id': self.partner_a.id,
                }),
            ],
        })
        arap_lines = self.env['account.move.line']

        for values in invoice_values:
            invoice = self._create_invoice_one_line(
                move_type=values['move_type'],
                currency_id=values['currency_id'],
                invoice_date=date,
                price_unit=values['price_unit'],
                tax_ids=[],
                post=True,
            )
            arap_lines |= invoice.line_ids.filtered(
                lambda line: line.account_id.account_type in (
                    'asset_receivable',
                    'liability_payable',
                )
            )

        statement.line_ids.set_line_bank_statement_line(arap_lines.ids)

        return statement.line_ids.move_id

    def test_datev_in_invoice(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'date': fields.Date.to_date('2020-12-01'),
            'ref': 'Brocken123',
            'invoice_line_ids': [
                (0, None, {
                    'name': 'Line Number 1',
                    'price_unit': 100,
                    'account_id': self.account_3400.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
                (0, None, {
                    'name': 'Line Number 2',
                    'price_unit': 100,
                    'account_id': self.account_3400.id,
                    'tax_ids': [],
                }),
                (0, None, {
                    'name': 'Line Number 3',
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()
        move.line_ids.flush_recordset()

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(3, len(data), "csv should have 3 lines")
        self.assertIn(['119,00', 'S', 'EUR', '34000000', str(move.partner_id.id + 700000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[0].name], data)
        self.assertIn(['100,00', 'S', 'EUR', '34000000', str(move.partner_id.id + 700000000),
                       '', '112', move.name, move.invoice_line_ids[1].name], data)
        self.assertIn(['119,00', 'S', 'EUR', '49800000', str(move.partner_id.id + 700000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[2].name], data)

    def test_datev_in_receipt(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'in_receipt',
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'date': fields.Date.to_date('2020-12-01'),
            'ref': 'Brocken123',
            'invoice_line_ids': [Command.create({
                    'name': 'Line Number 1',
                    'price_unit': 100,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
                Command.create({
                    'name': 'Line Number 2',
                    'price_unit': 100,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
                Command.create({
                    'name': 'Line Number 3',
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()
        move.line_ids.flush_recordset()

        account = move.l10n_de_datev_main_account_id
        with zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r') as zf:
            reader = csv.reader(TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8"), delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:][::-1]
        self.assertCountEqual([
            ['119,00', 'S', 'EUR', '34000000', str(account.code).ljust(8, '0'), self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[0].name],
            ['119,00', 'S', 'EUR', '34000000', str(account.code).ljust(8, '0'), self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[1].name],
            ['119,00', 'S', 'EUR', '49800000', str(account.code).ljust(8, '0'), self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[2].name],
        ], data)

    def test_datev_out_invoice(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                (0, None, {
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()
        move.line_ids.flush_recordset()

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(1, len(data), "csv should have 1 line")
        self.assertIn(['119,00', 'H', 'EUR', '49800000', str(move.partner_id.id + 100000000),
                      self.tax_19.l10n_de_datev_code, '112', move.name, move.name], data)

    def test_datev_miscellaneous(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2020-12-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {
                    'debit': 100,
                    'credit': 0,
                    'partner_id': self.partner_a.id,
                    'account_id': self.account_4980.id,
                }),
                (0, 0, {
                    'debit': 0,
                    'credit': 100,
                    'partner_id': self.partner_a.id,
                    'account_id': self.account_3400.id,
                    'tax_ids': [],
                }),
            ]
        })
        move.action_post()
        move.line_ids.flush_recordset()

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(1, len(data), "csv should have 1 lines")
        self.assertIn(['100,00', 'H', 'EUR', '34000000', '49800000', '112', move.name, move.name], data)

    def test_datev_out_invoice_payment(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                (0, None, {
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()

        pay = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'payment_date': fields.Date.to_date('2020-12-03'),
        })._create_payments()

        self.env.flush_all()

        debit_account_code = str(pay.payment_method_line_id.payment_account_id.code).ljust(8, '0')

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(2, len(data), "csv should have 2 lines")
        self.assertIn(['119,00', 'H', 'EUR', '49800000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.name], data)
        self.assertIn(['119,00', 'H', 'EUR', str(move.partner_id.id + 100000000), debit_account_code, '', '312',
                       pay.name, pay.move_id.line_ids[0].name], data)

    def test_datev_out_invoice_payment_same_account_counteraccount(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                (0, None, {
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()

        # set counter account = account
        bank_journal = self.company_data['default_journal_bank']
        bank_journal.inbound_payment_method_line_ids.payment_account_id = bank_journal.default_account_id

        pay = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'payment_date': fields.Date.to_date('2020-12-03'),
        })._create_payments()

        debit_account_code = str(bank_journal.default_account_id.code).ljust(8, '0')

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        self.addCleanup(zf.close)
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertEqual(2, len(data), "csv should have 2 lines")
        self.assertIn(['119,00', 'H', 'EUR', '49800000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.name], data)
        self.assertIn(['119,00', 'H', 'EUR', str(move.partner_id.id + 100000000), debit_account_code, '', '312',
                       pay.name, pay.move_id.line_ids[0].name], data)

    def test_datev_in_invoice_payment(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                (0, None, {
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()

        pay = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'payment_date': fields.Date.to_date('2020-12-03'),
        })._create_payments()

        self.env.flush_all()

        credit_account_code = str(pay.payment_method_line_id.payment_account_id.code).ljust(8, '0')
        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(2, len(data), "csv should have 2 lines")
        self.assertIn(['119,00', 'S', 'EUR', '49800000', str(move.partner_id.id + 700000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.name], data)
        self.assertIn(['119,00', 'S', 'EUR', str(move.partner_id.id + 700000000), credit_account_code, '', '312',
                       pay.name, pay.move_id.line_ids[0].name], data)

    def test_datev_bank_statement(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        statement = self.env['account.bank.statement'].create({
            'balance_end_real': 100.0,
            'line_ids': [
                (0, 0, {
                    'journal_id': self.company_data['default_journal_bank'].id,
                    'payment_ref': 'line1',
                    'amount': 100.0,
                    'date': '2020-01-01',
                }),
            ],
        })
        statement.line_ids.move_id.flush_recordset()

        suspense_account_code = str(self.env.company.account_journal_suspense_account_id.code).ljust(8, '0')
        bank_account_code = str(self.env.company.bank_journal_ids.default_account_id.code).ljust(8, '0')

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        self.addCleanup(zf.close)
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['100,00', 'H', 'EUR', suspense_account_code, bank_account_code, '101',
                       statement.line_ids[0].name, statement.line_ids[0].payment_ref], data)

    def test_datev_out_invoice_paid(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [(0, 0, {
                'price_unit': 100.0,
                'quantity': 1,
                'account_id': self.company_data['default_account_revenue'].id,
                'tax_ids': [],
            })],
        })
        move.action_post()

        statement = self.env['account.bank.statement'].create({
            'balance_end_real': 100.0,
            'line_ids': [
                (0, 0, {
                    'journal_id': self.company_data['default_journal_bank'].id,
                    'payment_ref': 'line_1',
                    'amount': 100.0,
                    'partner_id': self.partner_a.id,
                    'date': '2020-01-01',
                }),
            ],
        })

        receivable_line = move.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        statement.line_ids.set_line_bank_statement_line(receivable_line.id)

        bank_account_code = str(self.env.company.bank_journal_ids.default_account_id.code).ljust(8, '0')

        self.env.flush_all()
        file_dict = self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)
        zf = zipfile.ZipFile(BytesIO(file_dict['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(2, len(data), "csv should have 2 lines")
        self.assertIn(['100,00', 'H', 'EUR', str(self.company_data['default_account_revenue'].code).ljust(8, '0'),
                       str(100000000 + move.partner_id.id), '112', move.name, move.name], data)
        self.assertIn(['100,00', 'H', 'EUR', str(100000000 + move.partner_id.id), bank_account_code, '101',
                       statement.line_ids[0].name, statement.line_ids[0].line_ids[1].name], data)
        # 2nd line of the statement because it's the line without the bank account

    def test_datev_out_invoice_with_negative_amounts(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                (0, None, {
                    'name': 'Line Number 1',
                    'price_unit': 1000,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
                (0, None, {
                    'name': 'Line Number 2',
                    'price_unit': -1000,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
                (0, None, {
                    'name': 'Line Number 3',
                    'price_unit': 1000,
                    'quantity': -1,
                    'account_id': self.account_4980.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
                (0, None, {
                    'price_unit': 2000,
                    'account_id': self.account_1500.id,
                    'tax_ids': [(6, 0, self.tax_7.ids)],
                }),
                (0, None, {
                    'price_unit': 3000,
                    'account_id': self.account_3400.id,
                    'tax_ids': [(6, 0, self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()
        move.line_ids.flush_recordset()

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(5, len(data), "csv should have 5 line")
        self.assertIn(['1190,00', 'H', 'EUR', '49800000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[0].name], data)
        self.assertIn(['1190,00', 'S', 'EUR', '49800000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[1].name], data)
        self.assertIn(['1190,00', 'S', 'EUR', '49800000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[2].name], data)
        self.assertIn(['2140,00', 'H', 'EUR', '15000000', str(move.partner_id.id + 100000000),
                       self.tax_7.l10n_de_datev_code, '112', move.name, move.name], data)
        self.assertIn(['3570,00', 'H', 'EUR', '34000000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.name], data)

    def test_datev_miscellaneous_several_line_same_account(self):
        """
            Tests that if we have only a single account to the debit, we have a contra-account that is this account, and
            we can put all the credit lines against this account
        """
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        account_1600 = self.env['account.account'].search(
            [('code', '=', 1600), ('company_ids', '=', self.company_data['company'].id)], limit=1)

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2020-12-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {
                    'debit': 100,
                    'credit': 0,
                    'partner_id': self.partner_a.id,
                    'account_id': self.account_4980.id,
                }),
                (0, 0, {
                    'debit': 100,
                    'credit': 0,
                    'partner_id': self.partner_a.id,
                    'account_id': self.account_4980.id,
                }),
                (0, 0, {
                    'debit': 0,
                    'credit': 100,
                    'partner_id': self.partner_a.id,
                    'account_id': account_1600.id,
                }),
                (0, 0, {
                    'debit': 0,
                    'credit': 100,
                    'partner_id': self.partner_a.id,
                    'account_id': self.account_1500.id,
                }),
            ]
        })
        move.action_post()

        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[9], x[10], x[13]] for x in reader][2:]
        self.addCleanup(zf.close)
        self.assertEqual(2, len(data), "csv should have 2 lines")
        self.assertIn(['100,00', 'H', 'EUR', str(700000000 + self.partner_a.id), '49800000', '112', move.name, move.name], data)
        self.assertIn(['100,00', 'H', 'EUR', '15000000', '49800000', '112', move.name, move.name], data)

    def test_datev_all_aml_present(self):
        report = self.env.ref('account_reports.general_ledger_report')
        report.load_more_limit = 3
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        for _dummy in range(5):
            move = self.env['account.move'].create([{
                'move_type': 'out_invoice',
                'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
                'invoice_date': fields.Date.to_date('2020-12-01'),
                'invoice_line_ids': [
                    (0, None, {
                        'price_unit': 100,
                        'account_id': self.account_4980.id,
                        'tax_ids': [(6, 0, self.tax_19.ids)],
                    }),
                ]
            }])
            move.action_post()

        self.env.flush_all()
        zf = zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r')
        self.addCleanup(zf.close)
        f = TextIOWrapper(zf.open('EXTF_accounting_entries.csv'), "utf-8")
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = list(reader)
        self.assertEqual(7, len(data), "csv should have 5 (+2 header) lines")

    def test_datev_vat_export(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        partners_list = [
            {'name': 'partner1', 'vat': 'BE0897223670'},
            {'name': 'partner2'},
            {'name': 'partner3', 'vat': 'US12345671'},
            {'name': 'partner4', 'vat': ''},
            {'name': 'partner5', 'vat': 'NA'},
            {'name': 'partner6', 'vat': '1234567890'},
            {'name': 'partner7', 'vat': 'NL000099998B57'},
            {'name': 'partner8', 'vat': '/'},
            {'name': 'partner9', 'vat': '12AAAAA1234AAZA'},
            {'name': 'partner10', 'vat': 'EL123456783'},
            {'name': 'partner11', 'vat': 'EL123456783', 'country_id': self.ref('base.gr')},
            {'name': 'partner12', 'vat': 'BE0897223670', 'country_id': self.ref('base.ch')},
        ]
        partners = self.env['res.partner'].create(partners_list)

        move = self.env['account.move'].create([{
                'move_type': 'out_invoice',
                'invoice_date': fields.Date.to_date('2020-12-01'),
                'date': fields.Date.to_date('2020-12-01'),
                'partner_id': partner.id,
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Invoice Line',
                        'price_unit': 100,
                        'account_id': self.account_3400.id,
                        'tax_ids': [Command.set(self.tax_19.ids)],
                    }),
                ]
        } for partner in partners])
        move.action_post()

        with zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)['file_content']), 'r') as zf, \
                TextIOWrapper(zf.open('EXTF_customer_accounts.csv'), 'utf-8') as f:
            reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
            # first 2 rows are just headers and needn't be validated
            # first 2 columns are 'account' and 'name' and they are irrelevant to this test
            # column 19 'land' required for non DE
            data = [row[2:10] + [row[19]] for row in itertools.islice(reader, 2, None)]
            self.assertEqual(
                data,
                [
                    ["", "", "", "", "2", "", "BE", "0897223670", "BE"],
                    ["", "partner2", "", "", "1", "", "", "", ""],
                    ["", "", "", "", "2", "", "", "", "US"],
                    ["", "partner4", "", "", "1", "", "", "", ""],
                    ["", "partner5", "", "", "1", "", "", "", ""],
                    ["", "", "", "", "2", "", "", "", ""],
                    ["", "", "", "", "2", "", "NL", "000099998B57", "NL"],
                    ["", "partner8", "", "", "1", "", "", "", ""],
                    ["", "", "", "", "2", "", "", "", ""],
                    ["", "", "", "", "2", "", "EL", "123456783", "GR"],
                    ["", "", "", "", "2", "", "EL", "123456783", "GR"],
                    ["", "", "", "", "2", "", "BE", "0897223670", "CH"],
                ],
            )

    def test_datev_out_invoice_payment_epd_rounding(self):
        ''' Test epd rounding error correction is applied also when exporting
        in datev, in order to avoid a mismatch between stored and exported data
        '''
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        self.early_pay_2_percents_10_days = self.env['account.payment.term'].create({
            'name': '2% discount if paid within 10 days',
            'company_id': self.company_data['company'].id,
            'early_discount': True,
            'discount_percentage': 2,
            'discount_days': 10,
            'line_ids': [Command.create({
                'value': 'percent',
                'value_amount': 100,
                'nb_days': 30,
            })]
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_payment_term_id': self.early_pay_2_percents_10_days.id,
            'invoice_line_ids': [
                Command.create({
                    'quantity': 1.0,
                    'price_unit': 761.76,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
                Command.create({
                    'quantity': 1.0,
                    'price_unit': 100,
                    'tax_ids': [Command.set(self.tax_7.ids)],
                }),
                Command.create({
                    'quantity': 1.0,
                    'price_unit': 200,
                    'tax_ids': [],
                }),
            ]}])

        move.action_post()

        pay = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'payment_date': fields.Date.to_date('2020-12-03'),
        })._create_payments()

        debit_account_code = str(pay.payment_method_line_id.payment_account_id.code).ljust(8, '0')

        moves = move + pay.move_id
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, moves))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        epd_loss_account_code = str(self.env.company.account_journal_early_pay_discount_loss_account_id.code).ljust(8, '0')
        self.assertIn(['18,14', 'S', 'EUR', epd_loss_account_code, debit_account_code, self.tax_19.l10n_de_datev_code, '312', pay.name, pay.move_id.line_ids[2].name], data)
        self.assertIn(['2,13', 'S', 'EUR', epd_loss_account_code, debit_account_code, self.tax_7.l10n_de_datev_code, '312', pay.name, pay.move_id.line_ids[2].name], data)

    def test_datev_out_bank_payment_epd_rounding(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        self.early_pay_2_percents_10_days = self.env['account.payment.term'].create({
            'name': '2% discount if paid within 10 days',
            'company_id': self.company_data['company'].id,
            'early_discount': True,
            'discount_percentage': 2,
            'discount_days': 10,
            'line_ids': [Command.create({
                'value': 'percent',
                'value_amount': 100,
                'nb_days': 30,
            })]
        })

        move_1 = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_payment_term_id': self.early_pay_2_percents_10_days.id,
            'invoice_line_ids': [
                Command.create({
                    'quantity': 1.0,
                    'price_unit': 161.10,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
        ]}])
        move_2 = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_payment_term_id': self.early_pay_2_percents_10_days.id,
            'invoice_line_ids': [
                Command.create({
                    'quantity': 1.0,
                    'price_unit': 77.50,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
            ]}])

        moves = (move_1 | move_2)
        moves.action_post()

        # Create the payment statement
        statement = self.env['account.bank.statement'].create({
            'name': 'test_statement',
            'line_ids': [
                (0, 0, {
                    'journal_id': self.company_data['default_journal_bank'].id,
                    'date': '2020-12-02',
                    'payment_ref': 'test',
                    'amount': -278.27,
                    'partner_id': self.partner_a.id,
            })]
        })

        statement.line_ids.set_line_bank_statement_line(
            (
                move_1.line_ids.filtered(lambda x: x.account_id.account_type == 'liability_payable') +
                move_2.line_ids.filtered(lambda x: x.account_id.account_type == 'liability_payable')
            ).ids
        )
        payment_move = statement.line_ids.move_id
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, payment_move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        epd_gain_account_code = str(self.env.company.account_journal_early_pay_discount_gain_account_id.code).ljust(8, '0')
        self.assertIn(['3,83', 'H', 'EUR', epd_gain_account_code, '12010000', self.tax_19.l10n_de_datev_code, '212', payment_move.name, "Early Payment Discount"], data)
        self.assertIn(['1,84', 'H', 'EUR', epd_gain_account_code, '12010000', self.tax_19.l10n_de_datev_code, '212', payment_move.name, "Early Payment Discount"], data)

    @freeze_time('2021-01-02 18:00')
    def test_datev_out_invoice_with_attch(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Res Partner 12'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                Command.create({
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()
        self.env['account.move.send.wizard'] \
            .with_context(active_model='account.move', active_ids=move.ids) \
            .create({}).action_send_and_print()
        move.line_ids.flush_recordset()

        move_guid = move._l10n_de_datev_get_guid()

        with zipfile.ZipFile(BytesIO(self.env[report.custom_handler_model_name].l10_de_datev_export_to_zip_and_attach(options)['file_content']), 'r') as zf:
            xml = zf.open('document.xml').read()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        csv_data = list(reader)[2]

        self.assertEqual(f'BEDI "{move_guid}"', csv_data[19])

        # xml document is generated during tests because of an override in _hook_invoice_document_after_pdf_report_render
        expected_tree = f"""
        <archive xmlns="http://xml.datev.de/bedi/tps/document/v06.0"
                     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                     xsi:schemaLocation="http://xml.datev.de/bedi/tps/document/v06.0 Document_v060.xsd"
                     version="6.0"
                     generatingSystem="Odoo">
            <header>
                <date>2021-01-02T18:00:00</date>
            </header>
            <content>
                <document guid="{move_guid}" processID="1" type="2">
                    <extension xsi:type="File" name="INV-2020-00001.pdf"></extension>
                </document>
            </content>
        </archive>
        """

        self.assertXmlTreeEqual(self.get_xml_tree_from_string(xml), self.get_xml_tree_from_string(expected_tree))

    @freeze_time('2021-01-02 18:00')
    def test_datev_out_invoice_with_orphaned_attachment(self):
        """
        `message_main_attachment_id` may point to an attachment not linked to the
        move (`res_id=0`, `res_model=False`, e.g. an image uploaded by another user).
        Exporting as a plain accounting user (not manager, not system) must not raise
        an `AccessError`.
        """
        accountant = self.env['res.users'].create({
            'name': 'Accountant',
            'login': 'accountant',
            'group_ids': [Command.set([self.env.ref('account.group_account_user').id])],
        })

        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                Command.create({
                    'price_unit': 100,
                    'account_id': self.account_4980.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
            ]
        })
        move.action_post()

        move.message_main_attachment_id = self.env['ir.attachment'].create({
            'name': 'orphan.png',
            'mimetype': 'image/png',
            'raw': b'Fake Image',
        })
        # Access is only re-checked when fields are actually fetched from the DB; the ORM
        # cache is shared for the whole transaction, so without this the accountant would
        # transparently reuse the values already cached by the admin's create() above
        move.message_main_attachment_id.invalidate_recordset()

        self.env[report.custom_handler_model_name].with_user(accountant).l10_de_datev_export_to_zip_and_attach(options)

    def test_datev_out_invoice_with_included_tax(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })
        tax_19_incl = self.tax_19.copy({'name': 'Tax 19% incl.', 'price_include_override': 'tax_included'})

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Partner XYZ'}).id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 19.95,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(tax_19_incl.ids)],
                }),
            ]
        }])
        move.action_post()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['19,95', 'H', 'EUR', '34000000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[0].name], data)

    def test_datev_out_invoice_in_foreign_currency(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })
        tax_19_incl = self.tax_19.copy({'name': 'Tax 19% incl.', 'price_include_override': 'tax_included'})
        foreign_currency = self.env['res.currency'].create({
            'name': "XYZ",
            'symbol': 'X',
            'rate_ids': [
                Command.create({'name': '2020-01-01', 'rate': 0.5}),
            ],
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Partner XYZ'}).id,
            'currency_id': foreign_currency.id,
            'invoice_date': fields.Date.to_date('2020-12-01'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 100.00,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
                Command.create({
                    'name': 'Line with included tax',
                    'price_unit': 19.95,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(tax_19_incl.ids)],
                }),
            ]
        }])
        move.action_post()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['119,00', 'H', 'XYZ', '0,5', '238,00', 'EUR', '34000000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[0].name], data)
        self.assertIn(['19,95', 'H', 'XYZ', '0,5', '39,90', 'EUR', '34000000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[1].name], data)

    def test_datev_entry_in_foreign_currency(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })
        foreign_currency = self.env['res.currency'].create({
            'name': "XYZ",
            'symbol': 'X',
            'rate_ids': [
                Command.create({'name': '2020-01-01', 'rate': 0.5}),
            ],
        })

        move = self.env['account.move'].create([{
            'move_type': 'entry',
            'partner_id': self.env['res.partner'].create({'name': 'Partner XYZ'}).id,
            'date': fields.Date.to_date('2020-12-01'),
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                Command.create({
                    'name': 'Line',
                    'balance': 100.0,
                    'amount_currency': 50,
                    'account_id': self.account_4980.id,
                    'currency_id': foreign_currency.id,
                }),
                Command.create({
                    'name': 'Counterpart Line',
                    'balance': -100.0,
                    'amount_currency': -50.0,
                    'account_id': self.account_3400.id,
                    'tax_ids': [],
                    'currency_id': foreign_currency.id,
                }),
            ]
        }])
        move.action_post()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['50,00', 'H', 'XYZ', '0,5', '100,00', 'EUR', '34000000', '49800000',
                       '', '112', move.name, move.line_ids[1].name], data)

    def test_datev_miscellaneous_with_updated_credit_and_debit_in_aml(self):
        """
            Test that the datev exported values are correct when we update the
            credit and debit in aml of an miscellaneous move.
        """
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        options['date'].update({
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2020-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                Command.create({
                    'debit': 1000,
                    'credit': 0,
                    'account_id': self.account_4980.id,
                }),
                Command.create({
                    'debit': 0,
                    'credit': 1000,
                    'account_id': self.account_1500.id,
                }),
            ],
        })
        move.write({
            'line_ids': [
                Command.update(move.line_ids[0].id, {'debit': 3004}),
                Command.update(move.line_ids[1].id, {'credit': 3004}),
            ]
        })
        move.action_post()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[13]] for x in reader][2:]
        self.assertIn(['3004,00', move.name], data)

    def test_datev_select_receivable_payable_l10n_de_datev_main_account_id(self):
        """
        Test that when an entry contains both a revenue and a refund (like the ones generated by pos)
        The field l10n_de_datev_main_account_id is still populated
        """
        line_vals = [
            [self.company_data['default_account_revenue'].id, -100.0, self.tax_19.ids, 'Sale 19%'],
            [self.company_data['default_account_expense'].id, 50.0, self.tax_19.ids, 'Refund 19%'],
            [self.company_data['default_account_revenue'].id, -100.0, self.tax_7.ids, 'Sale 7%'],
            [self.company_data['default_account_expense'].id, 50.0, self.tax_7.ids, 'Refund 7%'],
            [self.company_data['default_account_receivable'].id, 113.0, False, ''],
        ]
        move = self.env['account.move'].create({
            'line_ids': [
                Command.create({
                    'account_id': account_id,
                    'debit': amount if amount > 0 else 0.0,
                    'credit': -amount if amount < 0 else 0.0,
                    'tax_ids': tax_ids,
                    'name': name,
                }) for account_id, amount, tax_ids, name in line_vals
            ]
        })
        self.assertEqual(move.l10n_de_datev_main_account_id, self.company_data['default_account_receivable'])

    @freeze_time('2021-01-02 18:00')
    def test_datev_company_name(self):
        """
        Test that DATEV report is exported succesfully even with complex company name
        """
        self.company_data['company'].name = 'Test Company GmbH & Co. AB'
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options({})
        vals = self.env[report.custom_handler_model_name].l10n_de_datev_export_to_zip(options)
        self.assertEqual(vals['file_name'], 'general_ledger_jan_2021_test_company_gmbh_&_co._ab_data.ZIP')

    def test_datev_in_invoice_total_tax_edited(self):
        """ Test that the correct amount is computed when the total of a tax group is edited manually """
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2020-12-01',
            'date_to': '2020-12-31'
        }})
        move = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Partner XYZ'}).id,
            'invoice_date': '2020-12-01',
            'date': '2020-12-01',
            'ref': 'Brocken123',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line 19% #1',
                    'price_unit': 100,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
                Command.create({
                    'name': 'Line 19% #2',
                    'price_unit': 200,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
                Command.create({
                    'name': 'Line 7%',
                    'price_unit': 100,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_7.ids)],
                }),
            ]
        }])
        with Form(move) as move_form:
            tax_totals = move.tax_totals
            tax_groups = tax_totals['subtotals'][0]['tax_groups']
            index = next(
                (i for i, data in enumerate(tax_groups)
                if data['id'] == self.tax_19.tax_group_id.id)
            )
            self.assertEqual(tax_totals['subtotals'][0]['tax_groups'][index]['tax_amount_currency'], 57.0)
            # remove 0.05 from Tax 19% group
            tax_totals['subtotals'][0]['tax_groups'][index]['tax_amount_currency'] = 56.95
            move_form.tax_totals = tax_totals
        move.action_post()
        move.line_ids.flush_recordset()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[8]] for x in reader][2:]
        self.assertEqual([
            # 0.03 should be dispatched to the first line using Tax 19%
            ['118,97', self.tax_19.l10n_de_datev_code],
            # 0.02 should be dispatched to the second line using Tax 19%
            ['237,98', self.tax_19.l10n_de_datev_code],
            ['107,00', self.tax_7.l10n_de_datev_code],
        ], data)

    def test_datev_out_invoice_in_foreign_currency_rate_set_manually(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        }})
        foreign_currency = self.env['res.currency'].create({
            'name': "XYZ",
            'symbol': 'X',
        })

        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'currency_id': foreign_currency.id,
            'invoice_date': '2020-12-01',
            'invoice_currency_rate': 0.5,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 100.00,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(self.tax_19.ids)],
                }),
            ]
        }])
        move.action_post()
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['119,00', 'H', 'XYZ', '0,5', '238,00', 'EUR', '34000000', str(move.partner_id.id + 100000000),
                       self.tax_19.l10n_de_datev_code, '112', move.name, move.invoice_line_ids[0].name], data)

    def test_datev_expense_payment_with_tax(self):
        """ Test that the tax code is exported from a payment move """
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2020-12-01',
            'date_to': '2020-12-31'
        }})
        bank_journal = self.company_data['default_journal_bank']

        account_1203 = self.env['account.account'].search([
            ('code', '=', 1203),
            ('company_ids', '=', self.company_data['company'].id)
        ], limit=1)

        tax_19_incl = self.tax_19.copy({'name': 'Tax 19% incl.', 'price_include': True})
        tax_repartition_line = tax_19_incl.refund_repartition_line_ids.filtered(lambda line: line.repartition_type == 'tax')

        skip_context = {
            'skip_invoice_sync': True,
            'skip_invoice_line_sync': True,
            'skip_account_move_synchronization': True,
        }
        payment = self.env['account.payment'].with_context(**skip_context).create({
            'amount': 150.00,
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'date': '2020-12-01',
            'journal_id': bank_journal.id,
            'line_ids': [
                Command.create({
                    'name': 'Line 19% #1',
                    'debit': 126.05,
                    'credit': 0.0,
                    'account_id': self.account_3400.id,
                    'tax_ids': [Command.set(tax_19_incl.ids)],
                }),
                Command.create({
                    'name': 'Line 19% tax',
                    'debit': 23.95,
                    'credit': 0.0,
                    'account_id': self.account_1500.id,
                    'tax_repartition_line_id': tax_repartition_line.id,
                }),
                Command.create({
                    'name': 'expense line',
                    'credit': 150.0,
                    'debit': 0.0,
                    'account_id': account_1203.id,
                }),
            ],
        })
        payment.action_post()

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, payment.move_id))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8]] for x in reader][2:]
        self.assertEqual([
            ['150,00', 'H', 'EUR', '12030000', '34000000', tax_19_incl.l10n_de_datev_code],
        ], data)

    def test_datev_out_invoice_in_foreign_currency_with_exchange_loss(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31'
        }})

        # Create exchange rate entries for the foreign currency
        foreign_currency = self.env['res.currency'].create({
            'name': "XYZ",
            'symbol': 'X',
            'rate_ids': [
                Command.create({'name': '2026-01-01', 'rate': 1.0}),
                Command.create({'name': '2026-01-15', 'rate': 1.1}),
            ],
        })

        # Create the invoice on any date before the exchange rate changes (i.e before 15th in this case)
        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'currency_id': foreign_currency.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 100.00,
                    'tax_ids': [],
                }),
            ]
        }])
        move.action_post()

        # Make the payment on any date with the new exchange rate (15th or after)
        # The payment should create two entries in the report, one for the invoice payment
        # and another for the currency exchange difference.
        pay = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'payment_date': fields.Date.to_date('2026-01-16'),
        })._create_payments()

        # Get the exchange move
        exchange_move = move.line_ids.matched_credit_ids.exchange_move_id

        # Get the payment move
        payment_move = pay.move_id

        moves = payment_move | exchange_move

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, moves))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['100,00', 'H', 'XYZ', '1,099989', '90,91', 'EUR', str(move.partner_id.id + 100000000), '12030000',
                       '', '1601', payment_move.name, payment_move.line_ids[0].name], data)
        self.assertIn(['0,00', 'H', 'XYZ', '1,0', '9,09', 'EUR', str(move.partner_id.id + 100000000), '21500000',
                      '', '3101', exchange_move.name, exchange_move.line_ids[0].name], data)

    def test_datev_out_invoice_in_foreign_currency_with_exchange_gain(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2026-01-01',
            'date_to': '2026-12-31'
        }})

        # Create exchange rate entries for the foreign currency
        foreign_currency = self.env['res.currency'].create({
            'name': "XYZ",
            'symbol': 'X',
            'rate_ids': [
                Command.create({'name': '2026-01-01', 'rate': 1.0}),
                Command.create({'name': '2026-01-15', 'rate': 0.5}),
            ],
        })

        # Create the invoice on any date before the exchange rate changes (i.e before 15th in this case)
        move = self.env['account.move'].create([{
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'currency_id': foreign_currency.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'price_unit': 100.00,
                    'tax_ids': [],
                }),
            ]
        }])
        move.action_post()

        # Make the payment on any date with the new exchange rate (15th or after)
        # The payment should create two entries in the report, one for the invoice payment
        # and another for the currency exchange difference.
        pay = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'payment_date': fields.Date.to_date('2026-01-16'),
        })._create_payments()

        # Get the exchange move
        exchange_move = move.line_ids.matched_credit_ids.exchange_move_id

        # Get the payment move
        payment_move = pay.move_id

        moves = payment_move | exchange_move

        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, moves))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[13]] for x in reader][2:]
        self.assertIn(['100,00', 'H', 'XYZ', '0,5', '200,00', 'EUR', str(move.partner_id.id + 100000000), '12030000',
                       '', '1601', payment_move.name, payment_move.line_ids[0].name], data)
        self.assertIn(['0,00', 'S', 'XYZ', '1,0', '100,00', 'EUR', str(move.partner_id.id + 100000000), '26600000',
                      '', '3101', exchange_move.name, exchange_move.line_ids[0].name], data)

    def test_datev_in_invoice_tax_with_multiple_repartition_lines(self):
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2026-01-01',
            'date_to': '2026-01-31',
        }})

        foreign_currency = self.env['res.currency'].create({
            'name': "for",
            'symbol': 'abc',
            'rounding': 0.01,
            'rate_ids': [
                Command.create({'name': '2025-01-01', 'rate': 3}),
            ],
        })

        tax_account = self.company_data['default_account_tax_purchase']

        tax = self.env['account.tax'].create({
            'name': 'multiple repartition line tax',
            'amount_type': 'percent',
            'amount': 10.0,
            'type_tax_use': 'purchase',
            'repartition_line_ids': [
                Command.create({'document_type': 'invoice', 'repartition_type': 'base'}),
                Command.create({'document_type': 'invoice', 'repartition_type': 'tax', 'account_id': tax_account.id, 'factor_percent': 50.0}),
                Command.create({'document_type': 'invoice', 'repartition_type': 'tax', 'account_id': tax_account.id, 'factor_percent': 50.0}),
                Command.create({'document_type': 'refund', 'repartition_type': 'base'}),
                Command.create({'document_type': 'refund', 'repartition_type': 'tax', 'account_id': tax_account.id, 'factor_percent': 50.0}),
                Command.create({'document_type': 'refund', 'repartition_type': 'tax', 'account_id': tax_account.id, 'factor_percent': 50.0}),
            ]
        })

        move = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.partner_a.id,
            'date': '2026-01-01',
            'invoice_date': '2026-01-01',
            'currency_id': foreign_currency.id,
            'invoice_line_ids': [Command.create({
                'price_unit': 100.00,
                'tax_ids': [tax.id],
            })]
        }])
        move.action_post()
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[6], x[7], x[8]] for x in reader][2:]
        self.assertEqual([
            ['110,00', 'S', 'for', '34000000', str(move.partner_id.id + 700000000), ''],
        ], data)

    def test_datev_exchange_rate_zero_denominator(self):
        """Test that an exchange rate defaults to 1,0 when the base currency amount is zero"""
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={
            'date': {'date_from': '2026-01-01', 'date_to': '2026-12-31'}
        })
        foreign_currency = self.env['res.currency'].create({
            'name': "XYZ",
            'symbol': 'X',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-01-15',
            'currency_id': foreign_currency.id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Zero Base Test Line',
                    'quantity': 1,
                    'price_unit': 100.00,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'tax_ids': [],
                })
            ]
        })
        invoice.action_post()
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, invoice))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [[x[0], x[1], x[2], x[3], x[4], x[5]] for x in reader][2:]
        self.assertIn(['100,00', 'H', 'XYZ', '1,0', '100,00', 'EUR'], data)

    def test_datev_three_currency_basic(self):
        """
        Tests 3-currency export with one foreign AR line.

        Bank [AED] → AR [USD] → Company Currency [EUR]
        """
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        }})
        setup = self._setup_three_currency_test()
        move = self._create_three_currency_transaction(
            setup['bank_journal'].id,
            amount=3000.0,
            invoice_values=[{
                'move_type': 'out_invoice',
                'currency_id': setup['usd'].id,
                'price_unit': 5000.0,
            }],
        )
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [
            [x[0], x[1], x[2], x[4], x[5], x[7]]
            for x in list(reader)[2:]
        ]

        self.assertEqual(len(data), 2)
        self.assertIn(['3000,00', 'S', 'AED', '100,00', 'EUR', '13600000'], data)
        self.assertIn(['5000,00', 'H', 'USD', '100,00', 'EUR', '13600000'], data)

    def test_datev_three_currency_multiple_lines(self):
        """
        Tests multiple lines with mixed 2/3-currency handling.

        One bank transaction:
            -4,500 AED = -150 EUR

        Reconciled against:
            2,500 USD = 50 EUR
            2,500 USD = 50 EUR
            1,500 AED = 50 EUR
        """
        report = self.env.ref('account_reports.general_ledger_report')
        options = report.get_options(previous_options={'date': {
            'date_from': '2020-01-01',
            'date_to': '2020-12-31',
        }})
        setup = self._setup_three_currency_test()
        move = self._create_three_currency_transaction(
            setup['bank_journal'].id,
            amount=-4500.0,
            invoice_values=[
                {
                    'move_type': 'in_invoice',
                    'currency_id': setup['usd'].id,
                    'price_unit': 2500.0,
                },
                {
                    'move_type': 'in_invoice',
                    'currency_id': setup['usd'].id,
                    'price_unit': 2500.0,
                },
                {
                    'move_type': 'in_invoice',
                    'currency_id': setup['aed'].id,
                    'price_unit': 1500.0,
                },
            ],
        )
        f = StringIO(self.env[report.custom_handler_model_name]._l10n_de_datev_get_csv(options, move))
        reader = csv.reader(f, delimiter=';', quotechar='"', quoting=2)
        data = [
            [x[0], x[1], x[2], x[4], x[5], x[7]]
            for x in list(reader)[2:]
        ]

        self.assertEqual(len(data), 4)
        self.assertEqual(data.count(['4500,00', 'H', 'AED', '100,00', 'EUR', '13600000']), 1)
        self.assertEqual(data.count(['2500,00', 'S', 'USD', '50,00', 'EUR', '13600000']), 2)
        self.assertEqual(data.count(['1500,00', 'S', 'AED', '50,00', 'EUR', '12060000']), 1)
