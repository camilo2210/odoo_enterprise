from .common import TestAccountReportsCommon

from odoo import Command, fields
from freezegun import freeze_time
from odoo.tools import format_date
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestFollowupReport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.report = cls.env.ref('account_reports.followup_report')
        # Initiate Invoices
        with freeze_time('2025-10-08'):
            cls.today = fields.Date.today()
        invoices_data = [
            # Partner A invoices
            {'partner': cls.partner_a, 'amount': 100.0, 'due_date': '2025-01-01'},
            {'partner': cls.partner_a, 'amount': 100.0, 'due_date': cls.today},
            {'partner': cls.partner_a, 'amount': 100.0, 'due_date': '2025-01-01', 'move_type': 'out_refund'},
            {'partner': cls.partner_a, 'amount': 100.0, 'due_date': '2025-01-01', 'date': '2024-12-22'},
            {'partner': cls.partner_a, 'amount': 100.0, 'due_date': False, 'date': '2024-12-22'},

            # Partner B invoices
            {'partner': cls.partner_b, 'amount': 100.0, 'due_date': '2025-01-01'},
            {'partner': cls.partner_b, 'amount': 100.0, 'due_date': cls.today},
            {'partner': cls.partner_b, 'amount': 400.0, 'due_date': '2025-01-01', 'move_type': 'out_refund'},
        ]
        cls.invoices = cls.env['account.move'].union(
            cls.init_invoice(
                move_type=invoice_data.get('move_type', 'out_invoice'),
                partner=invoice_data['partner'],
                amounts=[invoice_data['amount']],
                invoice_date_due=invoice_data['due_date'],
                invoice_date=invoice_data.get('invoice_date', '2025-01-01'),
            )
            for invoice_data in invoices_data
        )
        cls.formatted_today = format_date(cls.env, cls.today, date_format='MM/dd/YYY')

    @classmethod
    def init_invoice(cls, move_type, partner=None, invoice_date=None, post=False, products=None, amounts=None, taxes=None, company=False, currency=None, journal=None, invoice_date_due=None):
        move = super().init_invoice(move_type, partner, invoice_date, False, products, amounts, taxes, company, currency, journal)
        if invoice_date_due is not None:
            move.invoice_payment_term_id = False
            move.invoice_date_due = invoice_date_due
        move.action_post()
        return move

    @freeze_time('2025-10-08')
    def test_followup_report_unfold(self):
        ''' Test unfolding a line when rendering the whole report, having overdue and due sections '''
        options = self._generate_options(self.report, '2025-01-01', '2025-01-31')
        lines = self.report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                  Amount          Resdiual
            [   0,                                      4,              6],
            [
                ('Open Items',                      100.0,          100.0),
                ('partner_a',                       300.0,          300.0),
                ('partner_b',                      -200.0,         -200.0),
                ('Total Open Items',                100.0,          100.0),
            ],
            options
        )

        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.followup_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Due Date        Amount        Resdiual
            [   0,                                            3,            4,              6],
            [
                ('Open Items',                               '',        100.0,          100.0),
                ('partner_a',                                '',        300.0,          300.0),
                ('INV/2025/00001',                 '01/01/2025',        100.0,          100.0),
                ('RINV/2025/00001',                '01/01/2025',       -100.0,         -100.0),
                ('INV/2025/00003',                 '01/01/2025',        100.0,          100.0),
                ('INV/2025/00002',         self.formatted_today,        100.0,          100.0),
                ('INV/2025/00004',                           '',        100.0,          100.0),
                ('Total partner_a',                          '',        300.0,          300.0),
                ('partner_b',                                '',       -200.0,         -200.0),
                ('Total Open Items',                         '',        100.0,          100.0),
            ],
            options
        )

    @freeze_time('2025-10-08')
    def test_followup_report_load_more(self):
        ''' Test loading more lines when reaching the limit '''
        self.report.load_more_limit = 2

        invoices_data = [
            {'amount': 100.0, 'due_date': '2024-12-03'},
            {'amount': 100.0, 'due_date': self.today},
        ]

        for invoice_data in invoices_data:
            self.init_invoice(
                move_type='out_invoice',
                partner=self.partner_a,
                amounts=[invoice_data['amount']],
                invoice_date_due=invoice_data['due_date'],
                invoice_date='2025-01-01',
            )

        options = self._generate_options(self.report, '2025-01-01', '2025-01-31')
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.followup_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            report_lines,
            #   Name                                    Due Date        Amount       Resdiual
            [   0,                                            3,            4,             6],
            [
                ('Open Items',                               '',        300.0,         300.0),
                ('partner_a',                                '',        500.0,         500.0),
                ('INV/2025/00007',                 '12/03/2024',        100.0,         100.0),
                ('INV/2025/00001',                 '01/01/2025',        100.0,         100.0),
                ('5 more',                                   '',        300.0,         300.0),
                ('Total partner_a',                          '',        500.0,         500.0),
                ('partner_b',                                '',       -200.0,        -200.0),
                ('Total Open Items',                         '',        300.0,         300.0),
            ],
            options
        )

        options['unfolded_lines'] = [line.id for line in report_lines if line.unfolded]

        load_more_lines = self.report.get_expanded_lines(
            options,
            report_lines[1].id,
            report_lines[5].groupby,
            '_report_expand_unfoldable_line_with_groupby',
            None,
            None,
            ignore_load_more=True,
        )

        self.assertLinesValues(
            load_more_lines,
            #   Name                                    Due Date        Amount         Resdiual
            [   0,                                            3,            4,             6],
            [
                ('INV/2025/00007',                 '12/03/2024',        100.0,         100.0),
                ('INV/2025/00001',                 '01/01/2025',        100.0,         100.0),
                ('RINV/2025/00001',                '01/01/2025',       -100.0,        -100.0),
                ('INV/2025/00003',                 '01/01/2025',        100.0,         100.0),
                ('INV/2025/00002',         self.formatted_today,        100.0,         100.0),
                ('INV/2025/00008',         self.formatted_today,        100.0,         100.0),
                ('INV/2025/00004',                           '',        100.0,         100.0),
            ],
            options,
        )

    @freeze_time('2025-10-08')
    def test_followup_reconciled(self):
        receivable = self.partner_a.property_account_receivable_id
        payment = self.env['account.move'].create([{
            'partner_id': self.partner_a.id,
            'line_ids': [
                Command.create({
                    'balance': 50,
                    'account_id': self.company_data['default_account_revenue'].id,
                }),
                Command.create({
                    'balance': -50,
                    'account_id': receivable.id,
                }),
            ],
        }])
        options = self._generate_options(self.report, '2025-01-01', '2025-01-31')
        parent_line_id = self.report._get_generic_line_id(model_name='account.report.line', value=self.env.ref("account_reports.followup_report_line").id)
        partner_a_line_id = self.report._get_generic_line_id(model_name='res.partner', value=self.partner_a.id, markup={'groupby': 'partner_id'}, parent_line_id=parent_line_id)
        options['unfolded_lines'] = [partner_a_line_id]

        # We display the residual amount
        (self.invoices[0] + payment).line_ids.filtered(lambda l: l.account_id == receivable).reconcile()
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Due Date        Amount        Resdiual
            [   0,                                            3,            4,              6],
            [
                ('Open Items',                               '',        100.0,           50.0),
                ('partner_a',                                '',        300.0,          250.0),
                ('INV/2025/00001',                 '01/01/2025',        100.0,           50.0),
                ('RINV/2025/00001',                '01/01/2025',       -100.0,         -100.0),
                ('INV/2025/00003',                 '01/01/2025',        100.0,          100.0),
                ('INV/2025/00002',         self.formatted_today,        100.0,          100.0),
                ('INV/2025/00004',                           '',        100.0,          100.0),
                ('Total partner_a',                          '',        300.0,          250.0),
                ('partner_b',                                '',       -200.0,         -200.0),
                ('Total Open Items',                         '',        100.0,           50.0),
            ],
            options
        )

        # Fully reconciled lines are removed from the report
        (self.invoices[0] + self.invoices[2]).line_ids.filtered(lambda l: l.account_id == receivable).reconcile()
        self.assertLinesValues(
            self.report._get_lines(options),
            #   Name                                    Due Date        Amount        Resdiual
            [   0,                                            3,            4,              6],
            [
                ('Open Items',                               '',           '',           50.0),
                ('partner_a',                                '',        200.0,          250.0),
                ('RINV/2025/00001',                '01/01/2025',       -100.0,          -50.0),
                ('INV/2025/00003',                 '01/01/2025',        100.0,          100.0),
                ('INV/2025/00002',         self.formatted_today,        100.0,          100.0),
                ('INV/2025/00004',                           '',        100.0,          100.0),
                ('Total partner_a',                          '',        200.0,          250.0),
                ('partner_b',                                '',       -200.0,         -200.0),
                ('Total Open Items',                         '',           '',           50.0),
            ],
            options
        )
