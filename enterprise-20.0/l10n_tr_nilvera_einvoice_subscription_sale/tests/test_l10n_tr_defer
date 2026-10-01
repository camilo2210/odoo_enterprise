from odoo.tests import tagged
from odoo.addons.l10n_tr_nilvera_einvoice.tests.test_account_move_send import TestTRAccountMoveSend


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTRDeferredInvoices(TestTRAccountMoveSend):

    _test_user_groups = None  # FIXME list needed groups

    def test_invoice_line_dates_valid_for_nilvera(self):
        # Test for valid invoice configurations:
        # Case 1: Invoice with a subscription invoice line and a non-subscription invoice line
        # Case 2: Invoice with two subscription invoice lines with the same subscription dates, and a non-subscription invoice line

        valid_invoices_vals = [
            [
                ("2025-11-1", "2025-12-1"),
                (False, False)
            ],
            [
                ("2025-11-1", "2025-12-1"),
                ("2025-11-1", "2025-12-1"),
                (False, False)
            ],
        ]
        invoices = self.env["account.move"]
        for vals in valid_invoices_vals:
            invoices += self._create_invoice(
                move_type="out_invoice",
                invoice_date='2025-11-1',
                partner_id=self.partner_tr,
                invoice_line_ids=[
                    self._prepare_invoice_line(
                        product_id=self.product_a,
                        deferred_start_date=start_date,
                        deferred_end_date=end_date,
                    )
                    for start_date, end_date in vals
                ],
                post=True
            )
        wizard = self.create_send_and_print(invoices)
        self.assertNotIn('tr_invalid_subscription_dates', wizard.alerts)

    def test_invoice_line_dates_invalid_for_nilvera(self):
        # Test for invalid invoice configurations:
        # Case 1: Invoice with two subscription invoice lines with different dates and a non-subscription invoice line

        invalid_invoice_vals = [
            ("2025-11-1", "2025-12-1"),
            ("2025-11-1", "2025-12-2"),
            (False, False)
        ]
        invoice = self._create_invoice(
            move_type="out_invoice",
            partner_id=self.partner_tr,
            invoice_date='2025-11-1',
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_a,
                    deferred_start_date=start_date,
                    deferred_end_date=end_date,
                )
                for start_date, end_date in invalid_invoice_vals
            ],
            post=True
        )
        wizard = self.create_send_and_print(invoice)
        self.assertIn('tr_invalid_subscription_dates', wizard.alerts)
