# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPurchaseRequisitionContractControl(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env['purchase.order'])
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')
        cls.vendor = cls.env['res.partner'].create({'name': 'Contract Vendor'})

        Product = cls.env['product.product']
        cls.product_a = Product.create({
            'name': 'Contract Product A',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'standard_price': 10.0,
        })
        cls.product_b = Product.create({
            'name': 'Contract Product B',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'standard_price': 20.0,
        })
        cls.product_free = Product.create({
            'name': 'Product Outside Contract',
            'type': 'consu',
            'uom_id': cls.uom_unit.id,
            'standard_price': 5.0,
        })

        cls.blanket_order = cls._create_blanket_order([
            (cls.product_a, 100.0, 15.0),
            (cls.product_b, 50.0, 25.0),
        ])

    @classmethod
    def _create_blanket_order(cls, lines, date_start=None, date_end=None, company=None):
        company = company or cls.company
        requisition = cls.env['purchase.requisition'].with_company(company).create({
            'requisition_type': 'blanket_order',
            'vendor_id': cls.vendor.id,
            'company_id': company.id,
            'date_start': date_start or cls.today - timedelta(days=30),
            'date_end': date_end or cls.today + timedelta(days=30),
            'line_ids': [
                Command.create({'product_id': product.id, 'product_qty': qty, 'price_unit': price})
                for product, qty, price in lines
            ],
        })
        requisition.action_confirm()
        return requisition

    def _create_order(self, requisition, lines, user=None):
        """Create a purchase order through the ORM (no onchange), as an RPC call would.

        :param lines: list of tuples (product, quantity) or (product, quantity, uom)
        """
        PurchaseOrder = self.env['purchase.order']
        if user:
            PurchaseOrder = PurchaseOrder.with_user(user)
        return PurchaseOrder.with_company(requisition.company_id).create({
            'partner_id': requisition.vendor_id.id,
            'requisition_id': requisition.id,
            'company_id': requisition.company_id.id,
            'order_line': [
                Command.create({
                    'product_id': product.id,
                    'product_qty': qty,
                    'product_uom_id': (uom[0] if uom else product.uom_id).id,
                })
                for product, qty, *uom in lines
            ],
        })

    def _agreement_line(self, requisition, product):
        return requisition.line_ids.filtered(lambda line: line.product_id == product)

    # ------------------------------------------------------------
    # Test 1 - valid agreement
    # ------------------------------------------------------------

    def test_01_valid_blanket_order(self):
        self.assertEqual(self.blanket_order.state, 'confirmed')
        self.assertEqual(self.blanket_order.requisition_type, 'blanket_order')
        self.assertGreaterEqual(self.blanket_order.date_end, self.today)
        self.assertEqual(len(self.blanket_order.line_ids), 2)

    # ------------------------------------------------------------
    # Tests 2 & 3 - agreement selection without importing lines
    # ------------------------------------------------------------

    def test_02_select_agreement_does_not_import_lines(self):
        po_form = Form(self.env['purchase.order'])
        po_form.partner_id = self.vendor
        po_form.requisition_id = self.blanket_order
        self.assertEqual(len(po_form.order_line), 0, "Agreement lines must not be imported.")
        purchase_order = po_form.save()

        self.assertEqual(purchase_order.requisition_id, self.blanket_order)
        self.assertEqual(purchase_order.partner_id, self.vendor)
        self.assertIn(self.blanket_order.name, purchase_order.origin)
        self.assertFalse(purchase_order.order_line)

    def test_03_new_quotation_from_agreement_does_not_import_lines(self):
        # Reproduces the "New Quotation" button of the agreement form.
        po_form = Form(self.env['purchase.order'].with_context(default_requisition_id=self.blanket_order.id))
        self.assertEqual(po_form.partner_id, self.vendor)
        self.assertEqual(len(po_form.order_line), 0)
        purchase_order = po_form.save()
        self.assertEqual(purchase_order.requisition_id, self.blanket_order)
        self.assertFalse(purchase_order.order_line)

    def test_04_existing_lines_are_kept_when_selecting_agreement(self):
        po_form = Form(self.env['purchase.order'])
        po_form.partner_id = self.vendor
        with po_form.order_line.new() as line:
            line.product_id = self.product_free
            line.product_qty = 3.0
        po_form.requisition_id = self.blanket_order
        purchase_order = po_form.save()

        self.assertEqual(purchase_order.order_line.product_id, self.product_free)
        self.assertEqual(purchase_order.order_line.product_qty, 3.0)

    # ------------------------------------------------------------
    # Tests 4 & 5 - quantity validation
    # ------------------------------------------------------------

    def test_05_valid_quantity_is_accepted(self):
        po_form = Form(self.env['purchase.order'].with_context(default_requisition_id=self.blanket_order.id))
        with po_form.order_line.new() as line:
            line.product_id = self.product_a
            line.product_qty = 100.0
        # Products outside the agreement are not restricted, as in standard Odoo.
        with po_form.order_line.new() as line:
            line.product_id = self.product_free
            line.product_qty = 1000.0
        purchase_order = po_form.save()

        line_a = purchase_order.order_line.filtered(lambda line: line.product_id == self.product_a)
        self.assertEqual(line_a.price_unit, 15.0, "The native agreement price must still apply.")

        purchase_order.button_confirm()
        self.assertEqual(purchase_order.state, 'purchase')
        self.assertEqual(self._agreement_line(self.blanket_order, self.product_a).qty_ordered, 100.0)

    def test_06_exceeding_quantity_is_rejected(self):
        po_form = Form(self.env['purchase.order'].with_context(default_requisition_id=self.blanket_order.id))
        with self.assertLogs('odoo.tests.form.onchange', level='WARNING') as captured:
            with po_form.order_line.new() as line:
                line.product_id = self.product_a
                line.product_qty = 101.0
        self.assertIn(self.product_a.display_name, "\n".join(captured.output))

        with self.assertRaises(ValidationError):
            po_form.save()
        with self.assertRaises(ValidationError):
            self._create_order(self.blanket_order, [(self.product_a, 101.0)])

    def test_07_quantities_are_compared_in_product_unit_of_measure(self):
        agreement = self._create_blanket_order([(self.product_a, 24.0, 15.0)])
        purchase_order = self._create_order(agreement, [(self.product_a, 2.0, self.uom_dozen)])
        purchase_order.button_confirm()
        self.assertEqual(purchase_order.state, 'purchase')

        with self.assertRaises(ValidationError):
            self._create_order(agreement, [(self.product_a, 1.0)])

    # ------------------------------------------------------------
    # Tests 6 & 7 - expired agreement
    # ------------------------------------------------------------

    def test_08_expired_agreement_is_rejected(self):
        expired = self._create_blanket_order(
            [(self.product_a, 10.0, 15.0)],
            date_start=self.today - timedelta(days=60),
            date_end=self.today - timedelta(days=1),
        )
        self.assertEqual(expired.state, 'confirmed')

        po_form = Form(self.env['purchase.order'])
        po_form.partner_id = self.vendor
        with self.assertLogs('odoo.tests.form.onchange', level='WARNING') as captured:
            po_form.requisition_id = expired
        self.assertIn(expired.name, "\n".join(captured.output))
        with self.assertRaises(ValidationError):
            po_form.save()

        with self.assertRaises(ValidationError):
            self._create_order(expired, [(self.product_a, 1.0)])

        purchase_order = self.env['purchase.order'].create({'partner_id': self.vendor.id})
        with self.assertRaises(ValidationError):
            purchase_order.write({'requisition_id': expired.id})

    def test_09_agreement_valid_until_its_end_date_included(self):
        agreement = self._create_blanket_order([(self.product_a, 10.0, 15.0)], date_end=self.today)
        purchase_order = self._create_order(agreement, [(self.product_a, 10.0)])
        purchase_order.button_confirm()
        self.assertEqual(purchase_order.state, 'purchase')

    # ------------------------------------------------------------
    # Test 8 - backend bypass
    # ------------------------------------------------------------

    def test_10_expiration_cannot_be_bypassed_through_backend_methods(self):
        purchase_order = self._create_order(self.blanket_order, [(self.product_a, 10.0)])
        # The agreement expires after the RFQ was created.
        self.blanket_order.date_end = self.today - timedelta(days=1)

        with self.assertRaises(ValidationError):
            purchase_order.button_confirm()
        with self.assertRaises(ValidationError):
            purchase_order.button_approve()
        with self.assertRaises(ValidationError):
            purchase_order.write({'state': 'to approve'})
        with self.assertRaises(ValidationError):
            purchase_order.write({'state': 'purchase'})

        purchase_order.invalidate_recordset(['state'])
        self.assertEqual(purchase_order.state, 'draft')

        # Cancelling remains possible so that the order can be closed.
        purchase_order.button_cancel()
        self.assertEqual(purchase_order.state, 'cancel')

    def test_11_quantity_cannot_be_bypassed_through_backend_methods(self):
        purchase_order = self._create_order(self.blanket_order, [(self.product_a, 60.0)])
        purchase_order.button_confirm()
        line = purchase_order.order_line

        with self.assertRaises(ValidationError):
            line.write({'product_qty': 101.0})
        with self.assertRaises(ValidationError):
            purchase_order.write({'order_line': [
                Command.create({'product_id': self.product_a.id, 'product_qty': 41.0}),
            ]})
        with self.assertRaises(ValidationError):
            self.env['purchase.order.line'].create({
                'order_id': purchase_order.id,
                'product_id': self.product_a.id,
                'product_qty': 41.0,
            })

        # Increasing up to the agreement quantity remains allowed.
        line.write({'product_qty': 100.0})
        self.assertEqual(line.product_qty, 100.0)

    # ------------------------------------------------------------
    # Test 9 - consumption across several purchase orders
    # ------------------------------------------------------------

    def test_12_multiple_orders_consume_agreement_quantity(self):
        po_1 = self._create_order(self.blanket_order, [(self.product_a, 60.0)])
        po_1.button_confirm()
        self.assertEqual(po_1.state, 'purchase')

        with self.assertRaises(ValidationError):
            self._create_order(self.blanket_order, [(self.product_a, 41.0)])

        po_2 = self._create_order(self.blanket_order, [(self.product_a, 40.0)])
        po_2.button_confirm()
        self.assertEqual(po_2.state, 'purchase')
        self.assertEqual(self._agreement_line(self.blanket_order, self.product_a).qty_ordered, 100.0)

        with self.assertRaises(ValidationError):
            self._create_order(self.blanket_order, [(self.product_a, 1.0)])

        # Each agreement product keeps its own remaining quantity.
        po_3 = self._create_order(self.blanket_order, [(self.product_b, 50.0)])
        po_3.button_confirm()
        self.assertEqual(po_3.state, 'purchase')

        # Cancelling a confirmed order releases its quantity.
        po_1.button_cancel()
        po_4 = self._create_order(self.blanket_order, [(self.product_a, 60.0)])
        po_4.button_confirm()
        self.assertEqual(po_4.state, 'purchase')

    def test_13_draft_orders_are_validated_again_at_confirmation(self):
        # RFQs do not consume the agreement (native "Ordered" only counts confirmed orders).
        po_1 = self._create_order(self.blanket_order, [(self.product_a, 70.0)])
        po_2 = self._create_order(self.blanket_order, [(self.product_a, 70.0)])

        po_1.button_confirm()
        self.assertEqual(po_1.state, 'purchase')

        with self.assertRaises(ValidationError):
            po_2.button_confirm()
        po_2.invalidate_recordset(['state'])
        self.assertEqual(po_2.state, 'draft')

    # ------------------------------------------------------------
    # Test 10 - multi-company
    # ------------------------------------------------------------

    def test_14_multi_company(self):
        company_b = self.env['res.company'].create({'name': 'Contract Company B'})
        buyer = self.env['res.users'].create({
            'name': 'Contract Buyer',
            'login': 'contract_buyer',
            'email': 'contract.buyer@example.com',
            'company_id': self.company.id,
            'company_ids': [Command.set([self.company.id, company_b.id])],
            'group_ids': [Command.set([self.env.ref('purchase.group_purchase_user').id])],
        })
        agreement_a = self._create_blanket_order([(self.product_a, 10.0, 15.0)])
        agreement_b = self._create_blanket_order([(self.product_a, 10.0, 15.0)], company=company_b)

        po_b1 = self._create_order(agreement_b, [(self.product_a, 10.0)], user=buyer)
        self.assertEqual(po_b1.company_id, company_b)
        po_b1.button_confirm()
        self.assertEqual(po_b1.state, 'purchase')

        # Consumption of the company B agreement does not affect the company A agreement.
        po_a1 = self._create_order(agreement_a, [(self.product_a, 10.0)], user=buyer)
        po_a1.button_confirm()
        self.assertEqual(po_a1.state, 'purchase')

        # A non-superuser buyer is still blocked once the company B agreement is consumed.
        with self.assertRaises(ValidationError):
            self._create_order(agreement_b, [(self.product_a, 1.0)], user=buyer)

    # ------------------------------------------------------------
    # Native behaviour preserved for purchase templates
    # ------------------------------------------------------------

    def test_15_purchase_template_keeps_native_behaviour(self):
        template = self.env['purchase.requisition'].create({
            'requisition_type': 'purchase_template',
            'vendor_id': self.vendor.id,
            'line_ids': [Command.create({
                'product_id': self.product_a.id,
                'product_qty': 5.0,
                'price_unit': 15.0,
            })],
        })
        template.action_confirm()

        po_form = Form(self.env['purchase.order'].with_context(default_requisition_id=template.id))
        purchase_order = po_form.save()
        self.assertEqual(purchase_order.order_line.product_id, self.product_a)
        self.assertEqual(purchase_order.order_line.product_qty, 5.0)

        # Template quantities are suggestions, not limits.
        purchase_order.order_line.product_qty = 500.0
        purchase_order.button_confirm()
        self.assertEqual(purchase_order.state, 'purchase')
