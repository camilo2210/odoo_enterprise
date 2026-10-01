from odoo.tests.common import HttpCase, tagged

from odoo.addons.l10n_uy_edi_pos.tests.common import TestUyEdiPosCommon


@tagged("-at_install", "post_install", "post_install_l10n")
class TestUyEdiPosPortal(TestUyEdiPosCommon, HttpCase):

    def _portal_ticket_page(self, order):
        return self.url_open("/pos/ticket/validate?access_token=%s" % order.access_token)

    def test_portal_ticket_serves_the_cfe(self):
        """ The receipt QR must serve the legal e-Ticket, not the invoice request form """
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })
        # Demo mode returns no legal PDF, so attach a placeholder for it
        pdf = order._l10n_uy_edi_attach_pdf(b"%PDF-1.4 legal representation")

        response = self._portal_ticket_page(order)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/web/content/%s" % pdf.id, response.text)

    def test_portal_ticket_without_pdf_does_not_invoice(self):
        """ Without the legal PDF the customer gets a message, not the invoice request form """
        with self._pos_session():
            order = self._create_order({
                "pos_order_lines_ui_args": [(self.product_22, 1)],
                "customer": self.env.ref("l10n_uy.partner_cfu"),
            })

        response = self._portal_ticket_page(order)

        self.assertEqual(response.status_code, 200)
        self.assertIn("printable version of this sale is not available", response.text)
        self.assertFalse(order.is_singly_invoiced, "the sale must not have been invoiced")
