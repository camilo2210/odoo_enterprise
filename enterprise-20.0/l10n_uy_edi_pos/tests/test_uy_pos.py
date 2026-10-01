from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_uy_edi_pos.tests.common import TestUyEdiPosCommon


@tagged("-at_install", "post_install", "post_install_l10n")
class TestUyEdiPos(TestUyEdiPosCommon):

    def test_e_ticket(self):
        """ e-Ticket (101) for a non-RUT customer, with the receptor block only when identified. """
        for customer, expected_cfe, has_receptor in (
            (self.env.ref("l10n_uy.partner_cfu"), "pos_e_ticket", False),
            (self.partner_local_tk, "pos_e_ticket_identified", True),
        ):
            with self.subTest(customer=customer.name), self._pos_session():
                order = self._create_order({
                    "pos_order_lines_ui_args": [(self.product_22, 1)],
                    "customer": customer,
                })
                self.assertFalse(order.to_invoice)
                self.assertFalse(order.is_singly_invoiced)
                self.assertEqual(order._l10n_uy_edi_get_document_type().code, "101")
                # Below the limit the receptor block is required only for an identified customer.
                self.assertEqual(bool(order._l10n_uy_edi_cfe_A_receptor()), has_receptor)
                self._check_pos_cfe(order, expected_cfe)

    def test_threshold_above_limit(self):
        """ Above-limit CF order -> no CFE, the reason recorded on the order, and no raise """
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 3000)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
        self.assertEqual(order.l10n_uy_edi_cfe_state, "error")
        self.assertIn("receiver details", order.l10n_uy_edi_error)
        self.assertTrue(order.l10n_uy_edi_enable_send, "the order stays available for a retry")

    def test_rut_partner_invoice_path(self):
        """ RUT partner order -> standard invoice path, no POS CFE document, e-Invoice (111). """
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.partner_local,
                "is_invoiced": True,
            })
        self.assertTrue(order.to_invoice)
        self.assertTrue(order.account_move)
        self.assertFalse(order.l10n_uy_edi_document_id, "the CFE of a RUT order lives on its invoice")
        self.assertEqual(order.account_move.l10n_latam_document_type_id.code, "111")
        self.assertEqual(
            order.account_move.l10n_uy_edi_cfe_state, "accepted",
            "the CFE of the invoice must be issued during the sync, without the PDF",
        )

        # The PDF stays out of the sync even when the config asks to download the invoice
        self.config.use_download_invoice = True
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.partner_local,
                "is_invoiced": True,
            })
        self.assertTrue(order.defer_invoice_pdf, "the PDF must be left to the deferred cron")
        self.assertFalse(order.account_move.invoice_pdf_report_id)
        self.assertEqual(order.account_move.l10n_uy_edi_cfe_state, "accepted")

    def test_pay_later_non_rut_keeps_the_e_ticket(self):
        """ Customer Account forces an invoice, the CFE of a non-RUT customer stays an e-Ticket. """
        for customer in (self.env.ref("l10n_uy.partner_cfu"), self.partner_local_tk):
            with self.subTest(customer=customer.name):
                ui_args = {"pos_order_lines_ui_args": [(self.product_22, 1)], "customer": customer}
                with self._pos_session():
                    total = self.create_ui_order_data(**ui_args)["amount_total"]
                    order = self._create_order(ui_args | {"payments": [(self.pay_later_pm, total)]})
                self.assertTrue(order.is_singly_invoiced, "a pay_later payment always needs a receivable")
                self.assertEqual(order._l10n_uy_edi_get_document_type().code, "101")
                self.assertEqual(order.l10n_uy_edi_cfe_state, "accepted")
                self.assertTrue(order.l10n_uy_edi_document_id.pos_order_id, "the e-Ticket is on the order")
                self.assertFalse(order.account_move.l10n_uy_edi_document_id, "the invoice carries no CFE")
                self.assertTrue(
                    order.account_move.name.startswith("*"), "the receivable must not take a CFE number",
                )
                self.assertEqual(order._l10n_uy_edi_cfe_A_iddoc()["FmaPago"], 2, "a deferred settlement is credito")

    def test_rut_partner_forced_ticket_is_blocked(self):
        """ A stale client must not emit an e-Ticket for a RUT partner (server-side guard). """
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.partner_local,  # RUT partner
            })  # to_invoice defaults to False -> server refuses the e-Ticket
        self.assertEqual(order.l10n_uy_edi_cfe_state, "error")
        self.assertIn("must be invoiced", order.l10n_uy_edi_error)

    def test_invoicing_a_sent_e_ticket_is_blocked(self):
        """ An accepted e-Ticket must not be invoiced, the action refuses and not only the button """
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
            self.assertEqual(order.l10n_uy_edi_cfe_state, "accepted")
            self.assertTrue(order.l10n_uy_edi_is_enabled, "the Invoice button must be hidden too")

            with self.assertRaisesRegex(UserError, "report the same sale twice"):
                order.action_pos_order_invoice()

    def test_e_ticket_refund(self):
        """ e-Ticket refund -> doc 102 with a Referencia block pointing at the original CFE. """
        with self._pos_session():
            original = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
            self.assertEqual(original.l10n_uy_edi_cfe_state, "accepted")

            refund = self._refund_order(original)
        self.assertEqual(refund.refunded_order_id, original)
        self.assertEqual(refund._l10n_uy_edi_get_document_type().code, "102")
        self._check_pos_cfe(refund, "pos_e_ticket_credit_note")

    def test_e_ticket_refund_discounted_line(self):
        """ The discount amount of a refunded discounted line must stay a positive delta. """
        with self._pos_session():
            original = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 2, 10)],  # qty 2, 10% discount
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
            refund = self._refund_order(original)

        for order in (original, refund):
            line = order.lines
            details = order._l10n_uy_edi_cfe_B_details(order._l10n_uy_edi_get_base_lines())
            # A positive 10% of the gross in the CFE currency, not the negative refund delta
            self.assertAlmostEqual(
                details[0]["DescuentoMonto"], abs(line.qty) * line.price_unit * 0.10,
                places=2, msg=order.name,
            )

    def test_e_ticket_refund_of_unaccepted_is_blocked(self):
        """ A 102 whose original order has no accepted CFE must be refused. """
        with self._pos_session():
            original = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
            # Drop the accepted CFE so the original counts as not accepted
            original.l10n_uy_edi_document_id.unlink()
            original.l10n_uy_edi_document_number = False
            self.assertNotEqual(original.l10n_uy_edi_cfe_state, "accepted")

            refund = self._refund_order(original)
            self.assertEqual(refund.l10n_uy_edi_cfe_state, "error")
            self.assertIn("does not have an accepted CFE", refund.l10n_uy_edi_error)

    def test_e_ticket_refund_of_rejected_is_terminal(self):
        """ A rejected original CFE can never be referenced, the error must not invite a retry """
        with self._pos_session():
            original = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
            original.l10n_uy_edi_document_id.state = "rejected"

            refund = self._refund_order(original)
            self.assertEqual(refund.l10n_uy_edi_cfe_state, "error")
            self.assertIn("rejected by DGI", refund.l10n_uy_edi_error)
            self.assertNotIn("yet", refund.l10n_uy_edi_error)

    def _order_for_live_send(self):
        """ A CF order whose demo CFE is dropped, in a (mocked) live environment for a fresh send. """
        order = self._create_order({
            "pos_order_lines_ui_args": [(self.product_22, 1)],
            "customer": self.env.ref("l10n_uy.partner_cfu"),
        })
        order.l10n_uy_edi_document_id.unlink()
        order.l10n_uy_edi_document_number = False
        self.company_uy.write({
            "l10n_uy_edi_ucfe_env": "testing",
            "l10n_uy_edi_ucfe_password": "password_xxx",
            "l10n_uy_edi_ucfe_commerce_code": "commerce_xxx",
            "l10n_uy_edi_ucfe_terminal_code": "terminal_xxx",
        })
        return order

    def test_failed_sends_are_recorded_not_raised(self):
        """ A DGI rejection and a connectivity failure are recorded on the order, never raised """
        for response, kwargs, expected in (
            ("mock_invoice_rejected_status", {}, "rejected"),
            ("NO_RESPONSE", {"exception": "Timeout"}, "error"),
        ):
            with self.subTest(expected=expected), self._pos_session():
                order = self._order_for_live_send()

                with self._mock_pos_inbox(response, **kwargs):
                    order.l10n_uy_edi_action_send_document()  # must not raise

                self.assertEqual(order.l10n_uy_edi_cfe_state, expected)
                self.assertTrue(order.l10n_uy_edi_error)
                self.assertTrue(order.l10n_uy_edi_enable_send, "the order stays available for a retry")

    def test_retry_unlinks_previous_documents(self):
        """ Retry drops the previous failed document and leaves the accepted one """
        with self._pos_session():
            order = self._order_for_live_send()

            # Simulate a previous failed attempt whose document was persisted
            previous = self.env["l10n_uy_edi.document"].create({
                "pos_order_id": order.id, "uuid": "retry-doc", "state": "rejected",
            })
            order.l10n_uy_edi_document_id = previous
            self.assertTrue(order.l10n_uy_edi_enable_send)

            with self._mock_pos_inbox("mock_80_invoice_accepted"):
                order.l10n_uy_edi_action_send_document()

            self.assertFalse(previous.exists(), "the failed attempt must be superseded")
            self.assertEqual(order.l10n_uy_edi_cfe_state, "accepted")

    def test_non_billable_product(self):
        """ A non-billable line is reported with IndFact 6, in MontoNF and out of MntTotal """
        non_billable = self.env["product.product"].create({
            "name": "POS Rounding Adjustment",
            "type": "service",
            "available_in_pos": True,
            "company_id": self.company_uy.id,
            "taxes_id": False,
            "l10n_uy_edi_is_non_billable": True,
        })
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1), (non_billable, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
        self.assertEqual(order.l10n_uy_edi_cfe_state, "accepted")

        namespace = {"cfe": "http://cfe.dgi.gub.uy"}
        cfe = self.get_xml_tree_from_attachment(order.l10n_uy_edi_document_id.attachment_id)
        items = cfe.findall(".//cfe:Detalle/cfe:Item", namespace)
        self.assertEqual(len(items), 2, "The non-billable line must be reported in the detail")
        nb_item = next(
            item for item in items
            if item.find("cfe:NomItem", namespace).text == non_billable.name
        )
        self.assertEqual(nb_item.find("cfe:IndFact", namespace).text, "6", "Not the non-billable indicator")

        nb_line = order.lines.filtered(lambda line: line.product_id == non_billable)
        totals = cfe.find(".//cfe:Totales", namespace)
        self.assertEqual(float(totals.find("cfe:MontoNF", namespace).text), nb_line.price_subtotal)
        self.assertEqual(
            float(totals.find("cfe:MntTotal", namespace).text),
            order.amount_total - nb_line.price_subtotal,
            "The non-billable amount must be excluded from MntTotal",
        )
        self.assertEqual(
            float(totals.find("cfe:MntPagar", namespace).text), order.amount_total,
            "...but not from MntPagar",
        )
