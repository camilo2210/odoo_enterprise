import odoo
from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.point_of_sale.models.pos_config import PosConfig
from unittest.mock import patch


@odoo.tests.tagged('post_install', '-at_install')
class TestPoSSettleDueHttpCommon(TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_pos_settle_due_main(self):
        """
        As tour are very energy consuming, we will only write one test
        in which we will test the main flow of settling a due invoice

        Testing behavior:
        - Create an order with customer account and check that the due
        amount is correct on the partner
        - Deposit money from the partner list and check that the due
        amount is updated on the partner
        - Settle an open invoice from the partner list and check that
        the due amount is updated on the partner
        """
        self.partner_test_a = self.env["res.partner"].create({"name": "A Partner"})
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'type': 'pay_later',
        })
        self.main_pos_config.write({
            'payment_method_ids': [
                (4, self.customer_account_payment_method.id),
            ]
        })
        moda = self.env['res.partner'].create({
            'name': 'AAA - Moda',
        })
        invoice = self.env['account.move'].create({
            'partner_id': moda.id,
            'date': '2025-02-17',
            'invoice_date': '2025-02-17',
            'move_type': 'out_invoice',
            'invoice_line_ids': [
                (0, 0, {'name': 'test', 'price_unit': 200})
            ],
        })
        invoice.action_post()
        self.assertEqual(moda.total_due, 200)

        self.main_pos_config.open_ui()
        self.start_pos_tour('test_pos_settle_due_main', login='accountman')

        # Check partner due amount, should be 80000 deposit minus 10
        # from partially paid order created in the tour
        self.assertEqual(moda.total_due, -79990.0)

        pos_invoice = moda.invoice_ids[0]
        self.assertEqual(pos_invoice.amount_residual, 10)
        self.env['account.payment.register'].with_context(
            active_ids=pos_invoice.ids,
            active_model='account.move'
        ).create({
            'payment_date': pos_invoice.date,
            'amount': 10,
        })._create_payments()

        self.assertEqual(pos_invoice.amount_residual, 0)

    def test_settle_due_search_more(self):
        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'type': 'pay_later',
        })
        partner_test_a = self.env["res.partner"].create({"name": "APartner"})
        partner_test_b = self.env["res.partner"].create({"name": "BPartner"})

        def mocked_get_limited_partners_loading(self, offset=0):
            return [(partner_test_a.id,)]

        payment_methods = self.main_pos_config.payment_method_ids | self.customer_account_payment_method
        self.main_pos_config.write({'payment_method_ids': [Command.set(payment_methods.ids)]})

        self.assertEqual(partner_test_b.total_due, 0)
        self.assertEqual(partner_test_b.has_moves, False)

        self.main_pos_config.with_user(self.pos_admin).open_ui()
        current_session = self.main_pos_config.current_session_id

        order = self.env['pos.order'].create({
            'company_id': self.env.company.id,
            'session_id': current_session.id,
            'partner_id': partner_test_b.id,
            'lines': [Command.create({
                'product_id': self.product_a.id,
                'price_unit': 10,
                'discount': 0,
                'qty': 1,
                'price_subtotal': 10,
                'price_subtotal_incl': 10,
            })],
            'amount_paid': 10.0,
            'amount_total': 10.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'to_invoice': True,
        })

        payment_context = {"active_ids": order.ids, "active_id": order.id}
        order_payment = self.env['pos.make.payment'].with_context(**payment_context).create({
            'amount': 10.0,
            'payment_method_id': self.customer_account_payment_method.id
        })
        order_payment.with_context(**payment_context).check()

        self.assertEqual(partner_test_b.total_due, 10)
        current_session.close_session_from_ui()

        self.main_pos_config.with_user(self.user).open_ui()
        with patch.object(PosConfig, 'get_limited_partners_loading', mocked_get_limited_partners_loading):
            self.main_pos_config.open_ui()
            self.start_pos_tour('test_settle_due_search_more', login='accountman')

    def test_settle_open_invoice_with_credit_note(self):
        """Ensure POS settles net amount of invoice minus credit note via 'Settle invoices'."""
        self.partner_c = self.env["res.partner"].create({"name": "C Partner"})

        invoice = self.env["account.move"].create({
            "partner_id": self.partner_c.id,
            "date": "2025-02-17",
            "invoice_date": "2025-02-17",
            "move_type": "out_invoice",
            "invoice_line_ids": [(0, 0, {"name": "test", "price_unit": 10})],
        })
        invoice.action_post()
        credit_note = self.env["account.move"].create({
            "partner_id": self.partner_c.id,
            "date": "2025-02-17",
            "invoice_date": "2025-02-17",
            "move_type": "out_refund",
            "invoice_line_ids": [(0, 0, {"name": "credit", "price_unit": 2})],
        })
        credit_note.action_post()

        self.assertEqual(self.partner_c.total_due, 8)

        self.customer_account_payment_method = self.env["pos.payment.method"].create({
            "name": "Customer Account",
            'type': 'pay_later',
        })
        self.main_pos_config.write({
            "payment_method_ids": [(4, self.customer_account_payment_method.id, 0)],
        })

        self.main_pos_config.open_ui()
        self.start_tour(
            "/pos/ui?config_id=%d" % self.main_pos_config.id,
            "pos_settle_open_invoice_with_credit_note",
            login="accountman",
        )
        self.main_pos_config.current_session_id.close_session_from_ui()
        self.assertEqual(self.partner_c.total_due, 0)

    def test_settle_partial_paid_invoice_from_pos(self):
        self.partner_a = self.env['res.partner'].create({'name': 'A Partner'})

        self.customer_account_payment_method = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'type': 'pay_later',
        })
        self.main_pos_config.write({
            'payment_method_ids': [(4, self.customer_account_payment_method.id, 0)],
        })

        self.main_pos_config.open_ui()
        self.start_pos_tour('deposit_money_to_customer_and_pay_with_customer_account', login='accountman')
        last_order = self.main_pos_config.current_session_id.order_ids[0]
        account_move = last_order.account_move
        self.assertTrue(account_move)
        self.assertEqual(account_move.payment_state, 'not_paid')

        # Used _compute_payments_widget_to_reconcile_info domain to find the correct account move lines to reconcile with the invoice
        pay_term_lines = account_move.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        domain = [
            ('account_id', 'in', pay_term_lines.account_id.ids),
            '|', *account_move._check_company_domain(account_move.company_id), ('company_id', 'child_of', account_move.company_id.id),
            ('partner_id', '=', account_move.commercial_partner_id.id),
            ('reconciled', '=', False),
            ('balance', '<' if account_move.is_inbound() else '>', 0.0),
            '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
        ]
        account_move_lines = self.env['account.move.line'].search(domain)
        self.assertEqual(len(account_move_lines), 1)
        account_move.js_assign_outstanding_line([account_move_lines[0].id])
        self.assertEqual(account_move.payment_state, 'partial')
        self.start_pos_tour('settle_partial_paid_invoice_from_pos', login='accountman')
        self.main_pos_config.current_session_id.close_session_from_ui()
        self.assertEqual(self.partner_a.total_due, 0)
