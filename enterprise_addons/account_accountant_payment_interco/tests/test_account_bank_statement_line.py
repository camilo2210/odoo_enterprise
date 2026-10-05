from odoo.tests import tagged
from odoo.addons.account_accountant.tests.common import TestBankRecWidgetCommon


@tagged('post_install', '-at_install')
class TestAccountBankStatement(TestBankRecWidgetCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data_2 = cls.setup_other_company()

        account_data = (
            ('c/c interco receivable Odoo', '210002', 'asset_receivable'),
            ('c/c interco payable Odoo', '489286', 'liability_payable'),
        )
        for company in (cls.env.company + cls.company_data_2['company']):
            company.account_interco_clearing_journal_id = cls.env['account.journal'].create({
                'name': 'Intercompany clearings',
                'type': 'general',
                'company_id': company.id,
            })
            for account_name, account_code, account_type in account_data:
                account = cls.env['account.account'].with_company(company).create({
                    'name': f'{account_name} {company.country_id.code}',
                    'code': account_code,
                    'account_type': account_type,
                    'reconcile': True,
                })
                if account_type == 'asset_receivable':
                    company.account_interco_receivable_id = account
                else:
                    company.account_interco_payable_id = account

    def test_interco_reconciliation_invoice(self):
        invoice_line_company_1 = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            date='2017-01-04',
            price_unit=100.0,
            company_id=self.env.company.id,
        )
        st_line_company_2 = self._create_st_line(100.0, update_create_date=False, partner_id=self.partner_a.id, journal_id=self.company_data_2['default_journal_bank'].id, company_id=self.company_data_2['company'].id)
        st_line_company_2.set_line_bank_statement_line(invoice_line_company_1.id)

        # Clearing move
        self.assertRecordValues(invoice_line_company_1.reconciled_lines_ids.move_id.line_ids, [
            {'account_id': invoice_line_company_1.account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
            {'account_id': invoice_line_company_1.company_id.account_interco_receivable_id.id, 'partner_id': st_line_company_2.company_id.partner_id.id, 'balance': 100.0},
        ])
        # Clearing move should be reconciled with the invoice_line
        self.assertEqual(
            invoice_line_company_1.reconciled_lines_ids.matching_number,
            invoice_line_company_1.matching_number,
        )

        # Settlement move
        self.assertEqual(st_line_company_2.line_ids.reconciled_lines_ids.ref, 'Interco Settlement partner_a - INV/2017/00001 - company_1_data')
        self.assertRecordValues(st_line_company_2.line_ids.reconciled_lines_ids.move_id.line_ids, [
            {'account_id': st_line_company_2.company_id.account_interco_payable_id.id, 'partner_id': invoice_line_company_1.company_id.partner_id.id, 'balance': -100.0},
            {'account_id': st_line_company_2.company_id.receivable_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
        ])

        # Statement line entry
        self.assertRecordValues(st_line_company_2.line_ids, [
            {'account_id': st_line_company_2.journal_id.default_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
            {'account_id': st_line_company_2.company_id.receivable_account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
        ])

        # Settlement move and statement line entry should be reconciled together
        self.assertEqual(
            st_line_company_2.line_ids.reconciled_lines_ids.matching_number,
            st_line_company_2.line_ids[1].matching_number,
        )

    def test_interco_reconciliation_bill(self):
        bill_line_company_1 = self._create_invoice_one_line_reco(
            move_type='in_invoice',
            date='2017-01-04',
            price_unit=100.0,
            company_id=self.env.company.id,
        )
        st_line_company_2 = self._create_st_line(-100.0, update_create_date=False, partner_id=self.partner_a.id, journal_id=self.company_data_2['default_journal_bank'].id, company_id=self.company_data_2['company'].id)
        st_line_company_2.set_line_bank_statement_line(bill_line_company_1.id)

        # Clearing move
        self.assertRecordValues(bill_line_company_1.reconciled_lines_ids.move_id.line_ids, [
            {'account_id': bill_line_company_1.account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
            {'account_id': bill_line_company_1.company_id.account_interco_payable_id.id, 'partner_id': st_line_company_2.company_id.partner_id.id, 'balance': -100.0},
        ])

        # Clearing move should be reconciled with the bill_line
        self.assertEqual(
            bill_line_company_1.reconciled_lines_ids.matching_number,
            bill_line_company_1.matching_number,
        )

        # Settlement move
        self.assertEqual(st_line_company_2.line_ids.reconciled_lines_ids.ref, 'Interco Settlement partner_a - BILL/2017/01/0001 - company_1_data')
        self.assertRecordValues(st_line_company_2.line_ids.reconciled_lines_ids.move_id.line_ids, [
            {'account_id': st_line_company_2.company_id.account_interco_receivable_id.id, 'partner_id': bill_line_company_1.company_id.partner_id.id, 'balance': 100.0},
            {'account_id': st_line_company_2.company_id.payable_account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
        ])

        # Statement line entry
        self.assertRecordValues(st_line_company_2.line_ids, [
            {'account_id': st_line_company_2.journal_id.default_account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
            {'account_id': st_line_company_2.company_id.payable_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
        ])

        # Settlement move and statement line entry should be reconciled together
        self.assertEqual(
            st_line_company_2.line_ids.reconciled_lines_ids.matching_number,
            st_line_company_2.line_ids[1].matching_number,
        )

    def test_interco_reconciliation_two_invoices(self):
        invoice_line_company_1 = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            date='2017-01-04',
            price_unit=50.0,
            company_id=self.env.company.id,
        )
        invoice_line_company_2 = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            date='2017-01-04',
            price_unit=50.0,
            company_id=self.company_data_2['company'].id,
        )
        st_line_company_2 = self._create_st_line(100.0, update_create_date=False, partner_id=self.partner_a.id, journal_id=self.company_data_2['default_journal_bank'].id, company_id=self.company_data_2['company'].id)
        st_line_company_2.set_line_bank_statement_line((invoice_line_company_1 + invoice_line_company_2).ids)

        # Clearing move
        self.assertRecordValues(invoice_line_company_1.reconciled_lines_ids.move_id.line_ids, [
            {'account_id': invoice_line_company_1.account_id.id, 'partner_id': self.partner_a.id, 'balance': -50.0},
            {'account_id': invoice_line_company_1.company_id.account_interco_receivable_id.id, 'partner_id': st_line_company_2.company_id.partner_id.id, 'balance': 50.0},
        ])

        # Clearing move should be reconciled with the invoice_line
        self.assertEqual(
            invoice_line_company_1.reconciled_lines_ids.matching_number,
            invoice_line_company_1.matching_number,
        )

        # Settlement move
        settlement_line = st_line_company_2.line_ids.reconciled_lines_ids - invoice_line_company_2
        settlement_move = settlement_line.move_id
        self.assertEqual(settlement_move.ref, 'Interco Settlement partner_a - INV/2017/00001 - company_1_data')
        self.assertRecordValues(settlement_move.line_ids, [
            {'account_id': st_line_company_2.company_id.account_interco_payable_id.id, 'partner_id': invoice_line_company_1.company_id.partner_id.id, 'balance': -50.0},
            {'account_id': st_line_company_2.company_id.receivable_account_id.id, 'partner_id': self.partner_a.id, 'balance': 50.0},
        ])

        # Statement line entry
        self.assertRecordValues(st_line_company_2.line_ids, [
            {'account_id': st_line_company_2.journal_id.default_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
            {'account_id': invoice_line_company_2.account_id.id, 'partner_id': self.partner_a.id, 'balance': -50.0},
            {'account_id': st_line_company_2.company_id.receivable_account_id.id, 'partner_id': self.partner_a.id, 'balance': -50.0},
        ])

        # Other invoice_line move and statement line entry should be reconciled together
        self.assertEqual(
            invoice_line_company_2.matching_number,
            st_line_company_2.line_ids[1].matching_number,
        )

        # Settlement move and statement line entry should be reconciled together
        self.assertEqual(
            settlement_line.matching_number,
            st_line_company_2.line_ids[2].matching_number,
        )

    def test_interco_reconciliation_invoice_and_delete(self):
        invoice_line_company_1 = self._create_invoice_one_line_reco(
            move_type='out_invoice',
            date='2017-01-04',
            price_unit=100.0,
            company_id=self.env.company.id,
        )
        st_line_company_2 = self._create_st_line(100.0, update_create_date=False, partner_id=self.partner_a.id, journal_id=self.company_data_2['default_journal_bank'].id, company_id=self.company_data_2['company'].id)
        st_line_company_2.set_line_bank_statement_line(invoice_line_company_1.id)

        # Clearing move
        clearing_move_line = invoice_line_company_1.reconciled_lines_ids
        clearing_move = clearing_move_line.move_id
        self.assertRecordValues(clearing_move.line_ids, [
            {'account_id': invoice_line_company_1.account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
            {'account_id': invoice_line_company_1.company_id.account_interco_receivable_id.id, 'partner_id': st_line_company_2.company_id.partner_id.id, 'balance': 100.0},
        ])
        # Clearing move should be reconciled with the invoice_line
        self.assertEqual(
            clearing_move_line.matching_number,
            invoice_line_company_1.matching_number,
        )

        # Settlement move
        settlement_move_line = st_line_company_2.line_ids.reconciled_lines_ids
        settlement_move = settlement_move_line.move_id
        self.assertEqual(settlement_move_line.ref, 'Interco Settlement partner_a - INV/2017/00001 - company_1_data')
        self.assertRecordValues(settlement_move_line.move_id.line_ids, [
            {'account_id': st_line_company_2.company_id.account_interco_payable_id.id, 'partner_id': invoice_line_company_1.company_id.partner_id.id, 'balance': -100.0},
            {'account_id': st_line_company_2.company_id.receivable_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
        ])

        # Statement line entry
        self.assertRecordValues(st_line_company_2.line_ids, [
            {'account_id': st_line_company_2.journal_id.default_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
            {'account_id': st_line_company_2.company_id.receivable_account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
        ])

        # Settlement move and statement line entry should be reconciled together
        self.assertEqual(
            settlement_move_line.matching_number,
            st_line_company_2.line_ids[1].matching_number,
        )

        st_line_company_2.delete_reconciled_line(st_line_company_2.line_ids[1].id)
        # Settlement move should have been removed
        self.assertFalse(invoice_line_company_1.reconciled_lines_ids)
        self.assertFalse(clearing_move.exists())
        self.assertFalse(settlement_move.exists())
        self.assertRecordValues(st_line_company_2.line_ids, [
            {'account_id': st_line_company_2.journal_id.default_account_id.id, 'partner_id': self.partner_a.id, 'balance': 100.0},
            {'account_id': st_line_company_2.journal_id.suspense_account_id.id, 'partner_id': self.partner_a.id, 'balance': -100.0},
        ])
