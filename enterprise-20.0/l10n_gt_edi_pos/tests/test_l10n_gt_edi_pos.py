from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import formatLang

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nGTEdiPos(CommonPosTest, TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPointOfSaleHttpCommon.setup_country('gt')
    def setUpClass(cls):
        super().setUpClass()

        # The legal max limit for sales to an unidentified customer is
        # 2499 at the time these tests were written. The POS config is
        # set to this value here, update if the legal limit changes.
        cls.main_pos_config.write({
            'l10n_gt_final_consumer_limit': 2499,
        })

        cls.company.write({
            'l10n_gt_edi_phrase_ids': [
                Command.set([
                    cls.env.ref('l10n_gt_edi.l10n_gt_edi_phrase_type_1_code_1').id,
                ]),
            ],
        })

        cls.consumidor_final = cls.env.ref('l10n_gt_edi.final_consumer')

        # Rename to avoid confusion with similarly named customers across different LATAM localizations
        cls.consumidor_final.name = 'Guatemala Consumidor Final'

        cls.foreign_unidentified_customer = cls.env['res.partner'].create({
            'name': 'Foreign Unidentified Customer',
            'country_id': cls.env.ref('base.us').id,
        })

        # GT customer without a tax identifier (no NIT, no CUI)
        cls.gt_unidentified_customer = cls.env['res.partner'].create({
            'name': 'GT Unidentified Customer',
            'country_id': cls.env.ref('base.gt').id,
        })

        # GT customer with valid NIT (stored as VAT)
        cls.gt_identified_customer = cls.env['res.partner'].create({
            'name': 'GT Identified Customer',
            'vat': '9502297',
            'country_id': cls.env.ref('base.gt').id,
        })

        cls.foreign_identified_customer = cls.env['res.partner'].create({
            'name': 'Foreign Identified Customer',
            'vat': '12345678',
            'country_id': cls.env.ref('base.us').id,
        })

        cls.test_product = cls.env['product.template'].create({
            'name': 'Test Product',
            'available_in_pos': True,
            'list_price': 1250,
        })

    def test_gt_pos_order_customer_threshold_limit_through_frontend(self):
        self.main_pos_config.open_ui()
        self.start_pos_tour('test_gt_pos_unidentified_customer_threshold_limit')

    def test_gt_pos_order_customer_threshold_limit_through_form_view(self):
        # ==============================================
        # Unidentified Customers should not be allowed
        # ==============================================
        for partner in (
            self.consumidor_final,
            self.foreign_unidentified_customer,
            self.gt_unidentified_customer,
        ):
            with self.assertRaises(UserError) as error:
                self.create_backend_pos_order({
                    'order_data': {
                        'partner_id': partner.id,
                        'to_invoice': True,
                    },
                    'line_data': [
                        {'product_id': self.test_product.product_variant_id.id, 'qty': 2},
                    ],
                    'payment_data': [
                        {'payment_method_id': self.cash_payment_method.id, 'amount': 2500},
                    ],
                })

            error_message = error.exception.args[0]
            self.assertIn(
                (
                    "This order exceeds the maximum amount allowed for an unidentified customer.\n"
                    f"Maximum allowed amount: {formatLang(self.env, 2499, currency_obj=self.main_pos_config.currency_id)}\n"
                    "Please select a customer with a valid Identification Type and Number before continuing."
                ),
                error_message,
            )

        # ========================================
        # Identified Customers should be allowed
        # ========================================
        for partner in (
            self.gt_identified_customer,
            self.foreign_identified_customer,
        ):
            self.create_backend_pos_order({
                'order_data': {
                    'partner_id': partner.id,
                    'to_invoice': True,
                },
                'line_data': [
                    {'product_id': self.test_product.product_variant_id.id, 'qty': 2},
                ],
                'payment_data': [
                    {'payment_method_id': self.cash_payment_method.id, 'amount': 2500},
                ],
            })

    def test_gt_pos_order_customer_threshold_limit_through_consolidated_billing_wizard(self):
        partners = [
            # Unidentified Customers
            (self.consumidor_final, True),
            (self.foreign_unidentified_customer, True),
            (self.gt_unidentified_customer, True),

            # Identified Customers
            (self.foreign_identified_customer, False),
            (self.gt_identified_customer, False),
        ]

        for partner, expect_error in partners:
            order1, _ = self.create_backend_pos_order({
                'order_data': {
                    'partner_id': partner.id,
                    'to_invoice': False,
                },
                'line_data': [
                    {'product_id': self.test_product.product_variant_id.id, 'qty': 1},
                ],
                'payment_data': [
                    {'payment_method_id': self.cash_payment_method.id, 'amount': 1250},
                ],
            })
            order2, _ = self.create_backend_pos_order({
                'order_data': {
                    'partner_id': partner.id,
                    'to_invoice': False,
                },
                'line_data': [
                    {'product_id': self.test_product.product_variant_id.id, 'qty': 1},
                ],
                'payment_data': [
                    {'payment_method_id': self.cash_payment_method.id, 'amount': 1250},
                ],
            })

            wizard = self.env['pos.make.invoice'].with_context({
                'active_ids': [order1.id, order2.id],
            }).create({'consolidated_billing': True})

            if expect_error:
                with self.assertRaises(UserError) as error:
                    wizard.action_create_invoices()

                error_message = error.exception.args[0]
                self.assertIn(
                    (
                        "This order exceeds the maximum amount allowed for an unidentified customer.\n"
                        f"Maximum allowed amount: {formatLang(self.env, 2499, currency_obj=self.main_pos_config.currency_id)}\n"
                        "Please select a customer with a valid Identification Type and Number before continuing."
                    ),
                    error_message,
                )
                self.assertIn(order1.name, error_message)
                self.assertIn(order2.name, error_message)
            else:
                wizard.action_create_invoices()

    def test_gt_pos_refund_requires_linked_order_invoiced(self):
        with self.assertRaises(UserError) as error:
            _, refund = self.create_backend_pos_order({
                'order_data': {
                    'partner_id': self.consumidor_final.id,
                    'to_invoice': False,
                },
                'line_data': [
                    {'product_id': self.test_product.product_variant_id.id, 'qty': 1},
                ],
                'payment_data': [
                    {'payment_method_id': self.cash_payment_method.id, 'amount': 1250},
                ],
                'refund_data': [
                    {'payment_method_id': self.cash_payment_method.id, 'amount': -1250},
                ],
            })
            refund.action_pos_order_invoice()

        error_message = error.exception.args[0]
        self.assertIn(
            (
                "The order linked to this refund has not been electronically invoiced. "
                "Please make sure the original order has an electronic invoice before "
                "trying to create an electronic credit note for this refund."
            ),
            error_message,
        )

    def test_gt_pos_order_and_refund_fill_gt_phrases_from_company(self):
        order, refund = self.create_backend_pos_order({
            'order_data': {
                'partner_id': self.gt_identified_customer.id,
                'to_invoice': True,
            },
            'line_data': [
                {'product_id': self.test_product.product_variant_id.id, 'qty': 2},
            ],
            'payment_data': [
                {'payment_method_id': self.cash_payment_method.id, 'amount': 2500},
            ],
            'refund_data': [
                {'payment_method_id': self.cash_payment_method.id, 'amount': -2500},
            ],
        })

        self.assertEqual(order.account_move.l10n_gt_edi_phrase_ids.ids, self.company.l10n_gt_edi_phrase_ids.ids)
        self.assertEqual(refund.account_move.l10n_gt_edi_phrase_ids.ids, self.company.l10n_gt_edi_phrase_ids.ids)
