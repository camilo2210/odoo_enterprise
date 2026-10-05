from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.point_of_sale.tests.test_generic_localization import TestGenericLocalization
from odoo.tests import tagged
from odoo import Command, fields
from unittest.mock import patch
from lxml import etree
from lxml import objectify


def mocked_l10n_pe_edi_post_invoice_sign_web_service(invoice):
    # sign the EDI
    edi_filename = invoice._l10n_pe_edi_generate_edi_filename()
    edi_str, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
    edi_tree = objectify.fromstring(edi_str)
    signed_edi = invoice._l10n_pe_edi_sign(invoice.company_id.sudo().l10n_pe_edi_certificate_id, edi_tree)
    edi_str = etree.tostring(signed_edi, xml_declaration=True, encoding='ISO-8859-1')
    zip_edi_str = invoice._l10n_pe_edi_zip_edi_document([('%s.xml' % edi_filename, edi_str)])
    invoice.env['ir.attachment'].create({
        'res_model': invoice._name,
        'res_id': invoice.id,
        'res_field': 'l10n_pe_edi_attachment_file',
        'type': 'binary',
        'name': '%s.zip' % edi_filename,
        'raw': zip_edi_str,
        'mimetype': 'application/zip',
    })
    invoice.invalidate_recordset(fnames=["l10n_pe_edi_attachment_file", "l10n_pe_edi_attachment_id"])
    invoice.l10n_pe_edi_status = 'sent'


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPeEdiPoS(TestPeEdiCommon, TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].l10n_pe_edi_provider = 'digiflow'

    def test_invoice_signed_qr_code(self):
        with patch(
            "odoo.addons.l10n_pe_edi.models.account_move.AccountMove._l10n_pe_edi_post_invoice",
            new=mocked_l10n_pe_edi_post_invoice_sign_web_service,
        ):
            self.main_pos_config.open_ui()
            self.main_pos_config.use_download_invoice = True

            # We need to assign a new journal to the PoS that uses l10n_latam_use_documents
            self.main_pos_config.journal_id = self.env["account.journal"].create(
                {
                    "type": "sale",
                    "name": "Point of Sale - Test",
                    "code": "POSS-T",
                    "company_id": self.env.company.id,
                    "sequence": 20,
                    "l10n_latam_use_documents": True,
                }
            )
            order_data = {
                "amount_paid": 1180,
                "amount_tax": 180,
                "amount_return": 0,
                "amount_total": 1180,
                "date_order": fields.Datetime.to_string(fields.Datetime.now()),
                "fiscal_position_id": False,
                "lines": [
                    Command.create({
                        "discount": 0,
                        "price_unit": 1000.0,
                        "product_id": self.product_a.id,
                        "price_subtotal": 1000.0,
                        "price_subtotal_incl": 1180.0,
                        "tax_ids": [[6, False, [self.product_a.taxes_id[0].id]]],
                        "qty": 1,
                    }),
                ],
                "name": "Order 12345-123-1234",
                "partner_id": self.partner_a.id,
                "session_id": self.main_pos_config.current_session_id.id,
                "sequence_number": 2,
                "payment_ids": [
                        Command.create({
                            "amount": 1180,
                            "name": fields.Datetime.now(),
                            "payment_method_id": self.bank_payment_method.id,
                        }),
                ],
                "uuid": "12345-123-1234",
                "user_id": self.env.uid,
                "to_invoice": True,
            }

            order = self.env["pos.order"].sync_from_ui([order_data])["pos.order"][0]
            legal_documents = self.env["pos.order"].browse(order["id"]).account_move._get_invoice_legal_documents('pdf', allow_fallback=True)
            self.assertEqual(len(legal_documents), 1)
            invoice_str = legal_documents[0]['content'].decode()
            self.assertTrue("barcode_type=QR" in invoice_str)

    def test_receipt_html_contains_pe_edi_fields(self):
        with patch(
            "odoo.addons.l10n_pe_edi.models.account_move.AccountMove._l10n_pe_edi_post_invoice",
            new=mocked_l10n_pe_edi_post_invoice_sign_web_service,
        ):
            self.main_pos_config.open_ui()
            self.assertFalse(self.main_pos_config.use_download_invoice)

            self.main_pos_config.journal_id = self.env["account.journal"].create(
                {
                    "type": "sale",
                    "name": "Point of Sale - Test 2",
                    "code": "POSS-T2",
                    "company_id": self.env.company.id,
                    "sequence": 21,
                    "l10n_latam_use_documents": True,
                }
            )
            order_data = {
                "amount_paid": 1180,
                "amount_tax": 180,
                "amount_return": 0,
                "amount_total": 1180,
                "date_order": fields.Datetime.to_string(fields.Datetime.now()),
                "fiscal_position_id": False,
                "lines": [
                    Command.create({
                        "discount": 0,
                        "price_unit": 1000.0,
                        "product_id": self.product_a.id,
                        "price_subtotal": 1000.0,
                        "price_subtotal_incl": 1180.0,
                        "tax_ids": [[6, False, [self.product_a.taxes_id[0].id]]],
                        "qty": 1,
                    }),
                ],
                "name": "Order 12345-123-1235",
                "partner_id": self.partner_a.id,
                "session_id": self.main_pos_config.current_session_id.id,
                "sequence_number": 3,
                "payment_ids": [
                        Command.create({
                            "amount": 1180,
                            "name": fields.Datetime.now(),
                            "payment_method_id": self.bank_payment_method.id,
                        }),
                ],
                "uuid": "12345-123-1235",
                "user_id": self.env.uid,
                "to_invoice": True,
            }

            order = self.env["pos.order"].sync_from_ui([order_data])["pos.order"][0]
            pos_order = self.env["pos.order"].browse(order["id"])

            # PDF/email stay deferred to the cron; only the e-invoice itself is posted now.
            self.assertTrue(pos_order.defer_invoice_pdf)
            self.assertEqual(pos_order.account_move.l10n_pe_edi_status, "sent")

            edi_data = pos_order.account_move._l10n_pe_edi_get_extra_report_values()
            html = pos_order.order_receipt_generate_html()
            receipt = etree.HTML(html)

            self.assertTrue(receipt.xpath("//img[@class='edi-qr-code']"), "QR code image not found in the receipt")
            self.assertTrue(receipt.xpath("//b[contains(text(), 'Amount In Word')]"), "'Amount In Word' label not found in the receipt")
            self.assertIn(edi_data["amount_to_text"], html)
            self.assertTrue(receipt.xpath("//p[contains(text(), 'Summary')]"), "'Summary' label not found in the receipt")
            self.assertIn(edi_data["qr_str"].split("|")[-2], html)

    def test_refund_reason_not_set(self):
        """
        Test that a refund in Peruvian PoS does not crash and sets the refund reason.
        """
        self.main_pos_config.open_ui()
        session = self.main_pos_config.current_session_id
        order_result = self.env["pos.order"].sync_from_ui([{
            "amount_paid": 1180,
            "amount_tax": 180,
            "amount_return": 0,
            "amount_total": 1180,
            "lines": [
                Command.create({
                    "price_unit": 1000.0,
                    "product_id": self.product_a.id,
                    "price_subtotal": 1000.0,
                    "price_subtotal_incl": 1180.0,
                    "tax_ids": [Command.set([self.product_a.taxes_id[0].id])],
                    "qty": 1,
                }),
            ],
            "name": "Order 12345-123-1234",
            "partner_id": self.partner_a.id,
            "session_id": session.id,
            "payment_ids": [
                Command.create({
                    "amount": 1180,
                    "name": fields.Datetime.now(),
                    "payment_method_id": self.bank_payment_method.id,
                }),
            ],
            "uuid": "12345-123-1234",
            "to_invoice": True,
        }])
        original_order = self.env["pos.order"].browse(order_result["pos.order"][0]["id"])
        refund_order = self.env["pos.order"].create({
            "session_id": session.id,
            "partner_id": original_order.partner_id.id,
            "lines": [Command.create({
                "product_id": self.product_a.id,
                "qty": -1.0,
                "price_unit": 1000.0,
                "tax_ids": [Command.set([self.product_a.taxes_id[0].id])],
                "price_subtotal": -1000.0,
                "price_subtotal_incl": -1180.0,
            })],
            "refunded_order_id": original_order.id,
            "to_invoice": True,
            "amount_total": -1180.0,
            "amount_tax": -180.0,
            "amount_paid": -1180.0,
            "amount_return": 0.0,
            'is_refund': True,
        })
        refund_order.refunded_order_id = original_order
        try:
            refund_invoice = refund_order._generate_pos_order_invoice()
        except TypeError as e:
            self.fail(f'l10n_pe_edi_refund_reason should be able to not be set: {e}')
        # To make sure the l10n_pe_edi_refund_reason is still set as it should
        refund_order.write({"l10n_pe_edi_refund_reason": "01"})
        refund_invoice = refund_order._generate_pos_order_invoice()
        self.assertEqual(refund_invoice.l10n_pe_edi_refund_reason, "01")


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestGenericPE(TestGenericLocalization):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
