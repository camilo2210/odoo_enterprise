# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import freeze_time


class TestBankRecWidgetCommon(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_currency = cls.setup_other_currency('EUR')
        cls.other_currency_2 = cls.setup_other_currency('CAD', rounding=0.001, rates=[('2016-01-01', 6.0), ('2017-01-01', 4.0)])
        cls.other_currency_3 = cls.setup_other_currency('XAF', rounding=0.001, rates=[('2016-01-01', 12.0), ('2017-01-01', 8.0)])

        cls.early_payment_term = cls.env['account.payment.term'].create({
            'name': "Early_payment_term",
            'company_id': cls.company_data['company'].id,
            'discount_percentage': 10,
            'discount_days': 10,
            'early_discount': True,
            'line_ids': [
                Command.create({
                    'value': 'percent',
                    'value_amount': 100,
                    'nb_days': 20,
                }),
            ],
        })

    @classmethod
    @freeze_time('2017-01-01')
    def _create_invoice_one_line_reco(cls, **invoice_args):
        ''' Create an invoice on the fly.'''
        invoice = cls._create_invoice_one_line(**invoice_args, post=True)
        return invoice.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))

    @classmethod
    def _create_st_line(cls, amount, date='2019-01-01', payment_ref='turlututu', update_create_date=True, **kwargs):
        st_line = cls.env['account.bank.statement.line'].create({
            'amount': amount,
            'date': date,
            'payment_ref': payment_ref,
            'journal_id': kwargs.get('journal_id', cls.company_data['default_journal_bank'].id),
            **kwargs,
        })
        if update_create_date:
            # The automatic reconcile cron checks the create_date when considering st_lines to run on.
            # create_date is a protected field so this is the only way to set it correctly
            cls.env.cr.execute("UPDATE account_bank_statement_line SET create_date = %s WHERE id=%s",
                               (st_line.date, st_line.id))
        return st_line
