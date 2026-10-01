# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, tools
from odoo.addons.account_saft.tests.common import TestSaftReport
from odoo.tests import tagged

from freezegun import freeze_time
from itertools import starmap


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestLuSaftReport(TestSaftReport):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestSaftReport.setup_country('lu')
    def setUpClass(cls):
        super().setUpClass()

        (cls.partner_a + cls.partner_b).write({
            'city': 'Garnich',
            'zip': 'L-8353',
            'country_id': cls.env.ref('base.lu').id,
            'phone': '+352 24 11 11 11',
        })

        cls.company_data['company'].write({
            'city': 'Garnich',
            'zip': 'L-8353',
            'phone': '+352 11 11 11 11',
            'additional_identifiers': {'LU_EN': '123456'},
            'country_id': cls.env.ref('base.lu').id,
        })

        cls.env['res.partner'].create({
            'name': 'Mr Big CEO',
            'phone': '+352 24 11 12 34',
            'parent_id': cls.company_data['company'].partner_id.id,
        })

        cls.product_a.default_code = 'PA'
        cls.product_b.default_code = 'PB'
        cls.product_c = cls._create_product(name='product_c', lst_price=1000.0, standard_price=800.0, default_code='PA')
        cls.product_d = cls._create_product(name='product_d', lst_price=1000.0, standard_price=800.0, default_code=False)

        tax_10 = cls.company_data['default_tax_sale'].copy({
            'name': '10% S',
            'amount': 10.0,
            'include_base_amount': True,
        })
        cls.company_data['default_tax_sale'].sequence += 1

        # Create invoices

        invoices = cls.env['account.move'].create(
            list(starmap(cls._l10n_lu_saft_invoice_data, [
                ('out_invoice', '2019-01-01', cls.partner_a, [
                    {'product': cls.product_a, 'quantity': 5.0, 'price_unit': 1000.0, 'tax_ids': cls.company_data['default_tax_sale'].ids + tax_10.ids},
                    {'product': cls.product_b, 'quantity': 1.0, 'price_unit': 500.0, 'tax_ids': cls.company_data['default_tax_sale'].ids + tax_10.ids},
                ]),
                ('out_refund', '2019-03-01', cls.partner_a, [{'product': cls.product_a, 'quantity': 3.0, 'price_unit': 1000.0}]),
                ('in_invoice', '2018-12-31', cls.partner_b, [{'product': cls.product_b, 'quantity': 10.0, 'price_unit': 800.0}]),
                ('in_invoice', '2019-01-01', cls.partner_b, [{'product': cls.product_b, 'quantity': 10.0, 'price_unit': 800.0}]),
                ('in_invoice', '2019-04-01', cls.partner_b, [
                    {'product': cls.product_b, 'quantity': 10.0, 'price_unit': 800.0, 'tax_ids': cls.env.ref(f'account.{cls.company_data["company"].id}_lu_2015_tax_AB-EC-17').ids},
                    {'product': cls.product_a, 'quantity': 1.0, 'price_unit': -10.0, 'tax_ids': cls.company_data['default_tax_purchase'].ids},
                ]),
            ])))
        invoices.action_post()
        # Create an allocation entry
        ChartTemplate = cls.env['account.chart.template']
        allocation_acc = ChartTemplate.ref('lu_2020_account_6492')
        provision_acc = ChartTemplate.ref('lu_2011_account_1881')
        cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2018-12-31',
            'line_ids': [
                Command.create({
                    'name': 'Distribute earnings',
                    'account_id': provision_acc.id,
                    'debit': 8000.0,
                    'credit': 0.0,
                }),
                Command.create({
                    'name': 'Distribute earnings',
                    'account_id': allocation_acc.id,
                    'debit': 0.0,
                    'credit': 8000.0,
                }),
            ]
        }).action_post()

    @classmethod
    def _l10n_lu_saft_invoice_data(cls, move_type, invoice_date, partner, lines_data):
        tax_type = 'purchase' if move_type == 'in_invoice' else 'sale'
        return {
            'move_type': move_type,
            'invoice_date': invoice_date,
            'date': invoice_date,
            'partner_id': partner.id,
            'invoice_line_ids': [Command.create({
                'product_id': line_data['product'].id,
                'quantity': line_data['quantity'],
                'price_unit': line_data['price_unit'],
                'tax_ids': [Command.set(line_data.get('tax_ids') or cls.company_data[f"default_tax_{tax_type}"].ids)]
            }) for line_data in lines_data],
        }

    def _l10n_lu_saft_generate_report(self, date_from='2019-01-01', date_to='2019-12-31'):
        options = self._generate_options(date_from, date_to)
        with freeze_time('2019-12-31'):
            return self.report_handler.l10n_lu_export_saft_to_xml(options)['file_content']

    def test_saft_report_errors(self):
        invoice_data = list(starmap(self._l10n_lu_saft_invoice_data, [
            ('out_invoice', '2019-01-01', self.partner_a, [{'product': self.product_c, 'quantity': 5.0, 'price_unit': 1000.0}]),
            ('out_invoice', '2019-01-01', self.partner_a, [{'product': self.product_d, 'quantity': 5.0, 'price_unit': 1000.0}]),
            ('out_invoice', '2018-12-31', self.partner_a, [{'product': self.product_d, 'quantity': 5.0, 'price_unit': 1000.0}]),
        ]))
        new_invoices = self.env['account.move'].create(invoice_data)
        new_invoices.action_post()
        with self.assertRaises(self.ReportException) as cm:
            self._l10n_lu_saft_generate_report()
        self.assertEqual(set(cm.exception.errors), {'product_duplicate_ref', 'product_missing_ref', 'undistributed_earnings'})

    def test_saft_report_values(self):
        tax_8 = self.env['account.tax'].search([
            ('company_id', '=', self.company_data['company'].id),
            ('name', '=', '8% S'),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        ecotrel_tax = self.company_data['default_tax_sale'].copy({
            'name': '2% Ecotrel',
            'amount': 2.0,
            'include_base_amount': True,
            'sequence': min(self.company_data['default_tax_sale'].sequence, tax_8.sequence) - 1,
        })
        ecotrel_invoice = self.env['account.move'].create(self._l10n_lu_saft_invoice_data(
            'out_invoice',
            '2019-01-01',
            self.partner_a,
            [
                {'product': self.product_a, 'quantity': 1.0, 'price_unit': 100.0, 'tax_ids': (ecotrel_tax + self.company_data['default_tax_sale']).ids},
                {'product': self.product_b, 'quantity': 1.0, 'price_unit': 100.0, 'tax_ids': (ecotrel_tax + tax_8).ids},
            ],
        ))
        ecotrel_invoice.action_post()

        with tools.file_open("l10n_lu_reports/tests/xml/expected_faia_values_2019.xml", "rb") as expected_xml:
            self.assertXmlTreeEqual(
                self.get_xml_tree_from_string(self._l10n_lu_saft_generate_report()),
                self.get_xml_tree_from_string(expected_xml.read()),
            )

    @freeze_time('2025-12-30')
    def test_partner_classification_faia_report(self):
        """
        Test that partners are correctly classified as both customers and suppliers in the FAIA report,
        and that credit notes are not classified as suppliers.
        """

        partner_c = self.env['res.partner'].create({
            'name': 'partner c',
            'city': 'Garnich',
            'zip': 'L-8353',
            'country_id': self.env.ref('base.lu').id,
            'phone': '+352 24 11 11 11',
        })

        last_month_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2025-11-01',
            'invoice_date': '2025-11-01',
            'partner_id': partner_c.id,
            'line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 300.0,
                'price_unit': 1.0,
                'tax_ids': [(6, 0, self.company_data['default_tax_sale'].ids)],
            })]
        })
        last_month_invoice.action_post()

        credit_note_wizard = self.env['account.move.reversal'].create({
            'move_ids': last_month_invoice.ids,
            'reason': 'test',
            'date': '2025-12-01',
            'journal_id': self.company_data['default_journal_sale'].id,
        })

        refund = self.env['account.move'].browse(credit_note_wizard.refund_moves()['res_id'])
        refund.action_post()

        this_month_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'date': '2025-12-01',
            'invoice_date': '2025-12-01',
            'partner_id': partner_c.id,
            'line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 100.0,
                'price_unit': 1.0,
                'tax_ids': [(6, 0, self.company_data['default_tax_sale'].ids)],
            })]
        })
        this_month_invoice.action_post()

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'date': '2025-12-01',
            'invoice_date': '2025-12-01',
            'partner_id': partner_c.id,
            'line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 200.0,
                'price_unit': 1.0,
                'tax_ids': [(6, 0, self.company_data['default_tax_purchase'].ids)],
            })]
        })
        bill.action_post()
        foreign_currency = self.setup_other_currency('USD', rates=[
            ('2016-01-01', 3.0),
            ('2017-01-01', 2.0),
        ])
        bill_forex = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'date': '2025-12-06',
            'invoice_date': '2025-12-03',
            'partner_id': partner_c.id,
            'currency_id': foreign_currency.id,
            'line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 200.0,
                'price_unit': 1.0,
                'tax_ids': [Command.set(self.company_data['default_tax_purchase'].ids)],
            })]
        })

        bill_forex.action_post()

        ChartTemplate = self.env['account.chart.template']
        allocation_acc = ChartTemplate.ref('lu_2020_account_6492')
        provision_acc = ChartTemplate.ref('lu_2011_account_1881')
        self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2018-12-31',
            'line_ids': [
                Command.create({
                    'name': 'Distribute earnings',
                    'account_id': provision_acc.id,
                    'debit': 13490.0,
                    'credit': 0.0,
                }),
                Command.create({
                    'name': 'Distribute earnings',
                    'account_id': allocation_acc.id,
                    'debit': 0.0,
                    'credit': 13490.0,
                }),
            ]
        }).action_post()

        self.env.flush_all()

        report = self.env.ref('account_reports.general_ledger_report')
        options = self._generate_options('2025-12-01', '2025-12-31')
        with tools.file_open("l10n_lu_reports/tests/xml/expected_faia_values_2025.xml", "rb") as expected_xml:
            self.assertXmlTreeEqual(
                self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].l10n_lu_export_saft_to_xml(options)['file_content']),
                self.get_xml_tree_from_string(expected_xml.read())
            )
