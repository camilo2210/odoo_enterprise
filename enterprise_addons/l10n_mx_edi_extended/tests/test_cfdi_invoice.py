# -*- coding: utf-8 -*-
from datetime import timedelta

from .common import TestMxExtendedEdiCommon
from odoo import fields, Command
from odoo.addons.l10n_mx_edi.tests.common import EXTERNAL_MODE, RATE_WITH_USD, TEST_RATE_WITH_USD
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install', *TestMxExtendedEdiCommon.extra_tags)
class TestCFDIInvoice(TestMxExtendedEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_invoice_external_trade(self):
        chf = self.setup_other_currency('CHF', rates=[(self.frozen_today - timedelta(days=1), 17.0)])

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='02',
                currency_id=chf.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 17000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'l10n_mx_edi_qty_umt': 5.0,
                        'l10n_mx_edi_price_unit_umt': self.product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            # The format of the customs number is incorrect.
            with self.assertRaises(ValidationError):
                invoice.invoice_line_ids.l10n_mx_edi_customs_number = '15  48  30  001234'

            invoice.invoice_line_ids.l10n_mx_edi_customs_number = '15  48  3009  0001234,15  48  3009  0001235'
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade')

    def test_invoice_external_trade_delivery_address(self):
        chf = self.setup_other_currency('CHF', rates=[(self.frozen_today - timedelta(days=1), 17.0)])

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='02',
                currency_id=chf.id,
                partner_shipping_id=self.partner_us.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'l10n_mx_edi_qty_umt': 5.0,
                        'l10n_mx_edi_price_unit_umt': self.product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade_delivery_address')

    def test_invoice_external_trade_two_lines_same_product(self):
        """
        Check that the unit price (ValorUnitarioAduana) is well calculated in case
        of having two lines with same product but different price and/or quantity.
        """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='02',
                currency_id=self.usd.id,
                partner_shipping_id=self.partner_us.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2000.0,
                        'quantity': 3,
                        'l10n_mx_edi_qty_umt': 3.0,
                        'l10n_mx_edi_price_unit_umt': 2000.0,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 4000.0,
                        'quantity': 5,
                        'l10n_mx_edi_qty_umt': 5.0,
                        'l10n_mx_edi_price_unit_umt': 4000.0,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade_two_lines_same_product')

    def test_invoice_external_trade_more_digits(self):
        self.env.ref('product.decimal_price').digits = 6
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='02',
                currency_id=self.usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3114.515000,
                        'quantity': 1,
                        'l10n_mx_edi_qty_umt': 11.0,
                        'l10n_mx_edi_price_unit_umt': 283.137727,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade_more_digits')

    def test_invoice_external_trade_null_qty(self):
        chf = self.setup_other_currency('CHF', rates=[(self.frozen_today - timedelta(days=1), 17.0)])

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='02',
                currency_id=chf.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 17000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'l10n_mx_edi_qty_umt': 0.0,
                        'l10n_mx_edi_price_unit_umt': self.product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade_null_qty')

    def test_invoice_external_trade_service(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                currency_id=self.usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.service_product.id,
                        'price_unit': 1000.0,
                        'quantity': 1,
                        'discount': 20.0,
                        'l10n_mx_edi_qty_umt': 1.0,
                        'l10n_mx_edi_price_unit_umt': self.service_product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 17000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'l10n_mx_edi_qty_umt': 5.0,
                        'l10n_mx_edi_price_unit_umt': self.product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade_service')

    def test_global_invoice_with_issued_address_on_journal(self):
        branch_address = self.env['res.partner'].create({
            'name': 'Sucursal Mexico City',
            'street': 'Paseo de la Reforma 222',
            'zip': '06600',
            'city': 'Cuauhtémoc',
            'state_id': self.env.ref('base.state_mx_mex').id,
            'country_id': self.env.ref('base.mx').id,
            'type': 'other',
        })

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 17000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'l10n_mx_edi_qty_umt': 0.0,
                        'l10n_mx_edi_price_unit_umt': self.product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )

            invoice.journal_id.l10n_mx_address_issued_id = branch_address

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))

            self._assert_global_invoice_cfdi_from_invoices(invoice, "test_global_invoice_with_issued_address_on_journal")

    def test_invoice_external_trade_type_04(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='04',
                currency_id=self.usd.id,
                invoice_incoterm_id=False,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'quantity': 1,
                        'discount': 100.0,
                        'l10n_mx_edi_qty_umt': 1.0,
                        'l10n_mx_edi_price_unit_umt': self.product.lst_price,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            if RATE_WITH_USD == TEST_RATE_WITH_USD or not EXTERNAL_MODE:
                self._assert_invoice_cfdi(invoice, 'test_invoice_external_trade_type_04')

    def test_invoice_pdf_cfdi_decode_external_trade_and_customs(self):
        # Without customs numbers
        with self.mx_external_setup(self.frozen_today), self.with_mocked_pac_sign_success():
            invoice = self._create_invoice_mx(
                currency_id=self.usd,
                l10n_mx_edi_external_trade_type='02',
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        price_unit=17000.0,
                        quantity=5,
                        l10n_mx_edi_qty_umt=5.0,
                        l10n_mx_edi_price_unit_umt=self.product.lst_price,
                        tax_ids=[],
                    ),
                    self._prepare_invoice_line(
                        product_id=self.service_product,
                        price_unit=1000.0,
                        quantity=1,
                        l10n_mx_edi_qty_umt=1.0,
                        l10n_mx_edi_price_unit_umt=self.service_product.lst_price,
                        tax_ids=[],
                    ),
                ]
            )
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        cfdi_infos = invoice._l10n_mx_edi_get_extra_invoice_report_values()
        cfdi_infos_expected_values = {
            'tax_registration_id_number': '123456789',
            'ext_trade_certificate_key': 'A1',
            'ext_trade_certificate_source': 'No',
            'ext_trade_nb_certificate_origin': '0',
            'ext_trade_certificate_origin': '',
            'ext_trade_nb_reliable_exporter': '',
            'ext_trade_incoterm': 'FCA',
            'ext_trade_rate_usd': '16.999500',
            'ext_trade_total_usd': '85000.00',
        }
        current_cfdi_vals = {}
        for key in cfdi_infos_expected_values:
            if key not in cfdi_infos:
                continue
            current_cfdi_vals[key] = cfdi_infos[key]
        self.assertDictEqual(current_cfdi_vals, cfdi_infos_expected_values)
        self.assertEqual(len(cfdi_infos['mercancias_list']), 2)

        mercancias_expected_values = [
            {
                'identification_no': 'product_mx',
                'fraccion_arancelaria': '7212100399',
                'customs_quantity': 5.0,
                'customs_unit': '01',
                'customs_unit_value': 17000.00,
                'dollar_value': 85000.0000,
            },
            {
                'identification_no': 'service_mx',
                'fraccion_arancelaria': None,
                'customs_quantity': 1.0,
                'customs_unit': '99',
                'customs_unit_value': 0.0,
                'dollar_value': 0.0,
            },
        ]

        for mercancia, expected_vals in zip(cfdi_infos['mercancias_list'], mercancias_expected_values):
            current_vals = {}
            for key in expected_vals:
                if key not in mercancia:
                    continue
                current_vals[key] = mercancia[key]
            self.assertDictEqual(current_vals, expected_vals)

        # Test customs number
        with self.mx_external_setup(self.frozen_today), self.with_mocked_pac_sign_success():
            invoice = self._create_invoice_mx(
                l10n_mx_edi_external_trade_type='01',
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        l10n_mx_edi_customs_number='15  48  3009  0001234, 15  48  3009  0001235'
                    ),
                ]
            )
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        cfdi_infos = invoice._l10n_mx_edi_get_extra_invoice_report_values()
        self.assertEqual(cfdi_infos['conceptos_list'][0]['customs_numbers'], '15  48  3009  0001234, 15  48  3009  0001235')
