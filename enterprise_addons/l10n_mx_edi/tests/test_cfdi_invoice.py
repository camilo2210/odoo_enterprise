from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from lxml import etree

from dateutil.relativedelta import relativedelta

from .common import TestMxEdiCommon, EXTERNAL_MODE
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import misc, html2plaintext
from odoo.tools.misc import file_open
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import CFDI_DATE_FORMAT
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install', *TestMxEdiCommon.extra_tags)
class TestCFDIInvoice(TestMxEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_invoice_misc_business_values(self):
        for move_type, output_file in (
            ('out_invoice', 'test_misc_business_values_invoice'),
            ('out_refund', 'test_misc_business_values_credit_note')
        ):
            with self.mx_external_setup(self.frozen_today), self.subTest(move_type=move_type):
                invoice = self._create_invoice_mx(
                    invoice_incoterm_id=self.env.ref('account.incoterm_FCA').id,
                    invoice_line_ids=[
                        Command.create({
                            'product_id': self.product.id,
                            'price_unit': 2000.0,
                            'quantity': 5,
                            'discount': 20.0,
                        }),
                        # Product with Predial Account
                        Command.create({
                            'product_id': self._create_product_mx(l10n_mx_edi_predial_account='123456789').id,
                            'quantity': 3.0,
                            'tax_ids': [],
                        }),
                        # Ignored lines by the CFDI:
                        Command.create({
                            'product_id': self.product.id,
                            'price_unit': 2000.0,
                            'quantity': 0.0,
                        }),
                        Command.create({
                            'product_id': self.product.id,
                            'price_unit': 0.0,
                            'quantity': 10.0,
                        }),
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()
                self._assert_invoice_cfdi(invoice, output_file)

    def test_customer_in_mx(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_customer_in_mx_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_customer_in_mx_pay')

    def test_customer_in_us(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(partner_id=self.partner_us.id)
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_customer_in_us_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_customer_in_us_pay')

    def test_customer_no_country(self):
        with self.mx_external_setup(self.frozen_today):
            self.partner_us.country_id = None
            invoice = self._create_invoice_mx(partner_id=self.partner_us.id)
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_customer_no_country_inv')

    def test_customer_in_mx_to_public(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_customer_in_mx_to_public_inv')

    def test_customer_mx_incomplete_address(self):
        with self.mx_external_setup(self.frozen_today):
            for zip_code, country in (['33826', None], [None, self.env.ref('base.mx')], [None, None]):
                self.partner_mx.zip = zip_code
                self.partner_mx.country_id = country
                invoice = self._create_invoice_mx()
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()
                self.assertTrue(invoice.l10n_mx_edi_cfdi_to_public)
                self._assert_invoice_cfdi(invoice, 'test_customer_mx_incomplete_address')

    def test_invoice_taxes_no_tax(self):
        with self.mx_external_setup(self.frozen_today):
            # Test the invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'tax_ids': [],
                    })
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_no_tax_invoice')

            # Test the payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_no_tax_payment')

    def test_invoice_taxes_exento_and_zero(self):
        with self.mx_external_setup(self.frozen_today):
            # Test the invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(self.tax_0_exento.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2000.0,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3000.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_exento_and_zero_invoice')

            # Test the payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_exento_and_zero_payment')

    def test_invoice_taxes_withholding(self):
        with self.mx_external_setup(self.frozen_today):
            # Test the invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set((self.tax_16 + self.tax_10_ret_isr + self.tax_10_67_ret).ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_withholding_invoice')

            # Test the payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_withholding_payment')

    def test_invoice_taxes_ieps(self):
        with self.mx_external_setup(self.frozen_today):
            # Test the invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set((self.tax_8_ieps + self.tax_0).ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2000.0,
                        'tax_ids': [Command.set((self.tax_53_ieps + self.tax_16).ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_ieps_invoice')

            # Test the payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_ieps_payment')

    def test_invoice_taxes_local(self):
        local_fixed_tax = self.env['account.tax'].create({
            'name': 'local fixed tax',
            'amount': 5.0,
            'amount_type': 'fixed',
            'l10n_mx_tax_type': 'local',
            'l10n_mx_factor_type': 'Cuota',
            'tax_group_id': self.local_tax_group.id,
        })
        with self.mx_external_setup(self.frozen_today):
            # Test the invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(self.local_tax_16_transferred.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2000.0,
                        'tax_ids': [Command.set(self.local_tax_8_withholding.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3000.0,
                        'tax_ids': [Command.set(self.local_tax_3_5_withholding.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 4000.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2500.0,
                        'quantity': 2.0,
                        'tax_ids': [Command.set(local_fixed_tax.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_local_invoice')

            # Test the payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_local_payment')

    def test_invoice_taxes_cuota(self):
        self.env['decimal.precision'].search([('name', '=', 'Product Price')]).digits = 6
        self.partner_mx.l10n_mx_edi_ieps_breakdown = True
        tax_cuota = self.fixed_tax(
            name="Cuota 14.0163",
            amount=14.0163,
            l10n_mx_factor_type='Cuota',
            l10n_mx_tax_type='ieps',
            sequence=10.0,
        )

        with self.mx_external_setup(self.frozen_today):
            # Test the first invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 523.448276,
                        'tax_ids': [Command.set(tax_cuota.ids)],
                    })
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_cuota_1_invoice')

            # Test the first payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_cuota_1_payment')

            # Test the second invoice CFDI.
            tax_8_include_base_amount = self.tax_8.copy(default={'name': "tax_8_include_base_amount"})
            tax_8_include_base_amount.include_base_amount = True
            tax_8_include_base_amount.sequence = 9
            self.tax_1_25_sale_withholding.sequence = 8
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 4000.0,
                        'tax_ids': [Command.set((tax_8_include_base_amount + tax_cuota + self.tax_1_25_sale_withholding).ids)],
                    })
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_cuota_2_invoice')

            # Test the second payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_cuota_2_payment')

    def test_invoice_taxes_cuota_partial_payment(self):
        """ For Cuota (fixed amount per unit) IEPS taxes, the SAT requires that
        ImporteDR == round(BaseDR * TasaOCuotaDR) on every TrasladoDR of a
        payment complement, including for partial payments. Independently
        prorating base and importe can break this invariant due to rounding;
        the payment CFDI generation must recompute importe from the prorated
        base for Cuota taxes. """
        self.partner_mx.l10n_mx_edi_ieps_breakdown = True
        tax_cuota = self.fixed_tax(
            name="Cuota 26.2569",
            amount=26.2569,
            l10n_mx_factor_type='Cuota',
            l10n_mx_tax_type='ieps',
        )

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 350.0,
                        'price_unit': 10.0,
                        'tax_ids': [Command.set(tax_cuota.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_cuota_partial_payment_inv')

            # Pay one third: the prorata isn't an exact decimal, so BaseDR keeps 6 decimals
            # to keep ImporteDR = round(BaseDR * TasaOCuotaDR) accurate.
            payment = self._register_payment(
                invoice,
                amount=invoice.amount_total / 3.0,
            )
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_cuota_partial_payment_pay')

    def test_invoice_taxes_cuota_with_custom_tax(self):
        self.ensure_installed('account_tax_python')

        self.partner_mx.l10n_mx_edi_ieps_breakdown = True
        tax_cuota = self.python_tax(
            formula="6.4555 * quantity",
            l10n_mx_factor_type='Cuota',
            l10n_mx_tax_type='ieps',
            price_include_override='tax_included',
            include_base_amount=True,
            sequence=1,
        )
        self.tax_16.price_include_override = 'tax_included'
        self.tax_16.sequence = 2

        with self.mx_external_setup(self.frozen_today):
            # Test the invoice CFDI.
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 43775.0,
                        'price_unit': 18.33,
                        'tax_ids': [Command.set((tax_cuota + self.tax_16).ids)],
                    })
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_taxes_cuota_with_custom_tax_invoice')

            # Test the payment CFDI.
            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_invoice_taxes_cuota_with_custom_tax_payment')

    def test_tax_objected_01(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'tax_ids': [],
            })])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_01_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_01_pay')

    def test_tax_objected_02(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[
                Command.create({
                    'product_id': self.product.id,
                    'tax_ids': [Command.set(self.tax_16.ids)],
                }),
                Command.create({
                    'product_id': self.product.id,
                    'discount': 100.0,
                    'tax_ids': [Command.set(self.tax_16.ids)],
                }),
            ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_02_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_02_pay')

    def test_tax_objected_03(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'l10n_mx_edi_tax_object': '03',
                'tax_ids': [Command.set(self.tax_16.ids)],
            })])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_03_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_03_pay')

    def test_tax_objected_04(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[
                Command.create({
                    'product_id': self.product.id,
                    'discount': 100.0,
                    'tax_ids': [Command.set(self.tax_16.ids)],
                    'l10n_mx_edi_tax_object': '04',
                }),
                Command.create({
                    'product_id': self.product.id,
                    'tax_ids': [Command.set(self.tax_16.ids)],
                }),
            ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_04_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_04_pay')

    def test_tax_objected_05(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'l10n_mx_edi_tax_object': '05',
                'tax_ids': [Command.set(self.tax_16.ids)],
            })])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_05_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_05_pay')

    def test_tax_objected_06(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'tax_ids': [Command.set(self.tax_10_ret_isr.ids)],
            })])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_06_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_06_pay')

    def test_tax_objected_07(self):
        with self.mx_external_setup(self.frozen_today):
            self.partner_mx.l10n_mx_edi_ieps_breakdown = True
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'tax_ids': [Command.set((self.tax_10_ret_isr + self.tax_8_ieps).ids)],
            })])
            # When not specified, tax object should be 07 if ieps breakdown
            self.assertRecordValues(invoice.invoice_line_ids, [{'l10n_mx_edi_tax_object': '07'}])
            self.partner_mx.l10n_mx_edi_ieps_breakdown = False
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            # Generated cfdi should have tax object '07' and breakdown IEPS, even if it is not specified
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_07_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_07_pay')

    def test_tax_objected_08(self):
        with self.mx_external_setup(self.frozen_today):
            self.partner_mx.l10n_mx_edi_ieps_breakdown = True
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'l10n_mx_edi_tax_object': '08',
                'tax_ids': [Command.set((self.tax_10_ret_isr + self.tax_8_ieps).ids)],
            })])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            # No IEPS breakdown even if specified
            self._assert_invoice_cfdi(invoice, 'test_tax_objected_08_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_tax_objected_08_pay')

    def test_global_invoice_ieps_breakdown(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'tax_ids': [Command.set((self.tax_10_ret_isr + self.tax_8_ieps).ids)]
            })])

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
            # IEPS should display even if not set
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_global_invoice_ieps_breakdown')

    def test_invoice_addenda(self):
        # The test data for complementos in this test are not recognized by the SAT as valid.
        if EXTERNAL_MODE:
            return

        with self.mx_external_setup(self.frozen_today):
            addenda_1, addenda_2, complementos_1, complementos_2 = self.env['l10n_mx_edi.addenda'].create([
                {
                    'name': 'addenda simple',
                    'arch': """
                        <t t-xml-node="addenda">
                            <SimpleAddenda info="this is a simple addenda"/>
                        </t>
                    """,
                },
                {
                    'name': 'addenda with complex qweb',
                    'arch': """
                        <t><t t-xml-node="addenda"><t>
                            <t t-set="asdf" t-value="'this is a complex addenda'"/>
                            <t><t><ComplexAddenda t-att-info="asdf"/></t></t>
                        </t></t></t>
                    """,
                },
                {
                    'name': 'complementos simple',
                    'arch': """
                        <t t-xml-node="complemento">
                            <SimpleComplementos info="this is a simple complementos"/>
                        </t>
                    """,
                },
                {
                    'name': 'complementos with complex qweb',
                    'arch': """
                        <t t-xml-node="complemento"><t>
                            <t t-set="zxcv" t-value="'this is a complex complementos'"/>
                            <t><t><t><ComplexComplementos t-att-info="zxcv"/></t></t></t>
                        </t></t>
                    """,
                },
            ])

            for addenda_file, addenda_ids in (
                ('test_invoice_addenda_just_addenda', addenda_1 + addenda_2),
                ('test_invoice_addenda_just_complementos', complementos_1 + complementos_2),
                ('test_invoice_addenda_complex', addenda_1 + addenda_2 + complementos_1 + complementos_2),
            ):
                with self.subTest(addenda_file=addenda_file):
                    self.partner_mx.l10n_mx_edi_addenda_ids = addenda_ids
                    invoice = self._create_invoice_mx()
                    self.assertEqual(invoice.l10n_mx_edi_addenda_ids, addenda_ids)
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    self._assert_invoice_cfdi(invoice, addenda_file)

    def test_invoice_addenda_with_namespace(self):
        with self.mx_external_setup(self.frozen_today):
            addenda_donat = self.env['l10n_mx_edi.addenda'].create([{
                'name': 'Donatarias',
                'arch': """
                    <?xml version="1.0"?>
                    <t>
                        <t t-xml-node="comprobante">
                            <t t-namespace-key="donat" t-namespace-url="http://www.sat.gob.mx/donat/"/>
                            <t t-schema-locations="https://www.schema_url_1.com/ https://www.schema_url_2.com/"/>
                        </t>
                        <t t-xml-node="addenda">
                            <t t-set="my_journal" t-value="record.journal_id"/>
                            <donat:Donatarias
                                t-att-testJournalName="my_journal.name"
                                testCertificate="325-SAT-09-IV-E-77917"
                                testDate="01/06/2005"
                                testText="hello world"/>
                        </t>
                    </t>
                """,
            }])

            invoice = self._create_invoice_mx()
            invoice.l10n_mx_edi_addenda_ids = addenda_donat
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_addenda_with_namespace')

            # Manually check if schema_locations are correctly saved in the document XML
            # This is done because the previous assertXmlTreeEqual don't check inside the value inside xsi:schemaLocation
            document = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')[:1]
            self.assertTrue(
                expr=b'xsi:schemaLocation="https://www.schema_url_1.com/ https://www.schema_url_2.com/ ' in document.attachment_id.raw.content,
                msg="The schema_locations string must be saved in the generated XML.",
            )

    def test_invoice_addenda_with_multi_schema_location(self):
        """ Ensure the schema locations are sorted per groups and included in the end XML result. """
        with self.mx_external_setup(self.frozen_today):
            addenda_vals = []
            schema_locations_list = [
                "https://abcde.com https://zzzzz.com",
                "https://zzzzz.com https://abcde.com",
                "https://zzzzz.com https://zzzzz.com",
                "https://abcde.com https://abcde.com",
                "https://iiiii.com https://zzzzz.com",
                "https://iiiii.com https://zzzzz.com",  # duplicate lines will be removed
                "https://abcde.com https://abcde.com",
            ]
            for i, schema_locations in enumerate(schema_locations_list, start=1):
                addenda_vals.append({
                    'name': f'test_addenda_{i}',
                    'arch': f"""
                        <t t-xml-node="comprobante">
                            <t t-schema-locations="{schema_locations}"/>
                        </t>
                        <t t-xml-node="addenda">
                            <TestAddenda{i}/>
                        </t>
                    """,
                })

            invoice = self._create_invoice_mx()
            invoice.l10n_mx_edi_addenda_ids = self.env['l10n_mx_edi.addenda'].create(addenda_vals)
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            document = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')[:1]
            self.assertTrue(
                expr=b'xsi:schemaLocation="https://abcde.com https://abcde.com https://abcde.com https://zzzzz.com https://iiiii.com https://zzzzz.com '
                     b'https://zzzzz.com https://abcde.com https://zzzzz.com https://zzzzz.com ' in document.attachment_id.raw.content,
                msg="The schema_locations string must be filtered and sorted by line.",
            )

    def test_invoice_addenda_decode_errors(self):
        invalid_cases = (
            ("<InvalidBecauseNotWrapped/>", "Arch must contain `<t t-xml-node="),
            ("<t t-xml-node='badvalue'><InvalidBecauseNotWrapped/></t>", "Arch value of t-xml-node must be either"),
            ("""
                <t t-xml-node="comprobante">
                    <t t-schema-locations="value_one_have  multiple_space_before_value_two"/>
                </t>
                <t t-xml-node="addenda">
                    <ValidAddendaButBadSchema/>
                </t>
            """, "Schema locations must be separated by only one whitespace character."),
            ("<t/>", "must contain either complemento or addenda"),
            ("<t t-xml-node='addenda'></t><t t-xml-node='complemento'></t>", "must contain either complemento or addenda"),
        )

        for (bad_arch, expected_regex) in invalid_cases:
            with self.subTest(bad_arch=bad_arch):
                with self.assertRaisesRegex(ValidationError, expected_regex):
                    self.env['l10n_mx_edi.addenda'].create([{
                        'name': 'invalid_addenda',
                        'arch': bad_arch,
                    }])

    def test_invoice_negative_lines_zero_total(self):
        """ Test an invoice completely refunded by the negative lines. """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 12.0,
                        'tax_ids': [],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': -12.0,
                        'tax_ids': [],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'move_id': invoice.id,
                'state': 'invoice_sent',
                'attachment_id': False,
                'cancel_button_needed': False,
            }])

    def test_invoice_negative_lines_orphan_negative_line(self):
        """ Test an invoice in which a negative line failed to be distributed. """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 12.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': -2.0,
                        'tax_ids': [],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'move_id': invoice.id,
                'state': 'invoice_sent_failed',
            }])

    def test_invoice_negative_lines_on_multiple_lines(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': quantity,
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    })
                    for quantity, price_unit in (
                        (1.0, 326.4),
                        (1.0, 24.0),
                        (1.0, 172.8),
                        (1.0, 691.2),
                        (-1.0, 1149.6),
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_negative_lines_on_multiple_lines')

    def test_invoice_payment_policy(self):
        """ Ensure the invoice payment policy isn't override by the partner payment policy. """
        with self.mx_external_setup(self.frozen_today):
            self.partner_mx.l10n_mx_edi_payment_policy = 'PUE'
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 12.0,
                        'tax_ids': [],
                    }),
                ],
                l10n_mx_edi_payment_policy='PPD',
            )

        with self.with_mocked_pac_sign_success():
            invoice._l10n_mx_edi_cfdi_invoice_try_send()
        self.assertEqual(invoice.l10n_mx_edi_payment_policy, 'PPD')

    def test_global_invoice_negative_lines_zero_total(self):
        """ Test an invoice completely refunded by the negative lines. """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 12.0,
                        'tax_ids': [],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': -12.0,
                        'tax_ids': [],
                    }),
                ],
            )

            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'invoice_ids': invoice.ids,
                'state': 'ginvoice_sent',
                'attachment_id': False,
                'cancel_button_needed': False,
            }])

    def test_global_invoice_negative_lines_orphan_negative_line(self):
        """ Test a global invoice containing an invoice having a negative line that failed to be distributed. """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 12.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': -2.0,
                        'tax_ids': [],
                    }),
                ],
            )

            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'invoice_ids': invoice.ids,
                'state': 'ginvoice_sent_failed',
            }])

    def test_global_invoice_including_partial_refund(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 10.0,
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': -2.0,
                    }),
                ],
            )
            refund = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                move_type='out_refund',
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 3.0,
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': -1.0,
                    }),
                ],
                reversed_entry_id=invoice.id,
            )

            invoices = invoice + refund
            with self.with_mocked_pac_sign_success():
                # Calling the global invoice on the invoice will include the refund automatically.
                self._create_invoices_global_invoice(invoice)
            self._assert_global_invoice_cfdi_from_invoices(invoices, 'test_global_invoice_including_partial_refund')

            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'invoice_ids': invoices.ids,
                'state': 'ginvoice_sent',
            }])

    def test_global_invoice_including_full_refund(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 10.0,
                    }),
                ],
            )
            refund = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                move_type='out_refund',
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 10.0,
                    }),
                ],
                reversed_entry_id=invoice.id,
            )

            invoices = invoice + refund
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoices)
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'invoice_ids': invoices.ids,
                'state': 'ginvoice_sent',
                'attachment_id': False,
            }])

    def test_global_invoice_not_allowed_refund(self):
        with self.mx_external_setup(self.frozen_today):
            refund = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                move_type='out_refund',
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 3.0,
                    }),
                ],
            )
            with self.assertRaises(UserError):
                self._create_invoices_global_invoice(refund)

    def test_global_invoice_refund_after(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 10.0,
                    }),
                ],
            )

            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self.assertRecordValues(invoice.l10n_mx_edi_invoice_document_ids, [{
                'invoice_ids': invoice.ids,
                'state': 'ginvoice_sent',
            }])

            refund = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                move_type='out_refund',
                invoice_date_due=self.frozen_today,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': 3.0,
                    }),
                ],
                reversed_entry_id=invoice.id,
            )
            with self.assertRaises(UserError):
                self._create_invoices_global_invoice(invoice)
            with self.with_mocked_pac_sign_success():
                self.env['account.move.send.wizard']\
                    .with_context(active_model=refund._name, active_ids=refund.ids)\
                    .create({})\
                    .action_send_and_print()
            self._assert_invoice_cfdi(refund, 'test_global_invoice_refund_after')

            self.assertRecordValues(refund.l10n_mx_edi_invoice_document_ids, [{
                'move_id': refund.id,
                'invoice_ids': refund.ids,
                'state': 'invoice_sent',
            }])

    def test_invoice_company_branch(self):
        with self.mx_external_setup(self.frozen_today - relativedelta(hours=1)):
            self.env.company.write({
                'child_ids': [Command.create({
                    'name': 'Branch A',
                    'zip': '85120',
                })],
            })
            branch = self.env.company.child_ids
            key = self.env['certificate.key'].create({
                'content': self.file_read('l10n_mx_edi/demo/pac_credentials/certificate.key'),
                'password': '12345678a',
                'company_id': branch.id,
            })
            certificate = self.env['certificate.certificate'].create({
                'content': self.file_read('l10n_mx_edi/demo/pac_credentials/certificate.cer'),
                'private_key_id': key.id,
                'company_id': branch.id,
            })
            branch.l10n_mx_edi_certificate_ids = certificate
            self.cr.precommit.run()  # load the CoA

            self.assertRecordValues(self.env.company, [{
                'l10n_mx_edi_global_invoice_sequence_id': False,
                'l10n_mx_edi_global_invoice_sequence_prefix': 'GINV/',
            }])

            self.assertRecordValues(branch, [{
                'l10n_mx_edi_global_invoice_sequence_id': False,
                'l10n_mx_edi_global_invoice_sequence_prefix': 'GINV/',
            }])

            self.product.company_id = branch

            # Invoice.
            invoice = self._create_invoice_mx(company_id=branch.id)
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_invoice_company_branch_inv')

            # Global invoice using the sequence of the root company.
            invoice = self._create_invoice_mx(company_id=branch.id, l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_invoice_company_branch_ginvoice_1')

            # Global invoice with a custom global invoice sequence on the branch.
            branch.l10n_mx_edi_global_invoice_sequence_prefix = "SAL/"

            self.assertRecordValues(branch, [{
                'l10n_mx_edi_global_invoice_sequence_prefix': 'SAL/',
            }])
            self.assertTrue(branch.l10n_mx_edi_global_invoice_sequence_id)

            invoice = self._create_invoice_mx(company_id=branch.id, l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_invoice_company_branch_ginvoice_2')

    def test_invoice_then_refund(self):
        # Create an invoice then sign it.
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                wizard = self.env['account.move.send.wizard']\
                    .with_context(active_model=invoice._name, active_ids=invoice.ids)\
                    .create({})
                wizard.action_send_and_print()
            self._assert_invoice_cfdi(invoice, 'test_invoice_then_refund_1')

            # You are no longer able to create a global invoice.
            with self.assertRaises(UserError):
                self._create_invoices_global_invoice(invoice)

            # Create a refund.
            results = self.env['account.move.reversal']\
                .with_context(active_model='account.move', active_ids=invoice.ids)\
                .create({
                    'reason': "turlututu",
                    'journal_id': invoice.journal_id.id,
                })\
                .refund_moves()
            refund = self.env['account.move'].browse(results['res_id'])
            refund.auto_post = 'no'
            refund.action_post()

            # You can't make a global invoice for it.
            with self.assertRaises(UserError):
                self._create_invoices_global_invoice(refund)

            # Create the CFDI and sign it.
            with self.with_mocked_pac_sign_success(), self.with_mocked_pac_cancel_success():
                self.env['account.move.send.wizard']\
                    .with_context(active_model=refund._name, active_ids=refund.ids)\
                    .create({})\
                    .action_send_and_print()
            self._assert_invoice_cfdi(refund, 'test_invoice_then_refund_2')
            self.assertRecordValues(refund, [{
                'l10n_mx_edi_cfdi_origin': f'01|{invoice.l10n_mx_edi_cfdi_uuid}',
            }])

    def test_global_invoice_then_refund(self):
        # Create a global invoice and sign it.
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_global_invoice_then_refund_1')

            # You are not able to create an invoice for it.
            wizard = self.env['account.move.send.wizard']\
                .with_context(active_model=invoice._name, active_ids=invoice.ids)\
                .create({})
            self.assertFalse(wizard.extra_edi_checkboxes and wizard.extra_edi_checkboxes.get('mx_cfdi'))

            # Refund the invoice.
            results = self.env['account.move.reversal']\
                .with_context(active_model='account.move', active_ids=invoice.ids)\
                .create({
                    'reason': "turlututu",
                    'journal_id': invoice.journal_id.id,
                })\
                .refund_moves()
            refund = self.env['account.move'].browse(results['res_id'])
            refund.auto_post = 'no'
            refund.action_post()

            # You can't do a global invoice for a refund
            with self.assertRaises(UserError):
                self._create_invoices_global_invoice(refund)

            # Sign the refund.
            with self.with_mocked_pac_sign_success():
                self.env['account.move.send.wizard']\
                    .with_context(active_model=refund._name, active_ids=refund.ids)\
                    .create({})\
                    .action_send_and_print()
            self._assert_invoice_cfdi(refund, 'test_global_invoice_then_refund_2')

    def test_global_invoice_foreign_currency(self):
        with self.mx_external_setup(self.frozen_today):
            usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(self.frozen_today, days=1), 1 / 17.0398)])
            invoice1 = self._create_invoice_mx(currency_id=usd.id, l10n_mx_edi_cfdi_to_public=True)
            invoice2 = self._create_invoice_mx(l10n_mx_edi_cfdi_to_public=True)
            invoices = invoice1 + invoice2

            with self.with_mocked_pac_sign_success():
                with self.assertRaisesRegex(UserError, "You can only process invoices sharing the same currency."):
                    self._create_invoices_global_invoice(invoices)
                self._create_invoices_global_invoice(invoice1)
                self._create_invoices_global_invoice(invoice2)
            self._assert_global_invoice_cfdi_from_invoices(invoice1, "test_global_invoice_foreign_currency")

    def test_invoice_send_and_print_fallback_pdf(self):
        # Trigger an error when generating the CFDI
        self.product.unspsc_code_id = False

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                        'tax_ids': [Command.set(self.tax_0.ids)],
                    }),
                ],
            )
            invoice.with_context(skip_invoice_sync=True)._generate_and_send(allow_fallback_pdf=True)
            self.assertFalse(invoice.invoice_pdf_report_id, "invoice_pdf_report_id shouldn't be set with the proforma PDF.")

    def test_import_cfdi_fail(self):
        """Test that no EDI document is created when importing invalid CFDI XML."""
        subtests = [
            {
                # Case document is not a CFDI with TipoComprobante I or E
                'file_name': 'test_import_payment_fail',
                'expected_message': 'The imported file is not a valid CFDI Invoice.',
                'type': 'sale',
            }, {
                # Case document is not on purchase or sale journal
                'file_name': 'test_import_invoice',
                'expected_message': 'Import of CFDI Invoice documents is only supported on purchase or sale journals.',
                'type': 'misc',
            }, {
                # Case invoice on purchase journal
                'file_name': 'test_import_invoice',
                'expected_message': "The RFC doesn't match with document's company",
                'type': 'purchase',
            }, {
                # Case bill on sale journal
                'file_name': 'test_import_bill',
                'expected_message': "The RFC doesn't match with document's company",
                'type': 'sale',
            },
        ]
        for subtest in subtests:
            file_name = subtest['file_name']
            with self.subTest(msg=file_name):
                file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content
                move = self._upload_document_on_journal(
                    journal=self.company_data['default_journal_' + subtest['type']],
                    content=file_content,
                    filename=f'{file_name}.xml',
                )

                self.assertRecordValues(move, [
                    {'l10n_mx_edi_cfdi_state': False, 'l10n_mx_edi_cfdi_attachment_id': False, 'review_state': 'anomaly'}
                ])
                self.assertRegex(move.message_ids[1].body, subtest['expected_message'])

    def test_import_invoice(self):
        file_name = "test_import_invoice"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        self.partner_mx.company_id = self.env.company

        # Read the problematic xml file that kept causing crash on bill uploads
        new_invoice = self._upload_document_on_journal(
            journal=self.company_data['default_journal_sale'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_invoice, [{
            'currency_id': self.comp_curr.id,
            'partner_id': self.partner_mx.id,
            'amount_tax': 80.0,
            'amount_untaxed': 500.0,
            'amount_total': 580.0,
            'invoice_date': fields.Date.from_string('2024-04-08'),
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_efectivo').id,
            'l10n_mx_edi_usage': 'G03',
            'l10n_mx_edi_cfdi_uuid': '8CA06290-4800-4F93-8B1B-25B208BB1AFF',
            'l10n_mx_edi_payment_policy': 'PUE',
        }])
        self.assertRecordValues(new_invoice.invoice_line_ids, [{
            'quantity': 1.0,
            'price_unit': 500.0,
            'discount': 0.0,
            'product_id': self.product.id,
            'tax_ids': self.tax_16.ids,
        }])

        # The state of the document should be "Sent".
        self.assertEqual(new_invoice.l10n_mx_edi_invoice_document_ids.state, 'invoice_sent')

        # The "Update SAT" button should appear continuously (after posting).
        new_invoice.action_post()
        self.assertRecordValues(new_invoice, [{
            'need_cancel_request': True,
            'l10n_mx_edi_update_sat_needed': True,
        }])

    def test_import_bill(self):
        # Invoice with payment policy = PUE, otherwise 'FormaPago' (payment method) is set to '99' ('Por Definir')
        # and the initial payment method cannot be backtracked at import
        file_name = "test_import_bill"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        # company's partner is not linked by default to its company.
        self.partner_mx.company_id = self.env.company

        # Read the problematic xml file that kept causing crash on bill uploads
        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_bill, [{
            'currency_id': self.comp_curr.id,
            'partner_id': self.partner_mx.id,
            'amount_tax': 80.0,
            'amount_untaxed': 500.0,
            'amount_total': 580.0,
            'invoice_date': fields.Date.from_string('2024-04-08'),
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_efectivo').id,
            'l10n_mx_edi_usage': 'G03',
            'l10n_mx_edi_cfdi_uuid': '8CA06290-4800-4F93-8B1B-25B208BB1AFF',
            'ref': '8CA06290-4800-4F93-8B1B-25B208BB1AFF',
            'l10n_mx_edi_payment_policy': 'PUE'
        }])
        self.assertRecordValues(new_bill.invoice_line_ids, [{
            'quantity': 1.0,
            'price_unit': 500.0,
            'discount': 0.0,
            'product_id': self.product.id,
            'product_uom_id': self.product.uom_id.id,
            'tax_ids': self.tax_16_purchase.ids,
        }])

        # The state of the document should be "Sent".
        self.assertEqual(new_bill.l10n_mx_edi_invoice_document_ids.state, 'invoice_received')

        # The "Update SAT" button should appear continuously (after posting).
        new_bill.action_post()
        self.assertTrue(new_bill.l10n_mx_edi_update_sat_needed)
        with self.with_mocked_sat_call(lambda _x: 'valid'):
            new_bill.l10n_mx_edi_cfdi_try_sat()
        self.assertTrue(new_bill.l10n_mx_edi_update_sat_needed)

        # Check the error about duplicated fiscal folio.
        new_bill_same_folio = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )
        new_bill_same_folio.action_post()
        self.assertRecordValues(new_bill_same_folio, [{'duplicated_ref_ids': new_bill.ids}])

    def test_add_cfdi_on_existing_bill_without_cfdi(self):
        file_name = 'test_add_cfdi_on_existing_bill'
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content
        attachment = self.env['ir.attachment'].create({
            'mimetype': 'application/xml',
            'name': f'{file_name}.xml',
            'raw': file_content,
        })
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_mx.id,
            'date': self.frozen_today.date(),
            'invoice_date': self.frozen_today.date(),
            'invoice_line_ids': [Command.create({'product_id': self.product.id})],
        })
        prev_invoice_line_ids = bill.invoice_line_ids
        # Bill was created without a cfdi invoice
        self.assertRecordValues(bill, [{
            'l10n_mx_edi_cfdi_attachment_id': None,
            'l10n_mx_edi_cfdi_uuid': None,
        }])
        # post message with the cfdi invoice attached
        bill.message_post(message_type='comment', attachment_ids=attachment.ids)
        # check that the uuid is now set and the cfdi attachment is linked but the invoice lines did not change
        self.assertRecordValues(bill, [{
            'l10n_mx_edi_cfdi_attachment_id': attachment.id,
            'l10n_mx_edi_cfdi_uuid': '42000000-0000-0000-0000-000000000001',
            'invoice_line_ids': prev_invoice_line_ids.ids,
        }])

    def test_add_cfdi_on_existing_receipt_without_cfdi(self):
        # Vendor receipts (the move type used by expenses) must expose the CFDI uploaded on them.
        file_name = 'test_add_cfdi_on_existing_bill'
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content
        attachment = self.env['ir.attachment'].create({
            'mimetype': 'application/xml',
            'name': f'{file_name}.xml',
            'raw': file_content,
        })
        receipt = self.env['account.move'].create({
            'move_type': 'in_receipt',
            'partner_id': self.partner_mx.id,
            'date': self.frozen_today.date(),
            'invoice_date': self.frozen_today.date(),
            'invoice_line_ids': [Command.create({'product_id': self.product.id})],
        })
        # Receipt was created without a cfdi invoice
        self.assertRecordValues(receipt, [{
            'l10n_mx_edi_cfdi_attachment_id': None,
            'l10n_mx_edi_cfdi_uuid': None,
        }])
        # drop the cfdi invoice in the attachment box: no message is posted, '_post_add_create' triggers the import
        attachment.write({'res_model': 'account.move', 'res_id': receipt.id})
        attachment._post_add_create()
        # check that the uuid is now set and the cfdi attachment is linked but the invoice lines did not change
        self.assertRecordValues(receipt, [{
            'move_type': 'in_receipt',
            'l10n_mx_edi_cfdi_attachment_id': attachment.id,
            'l10n_mx_edi_cfdi_state': 'received',
            'l10n_mx_edi_cfdi_uuid': '42000000-0000-0000-0000-000000000001',
        }])
        self.assertRecordValues(receipt.l10n_mx_edi_document_ids, [{
            'state': 'invoice_received',
            'attachment_id': attachment.id,
        }])

        # The "Update SAT" button should appear continuously (after posting), the vendor can cancel the CFDI anytime.
        receipt.action_post()
        self.assertTrue(receipt.l10n_mx_edi_update_sat_needed)
        with self.with_mocked_sat_call(lambda _x: 'valid'):
            receipt.l10n_mx_edi_cfdi_try_sat()
        self.assertRecordValues(receipt, [{'l10n_mx_edi_cfdi_sat_state': 'valid'}])

        # The CFDI is only imported, not sent by us: the user is allowed to drop it.
        attachment.unlink()

    def test_add_cfdi_on_existing_bill_with_cfdi(self):
        # Check that uploading a CFDI on a bill with an existing CFDI doesn't change the fiscal
        # folio or CFDI document
        file_name = "test_import_bill"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content
        self.env.company.partner_id.company_id = self.env.company
        bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        file_name = 'test_add_cfdi_on_existing_bill'
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content
        attachment = self.env['ir.attachment'].create({
            'mimetype': 'application/xml',
            'name': f'{file_name}.xml',
            'raw': file_content,
        })

        initial_uuid = bill.l10n_mx_edi_cfdi_uuid
        initial_attachment_id = bill.l10n_mx_edi_document_ids.attachment_id.id
        # post message with a different cfdi invoice attached
        bill.message_post(attachment_ids=attachment.ids)
        # check that the uuid and attachment have not changed to those of the attachment
        self.assertRecordValues(bill, [{
            'l10n_mx_edi_cfdi_uuid': initial_uuid,
            'l10n_mx_edi_cfdi_attachment_id': initial_attachment_id,
        }])

    def test_import_bill_with_extento(self):
        file_name = "test_import_bill_with_extento"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        # Read the problematic xml file that kept causing crash on bill uploads
        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_bill.invoice_line_ids, (
            {
                'quantity': 1,
                'price_unit': 54017.48,
                'tax_ids': self.tax_16_purchase.ids,
            },
            {
                'quantity': 1,
                'price_unit': 17893.00,
                'tax_ids': self.tax_0_exento_purchase.ids,
            }
        ))

    def test_import_bill_without_tax(self):
        file_name = "test_import_bill_without_tax"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        # Read the problematic xml file that kept causing crash on bill uploads
        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_bill.invoice_line_ids, (
            {
                'quantity': 1,
                'price_unit': 54017.48,
                'tax_ids': self.tax_16_purchase.ids,
            },
            {
                'quantity': 1,
                'price_unit': 17893.00,
                # This should be empty due to the error causing missing attribute 'TasaOCuota' to result in empty tax_ids
                'tax_ids': [],
            }
        ))

    def test_import_bill_mismatch_amount_tax(self):
        file_name = "test_import_bill_with_withholding"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        self.tax_4_purchase_withholding.unlink()
        bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )
        self.assertRecordValues(bill.invoice_line_ids, [{'tax_ids': self.tax_16_purchase.ids}])
        self.assertRecordValues(bill, [{'review_state': 'anomaly', 'l10n_mx_edi_show_import_totals_alert': True}])

    def test_import_bill_custom_tax_object(self):
        file_name = "test_import_bill_custom_tax_object"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        # Read the problematic xml file that kept causing crash on bill uploads
        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_bill.invoice_line_ids, (
            {
                'quantity': 1,
                'price_unit': 1000.0,
                'discount': 100.0,
                'tax_ids': [],
                'l10n_mx_edi_tax_object': '04',
            },
            {
                'quantity': 1,
                'price_unit': 1000.0,
                'discount': 0.0,
                'tax_ids': self.tax_16_purchase.ids,
                'l10n_mx_edi_tax_object': '02',
            },
        ))

    def test_import_bill_with_withholding(self):
        file_name = "test_import_bill_with_withholding"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        # Read the problematic xml file that kept causing crash on bill uploads
        new_invoice = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_invoice.line_ids.sorted(), (
            {
                'balance': 147.0,
                'tax_ids': (self.tax_16_purchase + self.tax_4_purchase_withholding).ids,
                'display_type': 'product',
                'tax_line_id': False,
            },
            {
                'balance': -5.88,
                'tax_ids': [],
                'display_type': 'tax',
                'tax_line_id': self.tax_4_purchase_withholding.id,
            },
            {
                'balance': 23.52,
                'tax_ids': [],
                'display_type': 'tax',
                'tax_line_id': self.tax_16_purchase.id,
            },
            {
                'balance': -164.64,
                'tax_ids': [],
                'display_type': 'payment_term',
                'tax_line_id': False,
            },
        ))

    def test_import_bill_with_local_taxes(self):
        file_name = "test_import_bill_with_local_taxes"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        local_tax = self.env['account.chart.template'].ref('l10n_mx_edi_tax_local_purchase')
        self.assertRecordValues(bill.line_ids.filtered(lambda line: line.tax_line_id == local_tax), [
            {'name': 'Local VAT (8.00)', 'balance': -160.00, 'display_type': 'tax'},
            {'name': 'Local VAT (3.50)', 'balance': -105.00, 'display_type': 'tax'},
            {'name': 'Local VAT (16.00)', 'balance': 160.00, 'display_type': 'tax'},
            {'name': 'Local VAT (5.00)', 'balance': 10.00, 'display_type': 'tax'},
        ])
        self.assertEqual(bill.amount_untaxed, 15000.00)

        # Resyncing the move must update the local tax lines, not drop and recreate them.
        local_tax_lines = bill.line_ids.filtered(lambda line: line.tax_line_id == local_tax)
        bill.invoice_line_ids[0].quantity = 2
        self.assertRecordValues(bill.line_ids.filtered(lambda line: line.tax_line_id == local_tax), [
            {'id': line.id, 'balance': line.balance} for line in local_tax_lines
        ])

    def test_import_bill_hidden_taxes(self):
        """Test that tax line amount and payment term line matches with total tax and cfdi total when hidden taxes"""
        file_name = "test_import_bill_hidden_taxes"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        # Bill with subtotal 17301.09 and 2700.21 in taxes (16%).
        # 17301.09 * .16 = 2768.16 ≠ 2700.121 due to hidden taxes
        # Tax line amount should be fixed to match tax amount from CFDI bill
        lines = bill.line_ids.filtered(lambda l: l.tax_line_id or l.display_type == 'payment_term')
        self.assertRecordValues(lines, [
            # Tax line
            {'balance': 2700.21, 'tax_ids': [], 'display_type': 'tax', 'tax_line_id': self.tax_16_purchase.id},
            # Term line
            {'balance': -20001.30, 'tax_ids': [], 'display_type': 'payment_term', 'tax_line_id': False},
        ])
        self.assertEqual(bill.amount_untaxed, 17301.09)

    def test_import_bill_vendor_product(self):
        file_name = "test_import_bill_vendor_product"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        self.product.write({
            'default_code': False,
            'variant_seller_ids': [Command.create({
                'partner_id': self.partner_mx.id,
                'product_code': 'product_mx',
            })]
        })
        product_mx_2 = self._create_product_mx(
            name='product_mx_2',
            default_code=False,
            variant_seller_ids=[Command.create({
                'partner_id': self.partner_mx.id,
                'product_name': 'vendor_product_mx_2',
            })]
        )
        self._create_product_mx(
            name='product_mx_3',
            default_code=False,
            variant_seller_ids=[
                Command.create({
                    'partner_id': self.partner.id,
                    'product_code': 'product_mx',
                }),
                Command.create({
                    'partner_id': self.partner_mx.id,
                    'product_code': 'not product_mx',
                }),
            ],
        )

        bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(bill.invoice_line_ids, [
            # Case product exists with vendor code
            {'product_id': self.product.id, 'name': '[product_mx] product_mx | product_mx', 'quantity': 1, 'price_unit': 500.00, 'price_subtotal': 500.00, 'price_total': 580.00},
            # Case product exists with vendor product name
            {'product_id': product_mx_2.id, 'name': 'vendor_product_mx_2', 'quantity': 1, 'price_unit': 500.00, 'price_subtotal': 500.00, 'price_total': 580.00},
            # Case product might exist but partner is not the vendor of the product or is the vendor but different vendor code
            {'product_id': False, 'name': 'vendor_product_mx_3 | vendor_product_mx_3', 'quantity': 1, 'price_unit': 500.00, 'price_subtotal': 500.00, 'price_total': 580.00},
        ])

    def test_import_cfdi_update_zip(self):
        """Test when importing a CFDI the zip code should be updated only when it doesn't have it."""
        subtests = [
            # Case when partner doesn't have zip code
            {
                'xml_file': 'test_import_invoice',
                'expected_zip': '26670',
                'journal_type': 'sale',
                'current_zip': False,
            },
            {
                'xml_file': 'test_import_bill',
                'expected_zip': '20914',
                'journal_type': 'purchase',
                'current_zip': False
            },
            # Case when partner has zip code
            {
                'xml_file': 'test_import_invoice',
                'expected_zip': '11320',
                'journal_type': 'sale',
                'current_zip': '11320'
            },
            {
                'xml_file': 'test_import_bill',
                'expected_zip': '11320',
                'journal_type': 'purchase',
                'current_zip': '11320'
            },
        ]
        for subtest in subtests:
            with self.subTest(subtest=subtest):
                self.partner_mx.zip = subtest['current_zip']
                file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{subtest["xml_file"]}.xml').content
                invoice = self._upload_document_on_journal(
                    journal=self.company_data[f'default_journal_{subtest["journal_type"]}'],
                    content=file_content,
                    filename=subtest['xml_file'],
                )
                self.assertEqual(invoice.partner_id.zip, subtest['expected_zip'])

    def test_import_invoice_cfdi_unknown_partner(self):
        '''Test the import of invoices with unknown partners:
            * The partner should be created correctly
            * On the created move the "CFDI to Public" field (l10n_mx_edi_cfdi_to_public) should be set correctly.
        '''
        mx = self.env.ref('base.mx')
        subtests = [
            {
                'xml_file': 'test_import_invoice_cfdi_unknown_partner_1',
                'expected_invoice_vals': {
                    'l10n_mx_edi_cfdi_to_public': False,
                },
                'expected_partner_vals': {
                    'name': "INMOBILIARIA CVA",
                    'vat': 'ICV060329BY0',
                    'country_id': mx.id,
                    'property_account_position_id': False,
                    'zip': '26670',
                },
            },
            {
                'xml_file': 'test_import_invoice_cfdi_unknown_partner_2',
                'expected_invoice_vals': {
                    'l10n_mx_edi_cfdi_to_public': True,
                },
                'expected_partner_vals': {
                    'name': "PARTNER_US",
                    'vat': False,
                    'country_id': False,
                    'property_account_position_id': self.env['account.chart.template'].ref('account_fiscal_position_foreign').id,
                    'zip': False,
                },
            },
            {
                'xml_file': 'test_import_invoice_cfdi_unknown_partner_3',
                'expected_invoice_vals': {
                    'l10n_mx_edi_cfdi_to_public': True,
                },
                'expected_partner_vals': {
                    'name': "INMOBILIARIA CVA",
                    'vat': False,
                    'country_id': mx.id,
                    'property_account_position_id': False,
                    'zip': False,
                },
            },
        ]
        for subtest in subtests:
            xml_file = subtest['xml_file']

            with self.subTest(msg=xml_file), self.mocked_import_retrieve_customer():
                file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{xml_file}.xml').content
                invoice = self._upload_document_on_journal(
                    journal=self.company_data['default_journal_sale'],
                    content=file_content,
                    filename=f'{xml_file}.xml',
                )

                self.assertRecordValues(invoice, [subtest['expected_invoice_vals']])

                # field 'property_account_position_id' is company dependant
                partner = invoice.partner_id.with_company(company=invoice.company_id)
                self.assertRecordValues(partner, [subtest['expected_partner_vals']])

    def test_upload_xml_to_generate_invoice_with_exento_tax(self):
        self.env['account.tax'].search([('name', '=', 'Exento')]).unlink()
        self.env['account.tax.group'].search([('name', '=', 'Exento')]).unlink()

        file_name = "test_import_bill_with_extento"
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content

        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        self.assertRecordValues(new_bill.invoice_line_ids, (
            {
                'quantity': 1,
                'price_unit': 54017.48,
            },
            {
                'quantity': 1,
                'price_unit': 17893.00,
            }
        ))

    def test_cfdi_rounding_1(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 398.28,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 108.62,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 362.07,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                ] + [
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 31.9,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ] * 12,
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_1_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_1_pay')

    def test_cfdi_rounding_2(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'quantity': quantity,
                        'price_unit': price_unit,
                        'discount': discount,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for quantity, price_unit, discount in (
                        (30, 84.88, 13.00),
                        (30, 18.00, 13.00),
                        (3, 564.32, 13.00),
                        (33, 7.00, 13.00),
                        (20, 49.88, 13.00),
                        (100, 3.10, 13.00),
                        (2, 300.00, 13.00),
                        (36, 36.43, 13.00),
                        (36, 15.00, 13.00),
                        (2, 61.08, 0),
                        (2, 13.05, 0),
                    )
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_2_inv')

            payment = self._register_payment(invoice, currency_id=self.comp_curr.id)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_2_pay')

    def test_cfdi_rounding_3(self):
        today = self.frozen_today
        today_minus_1 = self.frozen_today - relativedelta(days=1)
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(today_minus_1, days=1), 1 / 17.187), (fields.Date.subtract(today, days=1), 1 / 17.0357)])

        with self.mx_external_setup(today_minus_1):
            invoice = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 7.34,
                        'quantity': 200,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_3_inv')

        with self.mx_external_setup(today):
            payment = self._register_payment(
                invoice,
                payment_date=today,
                currency_id=usd.id,
            )
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_3_pay')

    def test_cfdi_rounding_4(self):
        today = self.frozen_today
        today_minus_1 = self.frozen_today - relativedelta(days=1)
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(today_minus_1, days=1), 1 / 16.9912), (fields.Date.subtract(today, days=1), 1 / 17.068)])

        with self.mx_external_setup(today_minus_1):
            invoice1 = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 68.0,
                        'quantity': 68.25,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice1._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice1, 'test_cfdi_rounding_4_inv_1')

        with self.mx_external_setup(today):
            invoice2 = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 68.0,
                        'quantity': 24.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice2._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice2, 'test_cfdi_rounding_4_inv_2')

            invoices = invoice1 + invoice2
            with self.mx_external_setup(today):
                payment = self._register_payment(
                    invoices,
                    amount=7276.68,
                    currency_id=usd.id,
                    payment_date=today,
                )
                with self.with_mocked_pac_sign_success():
                    payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
                self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_4_pay')

    def test_cfdi_rounding_5(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                    })
                    for quantity, price_unit in (
                        (412.0, 43.65),
                        (412.0, 43.65),
                        (90.0, 50.04),
                        (500.0, 11.77),
                        (500.0, 34.93),
                        (90.0, 50.04),
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_5_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_5_pay')

    def test_cfdi_rounding_6(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                        'discount': 30.0,
                    })
                    for quantity, price_unit in (
                        (7.0, 724.14),
                        (4.0, 491.38),
                        (2.0, 318.97),
                        (7.0, 224.14),
                        (6.0, 206.90),
                        (6.0, 129.31),
                        (6.0, 189.66),
                        (16.0, 775.86),
                        (2.0, 7724.14),
                        (2.0, 1172.41),
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_6_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_6_pay')

    def test_cfdi_rounding_7(self):
        with self.mx_external_setup(self.frozen_today):
            self.partner_mx.l10n_mx_edi_ieps_breakdown = True
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                        'tax_ids': [Command.set(taxes.ids)],
                    })
                    for quantity, price_unit, taxes in (
                        (12.0, 457.92, self.tax_26_5_ieps + self.tax_16),
                        (12.0, 278.04, self.tax_26_5_ieps + self.tax_16),
                        (12.0, 539.76, self.tax_26_5_ieps + self.tax_16),
                        (36.0, 900.0, self.tax_16),
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_7_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_7_pay')

    def test_cfdi_rounding_8(self):
        with self.mx_external_setup(self.frozen_today):
            self.partner_mx.l10n_mx_edi_ieps_breakdown = True
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                        'tax_ids': [Command.set(taxes.ids)],
                    })
                    for quantity, price_unit, taxes in (
                        (1.0, 244.0, self.tax_0_ieps + self.tax_0),
                        (8.0, 244.0, self.tax_0_ieps + self.tax_0),
                        (1.0, 2531.0, self.tax_0),
                        (1.0, 2820.75, self.tax_6_ieps + self.tax_0),
                        (1.0, 2531.0, self.tax_0),
                        (8.0, 468.0, self.tax_0_ieps + self.tax_0),
                        (1.0, 2820.75, self.tax_6_ieps + self.tax_0),
                        (1.0, 210.28, self.tax_7_ieps),
                        (1.0, 2820.75, self.tax_6_ieps + self.tax_0),
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_8_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_8_pay')

    def test_cfdi_rounding_9(self):
        usd_exchange_rates = (
            1 / 17.1325,
            1 / 17.1932,
            1 / 17.0398,
            1 / 17.1023,
            1 / 17.1105,
            1 / 16.7457,
        )

        def quick_create_invoice(rate, quantity_and_price_unit):
            # Only one rate is allowed per day and to make the test working in external_mode, we need to create 6 rates in less than
            # 3 days. So let's create/unlink the rate.
            usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(self.frozen_today, days=1), rate)])
            invoice = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for quantity, price_unit in quantity_and_price_unit
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            return invoice

        with self.mx_external_setup(self.frozen_today):
            invoice1 = quick_create_invoice(
                usd_exchange_rates[0],
                [(80.0, 21.9)],
            )
            invoice2 = quick_create_invoice(
                usd_exchange_rates[1],
                [(200.0, 13.36)],
            )
            invoice3 = quick_create_invoice(
                usd_exchange_rates[1],
                [(1200.0, 0.36), (1000.0, 0.44), (800.0, 0.44), (800.0, 0.23)],
            )
            invoice4 = quick_create_invoice(
                usd_exchange_rates[2],
                [(200.0, 21.9)],
            )
            invoice5 = quick_create_invoice(
                usd_exchange_rates[3],
                [(1000.0, 0.36), (500.0, 0.44), (500.0, 0.23), (400.0, 0.87), (200.0, 0.44)],
            )
            invoice6 = quick_create_invoice(
                usd_exchange_rates[4],
                [(200.0, 14.4)],
            )

            self.setup_other_currency('USD', rates=[(fields.Date.subtract(self.frozen_today, days=1), usd_exchange_rates[5])])
            payment = self._register_payment(
                invoice1 + invoice2 + invoice3 + invoice4 + invoice5 + invoice6,
                currency_id=self.env.company.currency_id.id,
            )
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_9_pay')

    def test_cfdi_rounding_10(self):
        def create_invoice(**kwargs):
            return self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(taxes.ids)],
                    })
                    for price_unit, taxes in (
                        (550.0, self.tax_0),
                        (505.0, self.tax_16),
                        (495.0, self.tax_16),
                        (560.0, self.tax_0),
                        (475.0, self.tax_16),
                    )
                ],
                **kwargs,
            )

        self.tax_16.price_include_override = 'tax_included'
        with self.mx_external_setup(self.frozen_today):
            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_10_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_10_pay')

            invoice = create_invoice(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_cfdi_rounding_10_ginvoice')

    def test_cfdi_rounding_11(self):
        self.tax_16.price_include_override = 'tax_included'
        with self.mx_external_setup(self.frozen_today):
            invoices = self.env['account.move']
            for price_unit in (2803.0, 1842.0, 2798.0, 3225.0, 3371.0):
                invoices += self._create_invoice_mx(
                    l10n_mx_edi_cfdi_to_public=True,
                    invoice_line_ids=[
                         Command.create({
                             'product_id': self.product.id,
                             'price_unit': price_unit,
                             'tax_ids': [Command.set(self.tax_16.ids)],
                         }),
                    ],
                )
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoices)
            self._assert_global_invoice_cfdi_from_invoices(invoices, 'test_cfdi_rounding_11_ginvoice')

    def test_cfdi_rounding_12(self):
        def create_invoice(**kwargs):
            return self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(taxes.ids)],
                    })
                    for price_unit, taxes in (
                        (7.54, self.tax_8_ieps),
                        (7.41, self.tax_8_ieps),
                        (5.27, self.tax_16),
                        (5.21, self.tax_16),
                    )
                ],
                **kwargs,
            )

        with self.mx_external_setup(self.frozen_today):
            self.partner_mx.l10n_mx_edi_ieps_breakdown = True
            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_12_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_12_pay')

            invoice = create_invoice(l10n_mx_edi_cfdi_to_public=True)
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoice)
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_cfdi_rounding_12_ginvoice')

    def test_cfdi_rounding_13(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                     Command.create({
                         'product_id': self.product.id,
                         'price_unit': 4000.0,
                         'tax_ids': [Command.set((self.tax_16 + self.local_tax_3_5_withholding).ids)],
                     }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_13_inv')

    def test_cfdi_rounding_14(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                     Command.create({
                         'product_id': self.product.id,
                         'price_unit': 100.05,
                         'discount': 50.0,
                         'tax_ids': [Command.set(self.tax_16.ids)],
                     }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_14_inv')

    def test_cfdi_rounding_15(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                     Command.create({
                         'product_id': self.product.id,
                         'price_unit': 18103.45,
                         'discount': 50.0,
                         'tax_ids': [Command.set(self.tax_16.ids)],
                     }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_15_inv')

    def test_cfdi_rounding_16(self):
        (self.tax_8_ieps + self.tax_26_5_ieps + self.tax_30_ieps + self.tax_53_ieps + self.tax_16).write({
            'active': True,
            'price_include_override': 'tax_included',
            'include_base_amount': True,
        })
        product1 = self._create_product_mx(
            lst_price=489.57,
            taxes_id=[Command.set((self.tax_26_5_ieps + self.tax_16).ids)],
        )
        product2 = self._create_product_mx(
            lst_price=789.57,
            taxes_id=[Command.set((self.tax_30_ieps + self.tax_16).ids)],
        )
        product3 = self._create_product_mx(
            lst_price=7989.57,
            taxes_id=[Command.set((self.tax_53_ieps + self.tax_16).ids)],
        )
        product4 = self._create_product_mx(
            lst_price=289.57,
            taxes_id=[Command.set((self.tax_8_ieps + self.tax_16).ids)],
        )
        product5 = self._create_product_mx(
            lst_price=378.0,
            taxes_id=[Command.set(self.tax_0.ids)],
        )
        product6 = self._create_product_mx(
            lst_price=1000.0,
            taxes_id=[Command.set(self.tax_16.ids)],
        )
        with self.mx_external_setup(self.frozen_today):
            invoices = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                invoice_line_ids=[
                    Command.create({
                        'product_id': product.id,
                        'quantity': quantity,
                    })
                    for product, quantity in (
                        (product1, 3),
                        (product2, 4),
                        (product3, 3),
                        (product4, 2),
                        (product5, 1),
                        (product6, 3),
                    )
                ],
            )
            invoices += self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                invoice_line_ids=[
                    Command.create({
                        'product_id': product.id,
                        'quantity': quantity,
                    })
                    for product, quantity in (
                        (product1, 3),
                        (product2, 4),
                        (product3, 2),
                        (product4, 2),
                        (product5, 1),
                        (product6, 3),
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                self._create_invoices_global_invoice(invoices)
            self._assert_global_invoice_cfdi_from_invoices(invoices, 'test_cfdi_rounding_16_ginvoice')

    def test_cfdi_rounding_17(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3163.79,
                        'discount': 25.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 2992.41,
                        'discount': 25.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3025.86,
                        'discount': 25.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_17_inv')

    def test_cfdi_rounding_18(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'l10n_mx_edi_tax_object': '03',
                        'product_id': self.product.id,
                        'price_unit': 50.00,
                        'tax_ids': [Command.set(self.tax_1_25_sale_withholding.ids)],
                    }),
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_18_inv')

    def test_cfdi_rounding_19(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'l10n_mx_edi_tax_object': '03',
                        'product_id': self.product.id,
                        'price_unit': 7.00,
                        'tax_ids': [Command.set(self.tax_1_25_sale_withholding.ids)],
                    }),
                    Command.create({
                        'l10n_mx_edi_tax_object': '03',
                        'product_id': self.product.id,
                        'price_unit': 43.00,
                        'tax_ids': [Command.set(self.tax_1_25_sale_withholding.ids)],
                    }),
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_19_inv')

    def test_cfdi_rounding_20(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'l10n_mx_edi_tax_object': '03',
                        'product_id': self.product.id,
                        'price_unit': 17.00,
                        'tax_ids': [Command.set(self.tax_1_25_sale_withholding.ids)],
                    }),
                    Command.create({
                        'l10n_mx_edi_tax_object': '03',
                        'product_id': self.product.id,
                        'price_unit': 33.00,
                        'tax_ids': [Command.set(self.tax_1_25_sale_withholding.ids)],
                    }),
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_20_inv')

    def test_cfdi_rounding_21(self):
        rate = 1 / 20.4277
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(self.frozen_today, days=1), rate)])
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 93.76,
                        'quantity': 172,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 74.18,
                        'quantity': 161,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 74.18,
                        'quantity': 162,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 93.76,
                        'quantity': 384,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 111.28,
                        'quantity': 178,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ])

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_21_inv')

            payment = self._register_payment(invoice, currency_id=usd.id)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_21_pay')

    def test_cfdi_rounding_22(self):
        today = self.frozen_today
        today_minus_1 = self.frozen_today - relativedelta(days=1)
        usd = self.setup_other_currency('USD', rates=[
            (fields.Date.subtract(today_minus_1, days=1), 0.049216958195),
            (fields.Date.subtract(today, days=1), 0.053418803419),
        ])
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                currency_id=usd.id,
                date=today_minus_1,
                invoice_date=today_minus_1,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 91,
                        'quantity': 64,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_22_inv')

            payment = self._register_payment(invoice, payment_date=today)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_22_pay')

    def test_cfdi_rounding_23(self):
        self.tax_16.price_include_override = 'tax_included'

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                        'discount': discount,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for quantity, price_unit, discount in (
                        (1.0, 454.0, 10.0),
                        (2.5, 452.01, 10.0),
                        (1.0, 209.99, 10.0),
                        (9.40, 27.25, 10.0),
                        (0.5, 1356.01, 10.0),
                        (20.0, 1.0, 0.0),
                    )
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_23_inv')

    def test_cfdi_rounding_24(self):
        self.tax_16.price_include_override = 'tax_excluded'

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_cfdi_to_public=True,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 47.25,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                        'discount': 50,
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_cfdi_rounding_24_ginvoice')

    def test_cfdi_rounding_25(self):
        self.env['decimal.precision'].search([('name', '=', 'Product Price')]).digits = 6
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 100.032,
                        'discount': 50.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_25_inv')

    def test_cfdi_rounding_26(self):
        self.tax_16.price_include_override = 'tax_included'

        def create_invoice():
            return self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'quantity': quantity,
                        'discount': discount,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for price_unit, quantity, discount in (
                        (64.99,     6.60,   10.0),
                        (220.01,    1.0,    10.0),
                        (1.0,       12.0,   0.0),
                        (151.99,    1.0,    10.0),
                    )
                ])

        with self.mx_external_setup(self.frozen_today):
            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_26_inv')

            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_cfdi_rounding_26_ginvoice')

    def test_cfdi_rounding_27(self):
        self.tax_16.price_include_override = 'tax_included'

        def create_invoice():
            return self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for price_unit in (
                        1999.0, 1999.0, 1999.0,
                        1799.0, 1799.0,
                        649.0, 649.0, 649.0, 649.0, 649.0,
                    )
                ])

        with self.mx_external_setup(self.frozen_today):
            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_27_inv')

            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_cfdi_rounding_27_ginvoice')

    def test_cfdi_rounding_28(self):
        self.tax_16.price_include_override = 'tax_included'

        def create_invoice():
            return self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for price_unit in (99.0, 99.0, 99.0, 399.0)
                ])

        with self.mx_external_setup(self.frozen_today):
            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_28_inv')

            invoice = create_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_global_invoice_try_send(fields.Date.to_date('2025-01-01'))
            self._assert_global_invoice_cfdi_from_invoices(invoice, 'test_cfdi_rounding_28_ginvoice')

    def test_cfdi_rounding_29(self):
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(self.frozen_today, days=1), 0.058748193493)])
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 4500,
                        'quantity': 1,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_29_inv')

            payment = self._register_payment(invoice, amount=30000, currency_id=self.comp_curr.id)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_29_pay')

    def test_cfdi_rounding_30(self):
        today = self.frozen_today
        usd = self.setup_other_currency('USD', rates=[
            (today, 1 / 17.4455),
        ])
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 3.488,
                        'quantity': 1,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ])
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_30_inv')

            payment = self._register_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_cfdi_rounding_30_pay')

    def test_cfdi_rounding_negative_line_on_many_others(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': price_unit,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })
                    for price_unit in (
                        723.77,
                        769.35,
                        1510.56,
                        1378.08,
                        851.40,
                        662.69,
                        1378.08,
                        1378.08,
                        77.80,
                        743.04,
                        503.28,
                        421.06,
                        743.04,
                        743.04,
                        63.47,
                        80.62,
                        80.62,
                        80.62,
                        80.62,
                        119.29,
                        11.27,
                        34.02,
                        16.60,
                        19.20,
                        19.20,
                        13.54,
                        15.79,
                        15.79,
                        5.37,
                        5.37,
                        0.01,
                        3.23,
                        32.01,
                        5.20,
                        68.54,
                        97.55,
                        121.36,
                        18.67,
                        32.51,
                        68.14,
                        15.33,
                        26.20,
                        46.89,
                        8.06,
                        8.06,
                        4.84,
                        8.06,
                        13.36,
                        -0.99,
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_rounding_negative_line_on_many_others')

    def test_cfdi_cash_rounding(self):
        """Cash rounding lines (add_invoice_line strategy) must not appear as CFDI
        concepts. The CFDI SubTotal/Total must reflect the pre-rounding amounts;
        the rounding difference only belongs in the journal entry."""
        cash_rounding = self.env['account.cash.rounding'].create({
            'name': 'Redondeo',
            'rounding': 1.0,
            'strategy': 'add_invoice_line',
            'profit_account_id': self.company_data['default_account_revenue'].copy().id,
            'loss_account_id': self.company_data['default_account_expense'].copy().id,
            'rounding_method': 'UP',
        })
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_cash_rounding_id=cash_rounding.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 86.034483,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    }),
                ],
            )
            rounding_lines = invoice.line_ids.filtered(lambda l: l.display_type == 'rounding')
            self.assertTrue(rounding_lines, "Expected a cash rounding line on the invoice")
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self._assert_invoice_cfdi(invoice, 'test_cfdi_cash_rounding')

    def test_partial_payment_1(self):
        date1 = self.frozen_today - relativedelta(days=2)
        date2 = self.frozen_today - relativedelta(days=1)
        date3 = self.frozen_today
        chf = self.setup_other_currency('CHF', rates=[(fields.Date.subtract(date1, days=1), 16.0), (fields.Date.subtract(date2, days=1), 17.0), (fields.Date.subtract(date3, days=1), 18.0)])

        with self.mx_external_setup(date1):
            invoice = self._create_invoice_mx()  # 1160 MXN
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            # Pay 10% in MXN.
            payment1 = self._register_payment(
                invoice,
                amount=116.0,
                currency_id=self.comp_curr.id,
                payment_date=date1,
            )
            with self.with_mocked_pac_sign_success():
                payment1.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment1.move_id, 'test_partial_payment_1_pay1')

            # Pay 10% in CHF (rate 1:16)
            payment2 = self._register_payment(
                invoice,
                amount=1856.0,
                currency_id=chf.id,
                payment_date=date1,
            )
            with self.with_mocked_pac_sign_success():
                payment2.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment2.move_id, 'test_partial_payment_1_pay2')

        with self.mx_external_setup(date2):
            # Pay 10% in CHF (rate 1:17).
            payment3 = self._register_payment(
                invoice,
                amount=1972.0,
                currency_id=chf.id,
                payment_date=date2,
            )
            with self.with_mocked_pac_sign_success():
                payment3.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment3.move_id, 'test_partial_payment_1_pay3')

        with self.mx_external_setup(date3):
            # Pay 10% in CHF (rate 1:18).
            payment4 = self._register_payment(
                invoice,
                amount=2088.0,
                currency_id=chf.id,
                payment_date=date3,
            )
            with self.with_mocked_pac_sign_success():
                payment4.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment4.move_id, 'test_partial_payment_1_pay4')

    def test_partial_payment_2(self):
        date1 = self.frozen_today - relativedelta(days=2)
        date2 = self.frozen_today - relativedelta(days=1)
        date3 = self.frozen_today
        chf = self.setup_other_currency('CHF', rates=[(fields.Date.subtract(date1, days=1), 16.0), (fields.Date.subtract(date2, days=1), 17.0), (fields.Date.subtract(date3, days=1), 18.0)])
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(date1, days=1), 17.0), (fields.Date.subtract(date2, days=1), 16.5), (fields.Date.subtract(date3, days=1), 16.0)])

        with self.mx_external_setup(date1):
            invoice = self._create_invoice_mx(
                currency_id=chf.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 16000.0,
                    }),
                ],
            )  # 18560 CHF = 1160 MXN
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        with self.mx_external_setup(date2):
            # Pay 10% in MXN (116 MXN = 1972 CHF).
            payment1 = self._register_payment(
                invoice,
                amount=116.0,
                currency_id=self.comp_curr.id,
                payment_date=date2,
            )
            with self.with_mocked_pac_sign_success():
                payment1.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment1.move_id, 'test_partial_payment_2_pay1')

            # Pay 10% in USD (rate 1:16.5)
            payment2 = self._register_payment(
                invoice,
                amount=1914.0,
                currency_id=usd.id,
                payment_date=date2,
            )
            with self.with_mocked_pac_sign_success():
                payment2.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment2.move_id, 'test_partial_payment_2_pay2')

        with self.mx_external_setup(date3):
            # Pay 10% in MXN (116 MXN = 2088 CHF).
            payment3 = self._register_payment(
                invoice,
                amount=116.0,
                currency_id=self.comp_curr.id,
                payment_date=date3,
            )
            with self.with_mocked_pac_sign_success():
                payment3.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment3.move_id, 'test_partial_payment_2_pay3')

            # Pay 10% in USD (rate 1:16)
            payment4 = self._register_payment(
                invoice,
                amount=1856.0,
                currency_id=usd.id,
                payment_date=date3,
            )
            with self.with_mocked_pac_sign_success():
                payment4.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment4.move_id, 'test_partial_payment_2_pay4')

    def test_partial_payment_3(self):
        """ Test a reconciliation chain with reconciliation with credit note in between. """
        date1 = self.frozen_today - relativedelta(days=2)
        date2 = self.frozen_today - relativedelta(days=1)
        date3 = self.frozen_today
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(date1, days=1), 17.0), (fields.Date.subtract(date2, days=1), 16.5), (fields.Date.subtract(date3, days=1), 17.5)])

        with self.mx_external_setup(date1):
            # MXN invoice at rate 19720 USD = 1160 MXN (1:17)
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        with self.mx_external_setup(date2):
            # Pay 1914 USD = 116 MXN (1:16.5)
            payment1 = self._register_payment(
                invoice,
                amount=1914.0,
                currency_id=usd.id,
                payment_date=date2,
            )
            with self.with_mocked_pac_sign_success():
                payment1.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment1.move_id, 'test_partial_payment_3_pay1')
            self.assertRecordValues(invoice, [{'amount_residual': 1044.0}])

            # USD Credit note at rate 1914 USD = 116 MXN (1:16.5)
            refund = self._create_invoice_mx(
                move_type='out_refund',
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1650.0,
                    }),
                ],
            )
            (refund + invoice).line_ids.filtered(lambda line: line.display_type == 'payment_term').reconcile()
            self.assertRecordValues(invoice + refund, [
                # The refund reconciled 116 MXN:
                # - 112.59 MXN with the invoice.
                # - 3.41 MXN as an exchange difference (1972 - 1914) / 17 ~= 3.41)
                {'amount_residual': 931.41},
                {'amount_residual': 0.0},
            ])

            # Pay 1914 USD = 116 MXN (1:16.5)
            # The credit note should be subtracted from the residual chain.
            payment2 = self._register_payment(
                invoice,
                amount=1914.0,
                currency_id=usd.id,
                payment_date=date2,
            )
            with self.with_mocked_pac_sign_success():
                payment2.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment2.move_id, 'test_partial_payment_3_pay2')
            self.assertRecordValues(invoice, [{'amount_residual': 815.41}])

        with self.mx_external_setup(date3):
            # Pay 10% in USD at rate 1:17.5
            payment3 = self._register_payment(
                invoice,
                amount=2030.0,
                currency_id=usd.id,
                payment_date=date3,
            )
            with self.with_mocked_pac_sign_success():
                payment3.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment3.move_id, 'test_partial_payment_3_pay3')
            self.assertRecordValues(invoice, [{'amount_residual': 699.41}])

            # USD Credit note at rate 2030 USD = 116 MXN (1:17.5)
            refund = self._create_invoice_mx(
                move_type='out_refund',
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1750.0,
                    }),
                ],
            )
            (refund + invoice).line_ids.filtered(lambda line: line.display_type == 'payment_term').reconcile()
            self.assertRecordValues(invoice + refund, [
                # The refund reconciled 116 MXN with the invoice.
                # An exchange difference of (2030 - 1972) / 17 ~= 3.41 has been created.
                {'amount_residual': 580.0},
                {'amount_residual': 0.0},
            ])

            # Pay 10% in USD at rate 1:17.5
            # The credit note should be subtracted from the residual chain.
            payment4 = self._register_payment(
                invoice,
                amount=2030.0,
                currency_id=usd.id,
                payment_date=date3,
            )
            with self.with_mocked_pac_sign_success():
                payment4.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment4.move_id, 'test_partial_payment_3_pay4')
            self.assertRecordValues(invoice, [{'amount_residual': 464.0}])

    def test_partial_payment_4(self):
        """ Test the residual chain of a foreign currency invoice partially reconciled with a credit note,
        then fully paid in the same foreign currency at another rate. The exchange difference created by the
        payment reconciliation must not prevent the credit note from being deducted from the residual chain.
        """
        date1 = self.frozen_today - relativedelta(days=2)
        date_rate2 = self.frozen_today - relativedelta(days=1)
        date2 = self.frozen_today
        # The new rate is dated strictly before the payment (not the same day) so the exchange
        # difference is guaranteed to be created regardless of the "rate as of date" lookup semantics.
        usd = self.setup_other_currency('USD', rates=[(date1, 17.0), (date_rate2, 16.5)])

        with self.mx_external_setup(date1):
            # USD invoice: 19720 USD = 1160 MXN (1:17)
            invoice = self._create_invoice_mx(
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 17000.0,
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            # Partial USD credit note at the same rate: 1972 USD = 116 MXN (1:17)
            refund = self._create_invoice_mx(
                move_type='out_refund',
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1700.0,
                    }),
                ],
            )
            (refund + invoice).line_ids.filtered(lambda line: line.display_type == 'payment_term').reconcile()
            self.assertRecordValues(invoice + refund, [
                {'amount_residual': 17748.0},
                {'amount_residual': 0.0},
            ])

        with self.mx_external_setup(date2):
            # Pay the remaining 17748 USD at rate 1:16.5 (dated 'date_rate2', strictly before this
            # payment). The rate differs from the one used for the invoice/CN (1:17), so reconciling
            # the payment is guaranteed to create an exchange difference move on the invoice/payment
            # partial (1075.64 MXN paid - 1044.0 MXN residual).
            # The credit note should be subtracted from the residual chain:
            # ImpSaldoAnt="17748.00", ImpPagado="17748.00", ImpSaldoInsoluto="0.00"
            payment = self._register_payment(
                invoice,
                amount=17748.0,
                currency_id=usd.id,
                payment_date=date2,
            )
            self.assertRecordValues(invoice, [{'amount_residual': 0.0}])
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_partial_payment_4_pay1')

    def test_full_payment_rate(self):
        date1 = fields.Date.today() - relativedelta(days=1)
        date2 = fields.Date.today()
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(date1, days=1), 0.049905678268), (fields.Date.subtract(date2, days=1), 0.049073733284)])

        with self.mx_external_setup(date1):
            invoice = self._create_invoice_mx(
                date=date1,
                currency_id=usd.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 5490.00,
                        'quantity': 1,
                        'discount': 0.0,
                        'tax_ids': [Command.set(self.tax_16.ids)],
                    })],
                )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self.assertEqual(invoice.l10n_mx_edi_cfdi_state, 'sent', f'Error: {invoice.l10n_mx_edi_document_ids.message}')

        with self.mx_external_setup(date2):
            payment = self._register_payment(
                invoice,
                amount=129772.07,
                payment_date=date2,
                currency_id=self.env.ref('base.MXN').id,
            )
            with self.with_mocked_pac_sign_success():
                invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
            self.assertEqual(payment.move_id.l10n_mx_edi_cfdi_state, 'sent', f'Error: {payment.move_id.l10n_mx_edi_document_ids.message}')
            self._assert_invoice_payment_cfdi(payment.move_id, 'test_full_payment_rate')

    def test_statement_line_partially_reconciled_multiple_invoices(self):
        payment_date = self.frozen_today

        with self.mx_external_setup(payment_date):
            invoice_1 = self._create_invoice(
                invoice_line_ids=[Command.create({
                    'product_id': self.product.id,
                    'price_unit': 100,  # + tax(16%)
                })],
                l10n_mx_edi_payment_policy='PPD',
            )
            invoice_2 = self._create_invoice(
                invoice_line_ids=[Command.create({
                    'product_id': self.product.id,
                    'price_unit': 100,  # + tax(16%)
                })],
                l10n_mx_edi_payment_policy='PPD',
            )
            (invoice_1 + invoice_2).action_post()

            with self.with_mocked_pac_sign_success():
                invoice_1._l10n_mx_edi_cfdi_invoice_try_send()
                invoice_2._l10n_mx_edi_cfdi_invoice_try_send()

            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': self.company_data['default_journal_bank'].id,
                'amount': 232,
                'date': payment_date,
                'payment_ref': 'test'
            })

            # Reconcile bank transaction with invoice_1
            st_line.set_line_bank_statement_line(invoice_1.line_ids.filtered(lambda l: l.display_type == 'payment_term').ids)
            self.assertRecordValues(st_line, [{'is_reconciled': False, 'l10n_mx_edi_cfdi_state': False}])
            self.assertRecordValues(invoice_1, [{'payment_state': 'paid', 'l10n_mx_edi_update_payments_needed': False}])
            self.assertRecordValues(invoice_2, [{'payment_state': 'not_paid', 'l10n_mx_edi_update_payments_needed': False}])
            with self.with_mocked_pac_sign_success():
                invoice_1.l10n_mx_edi_cfdi_invoice_try_update_payments()
            self.assertRecordValues(st_line, [{'l10n_mx_edi_cfdi_state': False}])

            # Reconcile bank transaction with invoice_2
            st_line.set_line_bank_statement_line(invoice_2.line_ids.filtered(lambda l: l.display_type == 'payment_term').ids)
            self.assertRecordValues(st_line, [{'is_reconciled': True, 'l10n_mx_edi_cfdi_state': False}])
            self.assertRecordValues(invoice_1, [{'payment_state': 'paid', 'l10n_mx_edi_update_payments_needed': True}])
            self.assertRecordValues(invoice_2, [{'payment_state': 'paid', 'l10n_mx_edi_update_payments_needed': True}])
            with self.with_mocked_pac_sign_success():
                invoice_2.l10n_mx_edi_cfdi_invoice_try_update_payments()
            self.assertRecordValues(st_line, [{'l10n_mx_edi_cfdi_state': 'sent'}])

    def test_payment_partially_reconciled_multiple_invoices(self):
        payment_date = self.frozen_today
        in_payment_state = self.env['account.move']._get_invoice_in_payment_state()

        with self.mx_external_setup(payment_date):
            invoice_1 = self._create_invoice(
                invoice_line_ids=[Command.create({
                    'product_id': self.product.id,
                    'price_unit': 100,  # + tax(16%)
                })],
                l10n_mx_edi_payment_policy='PPD',
            )
            invoice_2 = self._create_invoice(
                invoice_line_ids=[Command.create({
                    'product_id': self.product.id,
                    'price_unit': 100,  # + tax(16%)
                })],
                l10n_mx_edi_payment_policy='PPD',
            )
            (invoice_1 + invoice_2).action_post()
            with self.with_mocked_pac_sign_success():
                invoice_1._l10n_mx_edi_cfdi_invoice_try_send()
                invoice_2._l10n_mx_edi_cfdi_invoice_try_send()

            payment = self.env['account.payment'].create({
                'amount': 232.0,
                'date': payment_date,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice_1.partner_id.id,
            })
            payment.action_post()
            payment.action_draft()
            _liquidity_lines, counterpart_lines, _writeoff_lines = payment._seek_for_lines()
            payment.move_id.line_ids = [
                Command.update(counterpart_lines.id, {'balance': -116.0}),
                Command.create({'account_id': counterpart_lines.account_id.id, 'balance': -116.0}),
            ]
            payment.action_post()
            _liquidity_lines, counterpart_lines, _writeoff_lines = payment._seek_for_lines()

            # Reconcile payment with invoice_1
            (counterpart_lines[0] + invoice_1.line_ids.filtered(lambda l: l.display_type == 'payment_term')).reconcile()
            self.assertRecordValues(payment, [{'is_reconciled': False, 'l10n_mx_edi_cfdi_state': False}])
            self.assertRecordValues(invoice_1, [{'payment_state': in_payment_state, 'l10n_mx_edi_update_payments_needed': False}])
            self.assertRecordValues(invoice_2, [{'payment_state': 'not_paid', 'l10n_mx_edi_update_payments_needed': False}])
            with self.with_mocked_pac_sign_success():
                invoice_1.l10n_mx_edi_cfdi_invoice_try_update_payments()
            self.assertRecordValues(payment, [{'l10n_mx_edi_cfdi_state': False}])

            # Reconcile payment with invoice_2
            (counterpart_lines[1] + invoice_2.line_ids.filtered(lambda l: l.display_type == 'payment_term')).reconcile()
            self.assertRecordValues(payment, [{'is_reconciled': True, 'l10n_mx_edi_cfdi_state': False}])
            self.assertRecordValues(invoice_1, [{'payment_state': in_payment_state, 'l10n_mx_edi_update_payments_needed': True}])
            self.assertRecordValues(invoice_2, [{'payment_state': in_payment_state, 'l10n_mx_edi_update_payments_needed': True}])
            with self.with_mocked_pac_sign_success():
                invoice_2.l10n_mx_edi_cfdi_invoice_try_update_payments()
            self.assertRecordValues(payment, [{'l10n_mx_edi_cfdi_state': 'sent'}])

    def test_sw_finkok_CRP20211_usd_statement_in_mxn_journal_rounded_exchange_rate(self):
        """ Test rounding of exchange rate in payment cfdi of a statement line with foreign currency
        using Finkok, SW, or Solucion Factible does not trigger the CRP20211 error.
        """
        payment_date = self.frozen_today
        # Rates for how much USD for 1 MXN
        usd = self.setup_other_currency('USD', rates=[(fields.Date.subtract(payment_date, days=1), 0.05)])

        bank_journal = self.env['account.journal'].create({
            'name': 'Bank 123456',
            'code': 'BNK67',
            'type': 'bank',
            'bank_account_number': '123456',
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_transferencia').id,  # To default to this payment method
        })

        for pac in ['finkok', 'solfact']:
            self.env.company.l10n_mx_edi_pac = pac

            with self.mx_external_setup(payment_date):
                invoice = self._create_invoice_mx(
                    currency_id=usd.id,
                    invoice_line_ids=[
                        Command.create({
                            'product_id': self.product.id,
                            'price_unit': 11396.55,  # + tax(16%) = 13220.0 USD
                        }),
                    ],
                )

                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

            with self.mx_external_setup(payment_date):
                # Those are the important amount because
                # 305147.51 MXN / 13220.0 USD = 23.082262481 ≃ 23.082262 MXN/USD
                # 13220.0 USD * 23.082262 MXN/USD = 305147.50 MXN which is not 305147.51 MXN
                st_line = self.env['account.bank.statement.line'].create({
                    'journal_id': bank_journal.id,
                    'amount_currency': 13220.00,  # USD
                    'amount': 305147.51,  # MXN
                    'foreign_currency_id': self.env.ref('base.USD').id,
                    'date': payment_date,
                    'payment_ref': 'test'
                })

                # Reconcile bank transaction with invoice
                st_line.set_line_bank_statement_line(invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term').ids)
                self.assertRecordValues(st_line, [{'is_reconciled': True}])
                self.assertRecordValues(invoice, [{'payment_state': 'paid'}])

                # Generate payment cfdi file
                with self.with_mocked_pac_sign_success():
                    st_line.move_id._l10n_mx_edi_cfdi_payment_try_send()

                # Without fix, the generated cfdi payment file will be refused by Quadrum (finkok) due to CRP20211
                self._assert_invoice_payment_cfdi(st_line.move_id, 'test_sw_finkok_CRP20211_usd_statement_in_mxn_journal_rounded_exchange_rate_pay')

    def test_foreign_curr_payment_comp_curr_invoice_forced_balance(self):
        date1 = self.frozen_today - relativedelta(days=1)
        date2 = self.frozen_today
        chf = self.setup_other_currency('CHF', rates=[(fields.Date.subtract(date1, days=1), 16.0), (fields.Date.subtract(date2, days=1), 17.0)])

        with self.mx_external_setup(date1):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 1000.0,  # = 62.5 CHF
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        with self.mx_external_setup(date2):
            payment = self.env['account.payment.register'] \
                .with_context(active_model='account.move', active_ids=invoice.ids) \
                .create({
                    'payment_date': date2,
                    'currency_id': chf.id,
                    'amount': 62.0,  # instead of 62.5 CHF
                    'payment_difference_handling': 'reconcile',
                    'writeoff_account_id': self.env.company.expense_currency_exchange_account_id.id,
                }) \
                ._create_payments()
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(
                payment.move_id,
                'test_foreign_curr_payment_comp_curr_invoice_forced_balance',
            )

    def test_comp_curr_payment_foreign_curr_invoice_forced_balance(self):
        date1 = self.frozen_today - relativedelta(days=1)
        date2 = self.frozen_today
        chf = self.setup_other_currency('CHF', rates=[(fields.Date.subtract(date1, days=1), 16.0), (fields.Date.subtract(date2, days=1), 17.0)])

        with self.mx_external_setup(date1):
            invoice = self._create_invoice_mx(
                currency_id=chf.id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 62.5,  # = 1000 MXN
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        with self.mx_external_setup(date2):
            payment = self.env['account.payment.register'] \
                .with_context(active_model='account.move', active_ids=invoice.ids) \
                .create({
                    'payment_date': date2,
                    'currency_id': self.comp_curr.id,
                    'amount': 998.0,  # instead of 1000.0 MXN
                    'payment_difference_handling': 'reconcile',
                    'writeoff_account_id': self.env.company.expense_currency_exchange_account_id.id,
                }) \
                ._create_payments()
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            self._assert_invoice_payment_cfdi(
                payment.move_id,
                'test_comp_curr_payment_foreign_curr_invoice_forced_balance',
            )

    def test_cfdi_date_with_timezone(self):

        def assert_cfdi_date(document, tz, expected_datetime=None):
            self.assertTrue(document)
            cfdi_node = etree.fromstring(document.attachment_id.raw.content)
            cfdi_date_str = cfdi_node.get('Fecha')
            expected_datetime = (expected_datetime or self.frozen_today.astimezone(tz).replace(tzinfo=None)).replace(microsecond=0)
            current_date = datetime.strptime(cfdi_date_str, CFDI_DATE_FORMAT).replace(microsecond=0)
            self.assertEqual(current_date, expected_datetime)

        addresses = [
            # America/Tijuana UTC-8 (-7 DST)
            {
                'state_id': self.env.ref('base.state_mx_bc').id,
                'zip': '22750',
                'timezone': ZoneInfo('America/Tijuana'),
            },
            # America/Bogota UTC-5
            {
                'state_id': self.env.ref('base.state_mx_q_roo').id,
                'zip': '77890',
                'timezone': ZoneInfo('America/Bogota'),
            },
            # America/Boise UTC-7 (-6 DST)
            {
                'state_id': self.env.ref('base.state_mx_chih').id,
                'zip': '31820',
                'timezone': ZoneInfo('America/Boise'),
            },
            # America/Guatemala (Tiempo del centro areas)
            {
                'state_id': self.env.ref('base.state_mx_nay').id,
                'zip': '63726',
                'timezone': ZoneInfo('America/Guatemala'),
            },
            # America/Matamoros UTC-6 (-5 DST)
            {
                'state_id': self.env.ref('base.state_mx_tamps').id,
                'zip': '87300',
                'timezone': ZoneInfo('America/Matamoros'),
            },
            # Pacific area
            {
                'state_id': self.env.ref('base.state_mx_son').id,
                'zip': '83530',
                'timezone': ZoneInfo('America/Hermosillo'),
            },
            # America/Guatemala UTC-6
            {
                'state_id': self.env.ref('base.state_mx_ags').id,
                'zip': '20914',
                'timezone': ZoneInfo('America/Guatemala'),
            },
        ]

        for address in addresses:
            tz = address.pop('timezone')
            with self.subTest(zip=address['zip']):
                self.env.company.partner_id.write(address)

                # Invoice on the future.
                with self.mx_external_setup(self.frozen_today):
                    invoice = self._create_invoice_mx(
                        invoice_date=self.frozen_today + relativedelta(days=2),
                        invoice_line_ids=[Command.create({'product_id': self.product.id})],
                    )
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    document = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')[:1]
                    assert_cfdi_date(document, tz)

                # Invoice on the past.
                date_in_the_past = self.frozen_today - relativedelta(days=2)
                with self.mx_external_setup(self.frozen_today):
                    invoice = self._create_invoice_mx(
                        invoice_date=date_in_the_past,
                        invoice_line_ids=[Command.create({'product_id': self.product.id})],
                    )
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    document = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')[:1]
                    assert_cfdi_date(document, tz, expected_datetime=date_in_the_past.replace(hour=23, minute=59, second=0))

                # Invoice created in the past with a date which was then in the future,
                # which was already attempted to be sent in the past and which we try to resend today
                with self.mx_external_setup(self.frozen_today):
                    invoice = self._create_invoice_mx(invoice_date=date_in_the_past)
                    previous_send_time = (self.frozen_today - relativedelta(days=2)).replace(tzinfo=None)
                    invoice.l10n_mx_edi_post_time = previous_send_time
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    document = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')[:1]
                    assert_cfdi_date(document, tz, expected_datetime=previous_send_time)

                with self.mx_external_setup(self.frozen_today):
                    invoice = self._create_invoice_mx(invoice_line_ids=[Command.create({'product_id': self.product.id})])
                    with self.with_mocked_pac_sign_success():
                        invoice._l10n_mx_edi_cfdi_invoice_try_send()
                    document = invoice.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')[:1]
                    assert_cfdi_date(document, tz)

                    # Test an immediate payment.
                    payment = self.env['account.payment.register'] \
                        .with_context(active_model='account.move', active_ids=invoice.ids) \
                        .create({'amount': 100.0}) \
                        ._create_payments()
                    with self.with_mocked_pac_sign_success():
                        payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
                    document = payment.l10n_mx_edi_payment_document_ids.filtered(lambda x: x.state == 'payment_sent')[:1]
                    assert_cfdi_date(document, tz)

                # Test a payment made 10 days ago but send today.
                with self.mx_external_setup(self.frozen_today - relativedelta(days=10)):
                    payment = self.env['account.payment.register'] \
                        .with_context(active_model='account.move', active_ids=invoice.ids) \
                        .create({'amount': 100.0}) \
                        ._create_payments()
                with self.mx_external_setup(self.frozen_today):
                    with self.with_mocked_pac_sign_success():
                        payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
                    document = payment.l10n_mx_edi_payment_document_ids.filtered(lambda x: x.state == 'payment_sent')[:1]
                    assert_cfdi_date(document, tz)

    def test_vendor_bill_payment_production_sign_flow_cancel_from_the_sat(self):
        """ Test the case where the vendor bill is manually canceled from the SAT portal by the user (production environment). """
        self.env.company.l10n_mx_edi_pac_test_env = False
        self.env.company.l10n_mx_edi_pac_username = 'test'
        self.env.company.l10n_mx_edi_pac_password = 'test'

        file_name = "test_import_bill"
        self.env.company.partner_id.company_id = self.env.company
        file_content = self.file_read(f'{self.test_module}/tests/test_files/import/{file_name}.xml').content
        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )

        # Not checking bill values since they are already checked in a different test, only SAT
        self.assertEqual(new_bill.l10n_mx_edi_invoice_document_ids.state, 'invoice_received')
        new_bill.action_post()
        self.assertTrue(new_bill.l10n_mx_edi_update_sat_needed)
        with self.with_mocked_sat_call(lambda _x: 'valid'):
            new_bill.l10n_mx_edi_cfdi_try_sat()
        self.assertTrue(new_bill.l10n_mx_edi_update_sat_needed)

        # Manual cancellation from the SAT portal
        with self.with_mocked_sat_call(lambda _x: 'cancelled'):
            new_bill.l10n_mx_edi_cfdi_try_sat()

        inv_cancel_doc_values = {
            'move_id': new_bill.id,
            'state': 'invoice_cancel',
            'sat_state': 'cancelled',
        }
        inv_sent_doc_values = {
            'move_id': new_bill.id,
            'state': 'invoice_received',
            'sat_state': 'valid',
        }
        self.assertRecordValues(new_bill.l10n_mx_edi_invoice_document_ids.sorted(), [
            inv_cancel_doc_values,
            inv_sent_doc_values,
        ])
        self.assertRecordValues(new_bill, [{
            'state': 'cancel',
            'need_cancel_request': False,
            'show_reset_to_draft_button': True,
            'l10n_mx_edi_update_sat_needed': False,
            'l10n_mx_edi_cfdi_sat_state': 'cancelled',
            'l10n_mx_edi_cfdi_state': 'cancel',
        }])

    def test_cfdi_multi_relation_origin(self):
        "Ensure that a CfdiRelacionados Node should be created for each relation"
        cfdi_origin = "01|6c76a910-2115-4a2c-bf15-e67c1505dd21,02|6c76a910-2115-4a2c-bf15-e67c1505bb22"
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_cfdi_origin=cfdi_origin
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
                self._assert_invoice_cfdi(invoice, 'test_cfdi_multi_relation_inv')

        # Testing with a relation with multiple uuids
        cfdi_origin += ",7a86a910-3145-4a2c-bf15-e67c1505de30"
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                l10n_mx_edi_cfdi_origin=cfdi_origin
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
                self._assert_invoice_cfdi(invoice, 'test_cfdi_multi_uuid_inv')

    def test_cfdi_to_public_credit_note_g02_usage(self):
        with self.mx_external_setup(self.frozen_today):
            credit_note = self._create_invoice_mx(
                move_type='out_refund',
                l10n_mx_edi_cfdi_to_public=True,
                l10n_mx_edi_usage='G02',
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 500.0,
                    }),
                ],
            )
            with self.with_mocked_pac_sign_success():
                credit_note._l10n_mx_edi_cfdi_invoice_try_send()

            document = credit_note.l10n_mx_edi_invoice_document_ids.filtered(lambda x: x.state == 'invoice_sent')
            cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(document.attachment_id.raw.content)
            self.assertEqual(cfdi_infos['usage'], 'G02')

    def test_extra_invoice_report_values(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(invoice_date_due=self.frozen_today + relativedelta(months=1))
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            report_values = invoice._l10n_mx_edi_get_extra_invoice_report_values()
            self.assertEqual(report_values['payment_method'], 'PPD')
            self.assertEqual(report_values['payment_way'], '99 - Por Definir')

    def test_update_payments_rate(self):
        """ This tests make sure that the document generated after updating payments show the correct payment amount and exchange rate used """
        date1 = fields.Date.today()
        usd = self.setup_other_currency('USD', rates=[(date1, 0.05)])

        bank_journal = self.env['account.journal'].create({
            'name': 'Bank 123456',
            'code': 'BNK67',
            'type': 'bank',
            'currency_id': usd.id,
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_transferencia').id,
        })

        with self.mx_external_setup(date1):
            invoice = self._create_invoice_mx(
                date=date1,
                currency_id=self.env.ref('base.MXN').id,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 300.00,
                        'quantity': 1,
                        'tax_ids': [],
                    })],
                l10n_mx_edi_payment_policy='PPD',
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self.assertEqual(invoice.l10n_mx_edi_cfdi_state, 'sent', f'Error: {invoice.l10n_mx_edi_document_ids.message}')

            st_line = self.env['account.bank.statement.line'].create({
                'journal_id': bank_journal.id,
                'amount': 15.00,
                'foreign_currency_id': usd.id,
                'date': date1,
                'payment_ref': 'test'
            })

            # Reconcile bank transaction with invoice
            st_line.set_line_bank_statement_line(invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term').ids)
            with self.with_mocked_pac_sign_success():
                invoice.l10n_mx_edi_cfdi_invoice_try_update_payments()
            document = invoice.l10n_mx_edi_document_ids.filtered(lambda d: d.state == 'payment_sent')[0]
            xml_tree = self.get_xml_tree_from_string(document.attachment_id.raw.content)
            pago = xml_tree.xpath("//*[local-name()='Pago']")
            self.assertEqual(len(pago), 1)
            self.assertEqual(pago[0].get('Monto'), '15.00')
            self.assertEqual(pago[0].get('MonedaP'), 'USD')
            self.assertEqual(pago[0].get('TipoCambioP'), '20.000000')

    def test_cfdi_future_payment(self):
        """
        Ensure the l10n_mx_edi_update_payments_needed field is False
        when having only payments in the future. It means that the 'Update Payments'
        button will be invisible in the view.
        """
        with self.mx_external_setup(self.frozen_today):
            # Create a PDD invoice
            invoice = self._create_invoice_mx()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            # create a payment in the future
            self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
                'amount': invoice.amount_total / 2,
                'payment_date': self.frozen_today + relativedelta(days=1)
            })._create_payments()

            self.assertFalse(invoice.l10n_mx_edi_update_payments_needed)

            # create a payment today
            self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
                'payment_date': self.frozen_today
            })._create_payments()

            invoice.invalidate_recordset(['l10n_mx_edi_update_payments_needed'])
            self.assertTrue(invoice.l10n_mx_edi_update_payments_needed)

    def test_invoice_pdf_cfdi_decode(self):
        """Test that the cfdi information is correctly decoded for MX custom invoice PDF"""
        company_id = self.env.company.id
        ieps_tax_26_5 = self.env.ref(f'account.{company_id}_ieps_26_5_sale')
        isr_whh_1_25 = self.env.ref(f'account.{company_id}_mx_wh_1_25_sale')
        iva_tax_16 = self.env.ref(f'account.{company_id}_tax12')
        exento_tax = self.env.ref(f'account.{company_id}_tax19')
        self.product.l10n_mx_edi_predial_account = "1235543"
        # Test most complete case
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice_mx(
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        tax_ids=(iva_tax_16 | isr_whh_1_25 | exento_tax),
                        price_unit=2000.0,
                    ),
                    self._prepare_invoice_line(
                        product_id=self.product,
                        tax_ids=(iva_tax_16 | isr_whh_1_25 | ieps_tax_26_5),
                        price_unit=295.0,
                    ),
                    self._prepare_invoice_line(
                        product_id=self.product,
                        tax_ids=self.local_tax_16_transferred,
                        price_unit=1000.0,
                    ),
                    self._prepare_invoice_line(
                        product_id=self.product,
                        tax_ids=self.local_tax_8_withholding,
                        price_unit=2000.0,
                    ),
                ]
            )

            with self.with_mocked_pac_sign_error():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            self.assertTrue(not invoice._l10n_mx_edi_get_extra_invoice_report_values(), "No CFDI was signed, so there shouldn't be any info to extract")

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

        cfdi_infos = invoice._l10n_mx_edi_get_extra_invoice_report_values()
        self.assertTrue(cfdi_infos, "CFDI was succesfully signed. CFDI information should be extracted without any issues.")
        html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', invoice.ids, data=cfdi_infos)[0]
        text = html2plaintext(html)
        self.assertRegex(text, 'This document is a printed representation of a CFDI', "MX CFDI PDF should've been generated.")

        cfdi_infos_expected_vals = {
            'amount_subtotal': 5373.18,  # IEPS are directly applied on the subtotal (5000 + (295 * 1.265) ~= 5373.18)
            'total_amount': 5724.20,
            'total_amount_text': 'FIVE THOUSAND, SEVEN HUNDRED AND TWENTY-FOUR PESOS 20/100 M.N',
            'amount_discount': 0.0,
            'currency_rate': None,
            'usage': 'G03',
            'usage_desc': 'General expenses',
            'receptor_fiscal_regime_name': 'General de Ley Personas Morales',
            'payment_way': '99 - Por Definir',
            'payment_method': 'PPD',
            'bank_account': None,
            'cfdi_type_label': 'I - Income',
            'export_type': '01',
        }
        current_cfdi_vals = {}
        for key in cfdi_infos_expected_vals:
            if key not in cfdi_infos:
                continue
            current_cfdi_vals[key] = cfdi_infos[key]
        self.assertDictEqual(current_cfdi_vals, cfdi_infos_expected_vals)

        conceptos_list = cfdi_infos['conceptos_list']
        self.assertEqual(len(conceptos_list), 4, "There should be 4 lines")

        expected_concepto_vals = (
            {
                'description': '[product_mx] product_mx',
                'product_service_code': '01010101',
                'identification_number': 'product_mx',
                'quantity': 1.0,
                'unit': 'KG',
                'unit_code': 'KGM',
                'price_unit': 2000.0,
                'amount': 2000.0,
                'tax_object': '02',
                'discount': 0.0,
                'predial_account': '1235543',
            }, {
                'description': '[product_mx] product_mx',
                'product_service_code': '01010101',
                'identification_number': 'product_mx',
                'quantity': 1.0,
                'unit': 'KG',
                'unit_code': 'KGM',
                'price_unit': 373.175,
                'amount': 373.175,
                'tax_object': '02',
                'discount': 0.0,
                'predial_account': '1235543',
            }, {
                'description': '[product_mx] product_mx',
                'product_service_code': '01010101',
                'identification_number': 'product_mx',
                'quantity': 1.0,
                'unit': 'KG',
                'unit_code': 'KGM',
                'price_unit': 1000,
                'amount': 1000,
                'tax_object': '01',
                'discount': 0.0,
                'predial_account': '1235543',
            }, {
                'description': '[product_mx] product_mx',
                'product_service_code': '01010101',
                'identification_number': 'product_mx',
                'quantity': 1.0,
                'unit': 'KG',
                'unit_code': 'KGM',
                'price_unit': 2000,
                'amount': 2000,
                'tax_object': '01',
                'discount': 0.0,
                'predial_account': '1235543',
            },
        )
        for concepto, expected_vals in zip(conceptos_list, expected_concepto_vals):
            current_vals = {}
            for key in expected_vals:
                if key not in concepto:
                    continue
                current_vals[key] = concepto[key]
            self.assertDictEqual(current_vals, expected_vals)

        impuestos_list = cfdi_infos['impuestos_list']
        # We have 4 taxes: 16% IVA, -1.25% ISR, IVA Exento and 26.5% IEPS
        # But since IEPS breakdown is disabled in this partner, there should be only 3
        self.assertEqual(len(impuestos_list), 5)
        expected_impuesto_vals = [
            {
                'cfdi_code': '002',
                'tax_name': 'IVA',
                'factor_type': 'Tasa',
                'rate_or_fee': 16.00,
                'amount_base': 2373.18,
                'amount_tax': 379.71,
            }, {
                'cfdi_code': '002',
                'tax_name': 'IVA',
                'factor_type': 'Exento',
                'rate_or_fee': None,
                'amount_base': 2000.00,
                'amount_tax': 0,
            }, {
                'cfdi_code': '001',
                'tax_name': 'ISR',
                'factor_type': 'Tasa',
                'rate_or_fee': -1.25,
                'amount_base': 2295.0,
                'amount_tax': -28.6875,
            }, {
                'tax_name': 'Local VAT',
                'amount_tax': -160,
                'is_local_tax': True,
            }, {
                'tax_name': 'Local VAT',
                'amount_tax': 160,
                'is_local_tax': True,
            }
        ]

        for impuesto, expected_vals in zip(impuestos_list, expected_impuesto_vals):
            current_vals = {}
            for key in expected_vals:
                if key not in impuesto:
                    continue
                current_vals[key] = impuesto[key]
            self.assertDictEqual(current_vals, expected_vals)

        # Test that when applying a discount and using a different currency and enabling ieps breakdown
        self.partner_mx.l10n_mx_edi_ieps_breakdown = True
        other_currency = self.setup_other_currency('USD', rates=[(fields.Date.subtract(self.frozen_today, days=1), 1 / 17.1392)])
        with self.mx_external_setup(self.frozen_today), self.with_mocked_pac_sign_success():
            other_currency_inv = self._create_invoice_mx(
                currency_id=other_currency,
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product,
                        price_unit=150.0,
                        discount=20.0,
                        tax_ids=ieps_tax_26_5,
                    ),
                ]
            )
            other_currency_inv._l10n_mx_edi_cfdi_invoice_try_send()

        cfdi_infos = other_currency_inv._l10n_mx_edi_get_extra_invoice_report_values()
        cfdi_infos_expected_vals = {
            'amount_discount': 30.0,
            'currency_rate': '17.139200',
            'amount_subtotal': 150.0,
            'total_amount': 151.8,  # 150 * .80 * 1.265 = 151.8
        }
        current_cfdi_vals = {}
        for key in cfdi_infos_expected_vals:
            if key not in cfdi_infos:
                continue
            current_cfdi_vals[key] = cfdi_infos[key]
        self.assertDictEqual(current_cfdi_vals, cfdi_infos_expected_vals)

        self.assertEqual(len(cfdi_infos['impuestos_list']), 1, 'CFDI should contain IEPS')

        ieps_vals = cfdi_infos['impuestos_list'][0]
        expected_ieps_vals = {
            'cfdi_code': '003',
            'tax_name': 'IEPS',
            'factor_type': 'Tasa',
            'rate_or_fee': 26.5,
            'amount_base': 120.0,  # 150 * .80
            'amount_tax': 31.8,
        }
        current_vals = {}
        for key in expected_ieps_vals:
            if key not in ieps_vals:
                continue
            current_vals[key] = ieps_vals[key]
        self.assertDictEqual(current_vals, expected_ieps_vals)

    def test_cfdi_invoice_pdf_render(self):
        """This test checks that when we print a invoice pdf, the document to render is the custom mx pdf.
        Also checks the label for a not cfdi only appears for MX invoices that haven't been signed yet.
        """
        # Test for mx out_invoice and out_refund
        with self.mx_external_setup(self.frozen_today):
            # Case for out invoices
            mx_invoice = self._create_invoice_mx()

            self.assertEqual(mx_invoice._get_name_invoice_report(), 'account.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_invoice.ids)[0]
            text = html2plaintext(html)
            self.assertRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label should appear on MX invoices that are not signed yet.")

            with self.with_mocked_pac_sign_error():
                mx_invoice._l10n_mx_edi_cfdi_invoice_try_send()

            self.assertEqual(mx_invoice._get_name_invoice_report(), 'account.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_invoice.ids)[0]
            text = html2plaintext(html)
            self.assertRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label should appear on MX invoices that are not signed yet.")

            with self.with_mocked_pac_sign_success():
                mx_invoice._l10n_mx_edi_cfdi_invoice_try_send()

            # Lets simulate that even if the sign was succesful, the cfdi decoding wasn't
            with patch.object(self.env.registry['account.move'], '_l10n_mx_edi_get_extra_invoice_report_values', lambda inv: {}):
                # Name of report should be of mx one, but still, the printed report should be the standard one
                self.assertEqual(mx_invoice._get_name_invoice_report(), 'l10n_mx_edi.report_invoice_document')
                html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_invoice.ids)[0]
                text = html2plaintext(html)
                self.assertRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label should appear on MX invoices that are not signed yet.")

            self.assertEqual(mx_invoice._get_name_invoice_report(), 'l10n_mx_edi.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_invoice.ids)[0]
            text = html2plaintext(html)
            self.assertNotRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label shouldn't appear on signed MX invoices.")

            # Case for out refunds
            mx_refund = self._create_invoice_mx(
                move_type='out_refund',
                reversed_entry_id=mx_invoice.id,
            )

            self.assertEqual(mx_refund._get_name_invoice_report(), 'account.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_refund.ids)[0]
            text = html2plaintext(html)
            self.assertRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label should appear on MX invoices that are not signed yet.")

            with self.with_mocked_pac_sign_error():
                mx_refund._l10n_mx_edi_cfdi_invoice_try_send()

            self.assertEqual(mx_refund._get_name_invoice_report(), 'account.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_refund.ids)[0]
            text = html2plaintext(html)
            self.assertRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label should appear on MX invoices that are not signed yet.")

            with self.with_mocked_pac_sign_success():
                mx_refund._l10n_mx_edi_cfdi_invoice_try_send()

            # Lets simulate that even if the sign was succesful, the cfdi decoding wasn't
            with patch.object(self.env.registry['account.move'], '_l10n_mx_edi_get_extra_invoice_report_values', lambda inv: {}):
                # Name of report should be of mx one, but still, the printed report should be the standard one
                self.assertEqual(mx_refund._get_name_invoice_report(), 'l10n_mx_edi.report_invoice_document')
                html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_refund.ids)[0]
                text = html2plaintext(html)
                self.assertRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label should appear on MX invoices that are not signed yet.")

            self.assertEqual(mx_refund._get_name_invoice_report(), 'l10n_mx_edi.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', mx_refund.ids)[0]
            text = html2plaintext(html)
            self.assertNotRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label shouldn't appear on signed MX invoices.")

    def test_no_cfdi_invoice_pdf_render(self):
        """Test case when cfdi label should not be rendered and MX custom report shouldn't too"""
        non_mx_company = self.non_mx_company_data['company']
        move_types_by_company = {
            non_mx_company: ("out_invoice", "out_refund", "in_invoice", "in_refund", "in_receipt", "out_receipt"),
            self.env.company: ("in_invoice", "in_refund", "in_receipt"),
        }
        for company, move_types in move_types_by_company.items():
            invoices = self.env['account.move']
            for move_type in move_types:
                invoices |= self._create_invoice(
                    move_type=move_type,
                    company_id=company,
                    invoice_line_ids=[
                        self._prepare_invoice_line(product_id=self.generic_product)
                    ],
                )

            for invoice in invoices:
                self.assertEqual(invoice._get_name_invoice_report(), 'account.report_invoice_document')
            html = self.env['ir.actions.report']._render_qweb_html('account.report_invoice_with_payments', invoices.ids)[0]
            text = html2plaintext(html)
            self.assertNotRegex(text, 'NOT A CFDI INVOICE', "Not a cfdi label shouldn't appear on non MX company documents or if is not a CFDI Invoice")

        # Test case when we import a bill. Even if it is a CFDI, the custom report shouldn't be printed.
        file_name = "test_import_bill"
        full_file_path = misc.file_path(f'{self.test_module}/tests/test_files/import/{file_name}.xml')

        self.env.company.partner_id.company_id = self.env.company

        with file_open(full_file_path, "rb") as file:
            file_content = file.read()

        new_bill = self._upload_document_on_journal(
            journal=self.company_data['default_journal_purchase'],
            content=file_content,
            filename=file_name,
        )
        self.assertTrue(new_bill.l10n_mx_edi_cfdi_uuid)
        self.assertEqual(new_bill._get_name_invoice_report(), 'account.report_invoice_document')

    def test_payment_method_from_journal(self):
        """ Test that a payment created without any explicit payment way, will take the default one
            from the journal.
        """
        bank_journal = self.company_data['default_journal_bank']
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_mx.id,
            'amount': 100.0,
            'journal_id': bank_journal.id,
        }

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        self.assertRecordValues(payment, [{
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_transferencia').id,
        }])

        bank_journal.l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_tarjeta_de_credito')

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        self.assertRecordValues(payment, [{
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_tarjeta_de_credito').id,
        }])
