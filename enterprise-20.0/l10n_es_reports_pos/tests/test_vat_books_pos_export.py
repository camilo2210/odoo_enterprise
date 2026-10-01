# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.l10n_es_reports_pos.tests.common import TestL10nEsVATBooksPosCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestVATBooksPosExportXLSX(TestL10nEsVATBooksPosCommon):
    """Test XLSX export of VAT books with POS orders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.fakenow = datetime.datetime(2024, 1, 1)
        cls.startClassPatcher(freeze_time(cls.fakenow))

    def _get_sheet_vals_for_order(self, order):
        """Return VAT book sheet line_vals for a given POS order (EDI mode)."""
        invoice_name = self.env['l10n_es.vat.books.report.handler']._l10n_es_libros_get_pos_order_invoice_number(order)
        return sorted(
            (
                lv for lv in self.get_vat_book_sheet_line_vals()
                if lv['invoice_number'] == invoice_name
            ),
            key=lambda lv: lv['tax_rate'],
        )

    def _create_pos_order_and_get_sheet_vals(self, **kwargs):
        """Helper: create one order and return its sheet line_vals."""
        order = self._create_pos_order(**kwargs)
        sheet_vals = self._get_sheet_vals_for_order(order)
        self.assertEqual(len(sheet_vals), 1)
        return order, sheet_vals[0]

    def assertSheetLineVals(self, sheet_vals, expected):
        """Assert that sheet_vals contains all key-value pairs in expected."""
        self.assertDictEqual({k: sheet_vals[k] for k in expected}, expected)

    def test_pos_order_simple_xlsx_export(self):
        """Simple POS order with 21% VAT produces correct VAT book line."""
        order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'invoice_number': order.pos_reference,
            'partner_name': 'Spanish Partner',
            'partner_nif_id': '59962470K',
            'base_amount': 100.0,
            'total_amount': 121.0,
            'tax_rate': 21.0,
            'taxed_amount': 21.0,
            'income_computable': 100.0,
            'operation_code': '01',
            'operation_qualification': 'S1',
            'invoice_type': 'F2',
            'income_concept': 'I01',
            'year': 2024,
        })

    def test_pos_order_anonymous_customer_xlsx_export(self):
        """POS order without a customer has empty partner fields."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'partner_name': '',
            'partner_nif_id': '',
            'base_amount': 100.0,
            'total_amount': 121.0,
        })

    def test_pos_order_eu_customer_xlsx_export(self):
        """EU customer gets NIF type 02."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_eu,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'partner_name': 'French Partner',
            'partner_nif_id': 'FR23334175221',
            'partner_nif_type': '02',
            'base_amount': 100.0,
        })

    def test_pos_order_intl_customer_xlsx_export(self):
        """Non-EU international customer gets NIF type 06 with country code."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_intl,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'partner_name': 'US Company',
            'partner_nif_id': 'US66655598K',
            'partner_nif_type': '06',
            'partner_nif_code': 'US',
        })

    def test_pos_order_multiple_items_xlsx_export(self):
        """Multiple lines with the same tax are aggregated into one report line."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 2.0), (self.product, 0.5)],
            payments=[(self.bank_pm1, 302.5)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'base_amount': 250.0,
            'total_amount': 302.5,
            'tax_rate': 21.0,
            'taxed_amount': 52.5,
            'income_computable': 250.0,
        })

    def test_pos_order_mixed_tax_xlsx_export(self):
        """Order with 10% and 21% lines produces two separate VAT book lines."""
        order = self._create_pos_order(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 1.0), (self.product_10, 1.0)],
            payments=[(self.bank_pm1, 231.0)],
        )
        sheet_vals_10, sheet_vals_21 = self._get_sheet_vals_for_order(order)

        self.assertSheetLineVals(sheet_vals_10, {
            'tax_rate': 10.0, 'base_amount': 100.0,
            'taxed_amount': 10.0, 'total_amount': 110.0, 'income_computable': 100.0,
        })
        self.assertSheetLineVals(sheet_vals_21, {
            'tax_rate': 21.0, 'base_amount': 100.0,
            'taxed_amount': 21.0, 'total_amount': 121.0, 'income_computable': 100.0,
        })

    def test_pos_order_mixed_tax_refund_xlsx_export(self):
        """Refund of a mixed-tax order produces R5 lines with negative amounts."""
        with self.with_pos_session():
            order_data = self.create_ui_order_data(
                customer=self.partner_spanish,
                pos_order_lines_ui_args=[(self.product, 1.0), (self.product_10, 1.0)],
                payments=[(self.bank_pm1, 231.0)],
            )
            results = self.env['pos.order'].sync_from_ui([order_data])
            order = self.env['pos.order'].browse(results['pos.order'][0]['id'])

            refund_action = order.refund()
            refund = self.env['pos.order'].browse(refund_action['res_id'])
            payment_context = {'active_ids': refund.ids, 'active_id': refund.id}
            refund_payment = self.env['pos.make.payment'].with_context(**payment_context).create({
                'amount': refund.amount_total,
                'payment_method_id': self.bank_pm1.id,
            })
            refund_payment.with_context(**payment_context).check()

        with self.with_pos_edi_mode('tbai'):
            sheet_vals_list = sorted(
                self.env['l10n_es.vat.books.report.handler']._l10n_es_libros_get_pos_order_sheet_line_vals(refund),
                key=lambda lv: lv['tax_rate'],
            )
        sheet_vals_10, sheet_vals_21 = sheet_vals_list

        self.assertSheetLineVals(sheet_vals_10, {
            'invoice_type': 'R5', 'tax_rate': 10.0,
            'base_amount': -100.0, 'taxed_amount': -10.0, 'total_amount': -110.0,
        })
        self.assertSheetLineVals(sheet_vals_21, {
            'invoice_type': 'R5', 'tax_rate': 21.0,
            'base_amount': -100.0, 'taxed_amount': -21.0, 'total_amount': -121.0,
        })

    def test_pos_order_decimal_amounts_xlsx_export(self):
        """Fractional quantities produce correctly rounded amounts."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 0.33)],
            payments=[(self.bank_pm1, 39.93)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'base_amount': 33.0, 'total_amount': 39.93, 'tax_rate': 21.0,
        })

    def test_pos_order_period_xlsx_export(self):
        """POS order date is mapped to the correct quarterly period."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        self.assertSheetLineVals(sheet_vals, {'period': '01', 'year': 2024})

    def test_pos_order_activity_code_iae_group_xlsx_export(self):
        """IAE group 'A036533' maps to activity_code A, type 03, group 6533."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 1.0)],
            payments=[(self.bank_pm1, 121.0)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'activity_code': 'A',
            'activity_type': '03',
            'activity_group': '6533',
        })

    def test_pos_order_xlsx_export_low_amount(self):
        """Very small order amounts are handled without rounding errors."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            pos_order_lines_ui_args=[(self.product, 0.01)],
            payments=[(self.bank_pm1, 1.21)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'base_amount': 1.0, 'total_amount': 1.21, 'tax_rate': 21.0,
        })

    def test_pos_order_xlsx_export_high_amount(self):
        """Large amounts are handled correctly."""
        _order, sheet_vals = self._create_pos_order_and_get_sheet_vals(
            customer=self.partner_spanish,
            pos_order_lines_ui_args=[(self.product, 3.2)],
            payments=[(self.bank_pm1, 387.2)],
        )
        self.assertSheetLineVals(sheet_vals, {
            'base_amount': 320.0, 'total_amount': 387.2, 'tax_rate': 21.0,
        })

    def test_pos_order_level_xlsx_export_has_one_line_per_pos_order(self):
        """With TBAI/Verifactu EDI, each POS order generates its own VAT book line."""
        orders = self._create_pos_orders([
            {
                'customer': self.partner_spanish,
                'pos_order_lines_ui_args': [(self.product, 1.0)],
                'payments': [(self.bank_pm1, 121.0)],
            },
            {
                'customer': self.partner_spanish,
                'pos_order_lines_ui_args': [(self.product, 2.0)],
                'payments': [(self.bank_pm1, 242.0)],
            },
        ])
        sheet_vals = self.get_vat_book_sheet_line_vals()

        self.assertEqual(len(sheet_vals), 2)
        self.assertEqual(
            {sv['invoice_number'] for sv in sheet_vals},
            set(orders.mapped('pos_reference')),
        )
        self.assertEqual({sv['base_amount'] for sv in sheet_vals}, {100.0, 200.0})
        for sv in sheet_vals:
            self.assertEqual(sv['invoice_type'], 'F2')

    def test_pos_order_level_xlsx_export_skips_invoiced_pos_orders(self):
        """POS orders linked to an invoice are excluded from per-order EDI export."""
        orders = self._create_pos_orders([
            {
                'customer': self.partner_spanish,
                'pos_order_lines_ui_args': [(self.product, 1.0)],
                'payments': [(self.bank_pm1, 121.0)],
            },
            {
                'customer': self.partner_spanish,
                'pos_order_lines_ui_args': [(self.product, 2.0)],
                'payments': [(self.bank_pm1, 242.0)],
            },
        ])
        invoice = self.init_invoice(
            'out_invoice',
            partner=self.partner_spanish,
            invoice_date='2024-01-01',
            amounts=[100],
            taxes=self.tax21_goods,
            post=True,
        )
        smaller_order = orders.sorted('amount_total')[0]
        larger_order = orders - smaller_order
        smaller_order.write({'account_move': invoice.id})

        sheet_vals = self.get_vat_book_sheet_line_vals()
        invoice_numbers = {sv['invoice_number'] for sv in sheet_vals}

        self.assertNotIn(smaller_order.pos_reference, invoice_numbers)
        self.assertIn(larger_order.pos_reference, invoice_numbers)
        larger_sv = next(sv for sv in sheet_vals if sv['invoice_number'] == larger_order.pos_reference)
        self.assertEqual(larger_sv['base_amount'], 200.0)

    def test_pos_closing_entry_xlsx_export_single_line_without_order_level_edi(self):
        """Without EDI, the session closing entry is exported as a single F4 line."""
        self._create_pos_orders([
            {
                'customer': self.partner_spanish,
                'pos_order_lines_ui_args': [(self.product, 1.0)],
                'payments': [(self.bank_pm1, 121.0)],
            },
            {
                'customer': self.partner_spanish,
                'pos_order_lines_ui_args': [(self.product, 2.0)],
                'payments': [(self.bank_pm1, 242.0)],
            },
        ])
        line_vals_list = self.get_pos_closing_sheet_line_vals()

        self.assertEqual(len(line_vals_list), 1)
        self.assertSheetLineVals(line_vals_list[0], {
            'invoice_type': 'F4',
            'invoice_number': 'PoS Shop Test - 000001',
            'invoice_final_number': 'PoS Shop Test - 000002',
            'base_amount': 300.0,
            'tax_rate': 21.0,
            'taxed_amount': 63.0,
            'total_amount': 363.0,
        })
