# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import tagged
from odoo.exceptions import ValidationError
from odoo.addons.sale.tests.common import TestTaxCommonSale
from odoo.addons.l10n_br_avatax.tests.test_br_avatax import TestAvalaraBrCommon
from .mocked_so_response import generate_response


@tagged("post_install_l10n", "-at_install", "post_install")
class TestSaleAvalaraBr(TestTaxCommonSale, TestAvalaraBrCommon):
    _test_user_groups = None  # FIXME list needed groups

    def assertOrder(self, order, mocked_response=None):
        if mocked_response:
            amount_total = 95.00
            amount_tax = 11.4 + 5.21
            self.assertRecordValues(order, [{
                'amount_total': amount_total,
                'amount_untaxed': amount_total - amount_tax,
                'amount_tax': amount_tax,
            }])

            self.assert_sale_order_tax_totals_summary(order, {
                'base_amount_currency': order.amount_untaxed,
                'tax_amount_currency': order.amount_tax,
                'total_amount_currency': order.amount_total,
            }, soft_checking=True)

            for avatax_line in mocked_response['lines']:
                so_line = order.order_line.filtered(lambda l: l.id == avatax_line['lineCode'])
                total_tax_amount = sum(detail['tax'] for detail in avatax_line['taxDetails'] if detail['taxImpact']['impactOnNetAmount'] != 'Informative')
                self.assertRecordValues(so_line, [{
                    'price_subtotal': avatax_line['lineNetFigure'],
                    'price_total': avatax_line['lineNetFigure'] + total_tax_amount,
                }])
                # no digits= specified on this Float field, so assertRecordValues would do an exact comparison of floats
                self.assertAlmostEqual(so_line.price_tax, total_tax_amount)
        else:
            for line in order.order_line:
                product_name = line.product_id.display_name
                self.assertGreater(len(line.tax_ids), 0, "Line with %s did not get any taxes set." % product_name)

            self.assertGreater(order.amount_tax, 0.0, "Invoice has a tax_amount of 0.0.")

    def _create_l10n_br_avatax_sale_order(self, make_response=True, **values):
        products = (
            self.product_user,
            self.product_accounting,
            self.product_expenses,
            self.product_invoicing,
        )

        order_values = {
            'partner_id': self.partner.id,
            'fiscal_position_id': self.fp_avatax.id,
            'date_order': '2021-01-01',
            'order_line': [
                self._prepare_order_line(
                    product_id=product.id,
                    price_unit=product.list_price,
                    tax_ids=None,
                ) for product in products
            ],
            **values
        }

        order = self._create_sale_order(
            confirm=False,
            **order_values,
        )
        mocked_response = None
        if make_response:
            mocked_response = generate_response(order.order_line)

        return order, mocked_response

    def _create_l10n_br_avatax_sale_order_with_operation_types(self, operation_types=False, **values):
        products = (
            self.product_user,
            self.product_accounting,
            self.product_expenses,
            self.product_invoicing,
        )
        operation_types = operation_types or (
            self.env.ref('l10n_br_avatax.operation_type_1'),
            self.env.ref('l10n_br_avatax.operation_type_2'),
            self.env.ref('l10n_br_avatax.operation_type_3'),
            self.env.ref('l10n_br_avatax.operation_type_60'),
        )
        order_values = {
            'partner_id': self.partner.id,
            'fiscal_position_id': self.fp_avatax.id,
            'date_order': '2021-01-01',
            'order_line': [
                self._prepare_order_line(
                    product_id=product.id,
                    price_unit=product.list_price,
                    tax_ids=None,
                    l10n_br_goods_operation_type_id=operation_type and operation_type.id,
                )
                for product, operation_type in zip(products, operation_types)
            ],
            **values,
        }

        order = self._create_sale_order(
            confirm=False,
            **order_values,
        )

        return order

    def test_01_sale_order_br(self):
        order, mocked_response = self._create_l10n_br_avatax_sale_order()
        order.currency_id = self.env.ref('base.BRL')
        with self._capture_request_br(return_value=mocked_response):
            order.button_external_tax_calculation()
        self.assertOrder(order, mocked_response=mocked_response)

    def test_02_sale_order_br_integration(self):
        order, _ = self._create_l10n_br_avatax_sale_order()
        order.currency_id = self.env.ref('base.BRL')
        with self._skip_no_credentials():
            order.button_external_tax_calculation()
            self.assertOrder(order, mocked_response=False)

    def test_03_sale_order_unique_operation_type(self):
        """Tax calculation with unique operation types on each line."""
        order = self._create_l10n_br_avatax_sale_order_with_operation_types()

        payload = order._prepare_l10n_br_avatax_document_service_call(order._get_l10n_br_avatax_service_params())
        operationTypes = [line['operationType'] for line in payload['lines']]
        expected_operation_types = ['standardSales', 'complementary', 'amountComplementary', 'salesReturn']
        self.assertEqual(operationTypes, expected_operation_types, 'The expected operation types are not properly set. It should be unique per line.')

    def test_04_sale_order_override_operation_type(self):
        """Tax calculation with operation types set only on a single line."""
        operation_types = (
            False,
            False,
            self.env.ref('l10n_br_avatax.operation_type_2'),
            False,
        )
        order = self._create_l10n_br_avatax_sale_order_with_operation_types(operation_types=operation_types)

        payload = order._prepare_l10n_br_avatax_document_service_call(order._get_l10n_br_avatax_service_params())
        operationTypes = [line['operationType'] for line in payload['lines']]
        expected_operation_types = ['standardSales', 'standardSales', 'complementary', 'standardSales']
        self.assertEqual(operationTypes, expected_operation_types, 'The expected operation types are not properly set.')

    def test_05_sale_order_with_order_number_and_item_number(self):
        """ Tax calculation with order number and item number on sale order. """
        order = self._create_sale_order(
            partner_id=self.partner.id,
            fiscal_position_id=self.fp_avatax.id,
            date_order='2021-01-01',
            client_order_ref='5678',
            order_line=[
                self._prepare_order_line(
                    product_id=self.product_user.id,
                    price_unit=self.product_user.list_price,
                    tax_ids=None,
                    l10n_br_item_number='1234',
                )
            ],
            confirm=False,
        )

        payload = order._prepare_l10n_br_avatax_document_service_call(order._get_l10n_br_avatax_service_params())
        actual_line = payload['lines'][0]

        self.assertEqual(actual_line['orderNumber'], '5678')
        self.assertEqual(actual_line['orderItemNumber'], '1234')

    def test_06_sale_order_with_order_number_and_item_number_none(self):
        """ Tax calculation with order number and item number on sale order set to None. """
        order = self._create_sale_order(
            partner_id=self.partner.id,
            fiscal_position_id=self.fp_avatax.id,
            date_order='2021-01-01',
            order_line=[
                self._prepare_order_line(
                    product_id=self.product_user.id,
                    price_unit=self.product_user.list_price,
                    tax_ids=None,
                )
            ],
            confirm=False,
        )

        payload = order._prepare_l10n_br_avatax_document_service_call(order._get_l10n_br_avatax_service_params())
        actual_line = payload['lines'][0]

        self.assertTrue('orderNumber' not in actual_line)
        self.assertTrue('orderItemNumber' not in actual_line)

    def test_sale_order_redistribute_amounts_after_api_call(self):
        """Test that _process_external_taxes correctly distributes tax values back to all invoice lines."""
        order = self._create_sale_order(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            order_line=[
                self._prepare_order_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_order_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_order_line(product_id=self.product_user_discount, price_unit=-30.0),
            ],
            confirm=False,
        )

        service_params = order._get_l10n_br_avatax_service_params()
        line_data_list = service_params['line_data']
        self.assertEqual(len(line_data_list), 2)  # No discount line

        base_lines = [line_data['base_line'] for line_data in line_data_list]

        tax_group_values = {'name': 'Avatax Brazil', 'company_id': order.company_id.id}
        icms = {'name': 'icms', 'l10n_br_avatax_code': 'icms'}
        pis = {'name': 'pis', 'l10n_br_avatax_code': 'pis'}
        base_line_with_tax_values = [
            (base_lines[0], [
                (tax_group_values, icms, {'base_amount_currency': 80.0, 'tax_amount_currency': 8.0}),
                (tax_group_values, pis, {'base_amount_currency': 80.0, 'tax_amount_currency': 1.6}),
            ]),
            (base_lines[1], [
                # Amounts should be correctly distributed even if the taxes have a different order
                (tax_group_values, pis, {'base_amount_currency': 40.0, 'tax_amount_currency': 0.8}),
                (tax_group_values, icms, {'base_amount_currency': 40.0, 'tax_amount_currency': 4.0}),
            ]),
        ]

        result = order._process_external_taxes(
            order.company_id,
            base_line_with_tax_values,
            'l10n_br_avatax_code',
        )

        self.assertEqual(len(result), 3)  # Discount line should be brought back

        icms_id = str(self.env['account.tax'].search([('l10n_br_avatax_code', '=', 'icms')], limit=1).id)
        pis_id = str(self.env['account.tax'].search([('l10n_br_avatax_code', '=', 'pis')], limit=1).id)

        discount_record = order.order_line.filtered(lambda l: l.price_unit < 0)
        discount_amounts = result[discount_record]['manual_tax_amounts']
        self.assertAlmostEqual(discount_amounts[icms_id]['tax_amount_currency'], -20 / 80 * 8 - 10 / 40 * 4)
        self.assertAlmostEqual(discount_amounts[pis_id]['tax_amount_currency'], -20 / 80 * 1.6 - 10 / 40 * 0.8)

        # Totals should stay the same: ICMS = 12.0, PIS = 2.4
        total_icms = sum(result[r]['manual_tax_amounts'][icms_id]['tax_amount_currency'] for r in result)
        total_pis = sum(result[r]['manual_tax_amounts'][pis_id]['tax_amount_currency'] for r in result)
        self.assertAlmostEqual(total_icms, 12.0)
        self.assertAlmostEqual(total_pis, 2.4)

    def test_sale_order_global_discount_redistribution(self):
        """Check if order with discount line is redistributed correctly after Avatax call."""
        order = self._create_sale_order(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            order_line=[
                self._prepare_order_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_order_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_order_line(product_id=self.product_user_discount, price_unit=-30.0),
            ],
            confirm=False,
        )

        # Discount is absorbed by other lines: -20 to line 1, -10 to line 2
        # Mock Avatax response with 12% ICMS (tax included) for these lines
        response = {
            'lines': [
                {
                    'lineCode': order.order_line[0].id,
                    'lineNetFigure': 80.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 9.6,
                        'rate': 12,
                        'subtotalTaxable': 80.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
                {
                    'lineCode': order.order_line[1].id,
                    'lineNetFigure': 40.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 4.8,
                        'rate': 12,
                        'subtotalTaxable': 40.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
            ],
        }

        # Do it twice to check if it's idempotent
        request_args = []
        for _ in range(2):
            with self._capture_request_br(return_value=response) as mock:
                order.button_external_tax_calculation()
                request_args.append(mock.call_args.args[2])

            # Tax totals: 9.6 + 4.8 = 14.4, redistributed to 3 lines
            self.assertRecordValues(order, [{
                'amount_untaxed': 120.0,
                'amount_tax': 14.4,
                'amount_total': 134.4,
            }])

            self.assertRecordValues(order.order_line, [
                {'price_subtotal': 100, 'price_total': 112.0},  # line 100: 100/80 of (base=80, tax=9.6)
                {'price_subtotal': 50, 'price_total': 56.0},  # line 50: 50/40 of (base=40, tax=4.8)
                {'price_subtotal': -30, 'price_total': -33.6},    # discount: -20/80 and -10/40 of both amounts
            ])

        self.assertEqual(request_args[0], request_args[1], "Request to Avalara should be the same on both calls")

    def test_sale_order_tax_recalculation_after_removing_discount(self):
        """Test that tax calculation works after removing the discount line."""
        order = self._create_sale_order(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            order_line=[
                self._prepare_order_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_order_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_order_line(product_id=self.product_user_discount, price_unit=-30.0),
            ],
            confirm=False
        )

        # Response for 2 distributed lines
        response_with_discount = {
            'lines': [
                {
                    'lineCode': order.order_line[0].id,
                    'lineNetFigure': 80.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 9.6,
                        'rate': 12,
                        'subtotalTaxable': 80.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
                {
                    'lineCode': order.order_line[1].id,
                    'lineNetFigure': 40.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 4.8,
                        'rate': 12,
                        'subtotalTaxable': 40.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
            ],
        }

        with self._capture_request_br(return_value=response_with_discount):
            order.button_external_tax_calculation()

        self.assertEqual(order.amount_tax, 14.4)

        # Remove the discount line
        order.order_line.filtered(lambda l: l.price_unit < 0).unlink()

        # Response for 2 lines without discount
        response_without_discount = {
            'lines': [
                {
                    'lineCode': order.order_line[0].id,
                    'lineNetFigure': 100.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 12.0,
                        'rate': 12,
                        'subtotalTaxable': 100.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
                {
                    'lineCode': order.order_line[1].id,
                    'lineNetFigure': 50.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 6.0,
                        'rate': 12,
                        'subtotalTaxable': 50.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
            ],
        }

        with self._capture_request_br(return_value=response_without_discount):
            order.button_external_tax_calculation()

        self.assertRecordValues(order, [{
            'amount_untaxed': 150.0,
            'amount_tax': 18.0,
            'amount_total': 168.0,
        }])

        self.assertRecordValues(order.order_line, [
            {'price_subtotal': 100.0, 'price_total': 112.0},
            {'price_subtotal': 50.0, 'price_total': 56.0},
        ])

    def test_sale_order_global_discount_fixed_redistribute(self):
        """This test checks that when we apply a discount after calculating taxes, this is created without taxes so we have the discount amount
        independent of the taxes calculation.
        """
        order = self._create_sale_order(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            order_line=[
                self._prepare_order_line(product_id=self.product_user, price_unit=1570.0),
                self._prepare_order_line(product_id=self.product_user, price_unit=250.91),
                self._prepare_order_line(product_id=self.product_user, price_unit=555),
            ],
            confirm=False
        )  # Total order amount: 2375.91

        service_params = order._get_l10n_br_avatax_service_params()
        base_lines = [line_data['base_line'] for line_data in service_params['line_data']]

        tax_group_values = {'name': 'Avatax Brazil', 'company_id': order.company_id.id}
        icms = {'name': 'icms', 'amount': 1, 'l10n_br_avatax_code': 'icms', 'price_include_override': 'tax_included', 'amount_type': 'percent'}
        cofins = {'name': 'cofins', 'amount': 1, 'l10n_br_avatax_code': 'cofins', 'price_include_override': 'tax_included', 'amount_type': 'percent'}
        pis = {'name': 'pis', 'amount': 1, 'l10n_br_avatax_code': 'pis', 'price_include_override': 'tax_included', 'amount_type': 'percent'}
        ipi = {'name': 'ipi', 'amount': 1, 'l10n_br_avatax_code': 'ipi', 'price_include_override': 'tax_excluded', 'amount_type': 'percent'}

        base_line_with_tax_values = [
            (base_lines[0], [
                (tax_group_values, icms, {'base_amount_currency': 1381.6, 'tax_amount_currency': 188.4}),
            ]),
            (base_lines[1], [
                (tax_group_values, icms, {'base_amount_currency': 220.8, 'tax_amount_currency': 30.11}),
            ]),
            (base_lines[2], [
                (tax_group_values, cofins, {'base_amount_currency': 470.58, 'tax_amount_currency': 14.65}),
                (tax_group_values, icms, {'base_amount_currency': 470.58, 'tax_amount_currency': 66.6}),
                (tax_group_values, pis, {'base_amount_currency': 470.58, 'tax_amount_currency': 3.17}),
                (tax_group_values, ipi, {'base_amount_currency': 470.58, 'tax_amount_currency': 36.08}),
            ])
        ]

        _result = order._set_external_taxes(order._process_external_taxes(
            order.company_id,
            base_line_with_tax_values,
            'l10n_br_avatax_code',
        ))

        self.env['sale.order.discount'].create({
            'sale_order_id': order.id,
            'discount_amount': 250,
            'discount_type': 'amount',
        }).action_apply_discount()

        # discount lines should've been created without taxes
        self.assertRecordValues(order.order_line[-1], [
            {'price_unit': -250, 'tax_ids': [], 'product_uom_qty': 1, 'price_subtotal': -250, 'price_total': -250},
        ])
        self.assertTrue(not order.order_line.tax_ids, "Taxes should've been removed")
        self.assertEqual(order.amount_total, 2125.91)

        service_params_with_discount = order._get_l10n_br_avatax_service_params()
        base_lines_with_discount = [line_data['base_line'] for line_data in service_params_with_discount['line_data']]

        # Recompute the taxes with the new discounts
        base_line_with_discount_with_tax_values = [
            (base_lines_with_discount[0], [
                (tax_group_values, icms, {'base_amount_currency': 1236.22, 'tax_amount_currency': 168.58}),
                # Disc lines: 165.20 approx
            ]),
            (base_lines_with_discount[1], [
                (tax_group_values, icms, {'base_amount_currency': 197.57, 'tax_amount_currency': 26.94}),
            ]),  # Disc lines: 26.40 approx
            (base_lines_with_discount[2], [
                (tax_group_values, cofins, {'base_amount_currency': 421.06, 'tax_amount_currency': 13.11}),
                (tax_group_values, icms, {'base_amount_currency': 421.06, 'tax_amount_currency': 59.59}),
                (tax_group_values, pis, {'base_amount_currency': 421.06, 'tax_amount_currency': 2.84}),
                (tax_group_values, ipi, {'base_amount_currency': 421.06, 'tax_amount_currency': 32.28}),
            ])  # Disc lines: 58.40
        ]

        _result2 = order._set_external_taxes(order._process_external_taxes(
            order.company_id,
            base_line_with_discount_with_tax_values,
            'l10n_br_avatax_code',
        ))

        self.assertRecordValues(order.order_line, [
            # Amounts should be the same as we previously did since we have redistributed the tax and base amounts
            {'price_unit': 1570.00, 'price_subtotal': 1381.60, 'price_total': 1570.00},  # 1570 / 1404.80 (base=1236.22, tax=168.58)
            {'price_unit': 250.91, 'price_subtotal': 220.80, 'price_total': 250.91},  # 250.91/224.51 (base=197.57, tax=26.94)
            {'price_unit': 555.00, 'price_subtotal': 470.58, 'price_total': 591.08},  # 555/496.6 (base=421.06, tax=[13.11, 59.59, 2.84, 32.28])
            # Discount line
            {'price_unit': -250, 'price_subtotal': -218.13, 'price_total': -253.80},  # 165.20/1404.80 and 26.40/224.51 and 58.40/496.6 for each base and taxes
        ])

    def test_sale_order_global_discount_percentage_redistribute(self):
        """Same as previous test but with global discount as percentage
        """
        order = self._create_sale_order(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            order_line=[
                self._prepare_order_line(product_id=self.product_user, price_unit=1570.0),
                self._prepare_order_line(product_id=self.product_user, price_unit=250.91),
                self._prepare_order_line(product_id=self.product_user, price_unit=555),
            ],
            confirm=False
        )  # Total order amount: 2375.91

        service_params = order._get_l10n_br_avatax_service_params()
        base_lines = [line_data['base_line'] for line_data in service_params['line_data']]

        tax_group_values = {'name': 'Avatax Brazil', 'company_id': order.company_id.id}
        icms = {'name': 'icms', 'amount': 1, 'l10n_br_avatax_code': 'icms', 'price_include_override': 'tax_included', 'amount_type': 'percent'}
        cofins = {'name': 'cofins', 'amount': 1, 'l10n_br_avatax_code': 'cofins', 'price_include_override': 'tax_included', 'amount_type': 'percent'}
        pis = {'name': 'pis', 'amount': 1, 'l10n_br_avatax_code': 'pis', 'price_include_override': 'tax_included', 'amount_type': 'percent'}
        ipi = {'name': 'ipi', 'amount': 1, 'l10n_br_avatax_code': 'ipi', 'price_include_override': 'tax_excluded', 'amount_type': 'percent'}

        base_line_with_tax_values = [
            (base_lines[0], [
                (tax_group_values, icms, {'base_amount_currency': 1381.6, 'tax_amount_currency': 188.4}),
            ]),  # 1570
            (base_lines[1], [
                (tax_group_values, icms, {'base_amount_currency': 220.8, 'tax_amount_currency': 30.11}),
            ]),  # 250.91
            (base_lines[2], [
                (tax_group_values, cofins, {'base_amount_currency': 470.58, 'tax_amount_currency': 14.65}),
                (tax_group_values, icms, {'base_amount_currency': 470.58, 'tax_amount_currency': 66.6}),
                (tax_group_values, pis, {'base_amount_currency': 470.58, 'tax_amount_currency': 3.17}),
                (tax_group_values, ipi, {'base_amount_currency': 470.58, 'tax_amount_currency': 36.08}),
            ])  # 591.08
        ]

        _result = order._set_external_taxes(order._process_external_taxes(
            order.company_id,
            base_line_with_tax_values,
            'l10n_br_avatax_code',
        ))

        self.env['sale.order.discount'].create({
            'sale_order_id': order.id,
            'discount_percentage': 0.1,  # (1570 + 250.91 + 555) * .10 = 237.59
            'discount_type': 'so_discount',
        }).action_apply_discount()

        # discount lines should be created without taxes
        self.assertRecordValues(order.order_line[-1], [
            {'price_unit': -237.591, 'tax_ids': [], 'product_uom_qty': 1, 'price_subtotal': -237.59, 'price_total': -237.59},
        ])
        self.assertTrue(not order.order_line.tax_ids, "Taxes should've been removed")
        self.assertEqual(order.amount_total, 2138.32)

        service_params_with_discount = order._get_l10n_br_avatax_service_params()
        base_lines_with_discount = [line_data['base_line'] for line_data in service_params_with_discount['line_data']]

        # Recompute the taxes with the new discounts
        base_line_with_discount_with_tax_values = [
            (base_lines_with_discount[0], [
                (tax_group_values, icms, {'base_amount_currency': 1243.44, 'tax_amount_currency': 169.56}),
                # Disc lines: 157 approx
            ]),
            (base_lines_with_discount[1], [
                (tax_group_values, icms, {'base_amount_currency': 198.72, 'tax_amount_currency': 27.1}),
            ]),  # Disc lines: 25.09 approx
            (base_lines_with_discount[2], [
                (tax_group_values, cofins, {'base_amount_currency': 423.51, 'tax_amount_currency': 13.19}),
                (tax_group_values, icms, {'base_amount_currency': 423.51, 'tax_amount_currency': 59.94}),
                (tax_group_values, pis, {'base_amount_currency': 423.51, 'tax_amount_currency': 2.86}),
                (tax_group_values, ipi, {'base_amount_currency': 423.51, 'tax_amount_currency': 32.47}),
            ])  # Disc lines: 55.50
        ]

        _result2 = order._set_external_taxes(order._process_external_taxes(
            order.company_id,
            base_line_with_discount_with_tax_values,
            'l10n_br_avatax_code',
        ))

        self.assertRecordValues(order.order_line, [
            # Amounts should be the same as we previously did since we have redistributed the tax and base amounts
            {'price_unit': 1570.00, 'price_subtotal': 1381.60, 'price_total': 1570.00},  # 1570 / 1413.0 (base=1236.22, tax=168.58)
            {'price_unit': 250.91, 'price_subtotal': 220.80, 'price_total': 250.91},  # 250.91 / 225.82 (base=198.72, tax=27.1)
            {'price_unit': 555.00, 'price_subtotal': 470.57, 'price_total': 591.09},  # 555 / 499.5 (base=423.51, 13.19)
            # Discount lines
            {'price_unit': -237.591, 'price_subtotal': -207.30, 'price_total': -241.21},  # 157/1413 and 25.09/225.82 and 55.5/499.5 for each base and taxes
        ])

    def test_sale_order_fail_distribute_negative_amount_lines(self):
        order = self._create_sale_order(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            order_line=[
                self._prepare_order_line(
                    product_id=self.product_user,
                    price_unit=50.0,
                ),
                self._prepare_order_line(
                    product_id=self.product_user_discount,
                    price_unit=-100.0
                ),
            ],
            confirm=False,
        )

        with self.assertRaisesRegex(ValidationError, "The document amount must be positive."):
            order._get_external_taxes()
