# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.addons.l10n_br_edi.tests.data_invoice_1 import invoice_1_submit_success_response
from odoo.addons.l10n_br_edi.tests.test_l10n_br_edi import TestL10nBREDICommon
from odoo.tests import tagged


@tagged("post_install_l10n", "-at_install", "post_install")
class TestL10nBrEDIStock(TestL10nBREDICommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_screens.barcode = "12345678"
        cls.product_screens.is_storable = True
        cls.product_screens.product_variant_id.weight = 7
        cls.package_type = cls.env["stock.package.type"].create(
            {"name": "Box", "l10n_br_brand": "BR brand", "base_weight": 3}
        )
        cls.sale_order = cls.env["sale.order"].sudo().create(
            {
                "partner_id": cls.partner_customer.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product_screens.product_variant_id.id,
                            "tax_ids": False,
                            "product_uom_qty": 12,
                        }
                    ),
                ],
                "l10n_br_edi_freight_model": "CIF",
            }
        ).sudo(False)

    def _post_nfe(self, moves):
        """Post `moves` without reaching out to Avalara."""
        with self.with_patched_account_move("_l10n_br_iap_request"), self.with_patched_account_move(
            "_get_and_set_external_taxes_on_eligible_records",
        ):
            moves.action_post()

    def _create_accepted_nfe(self, count=1, fiscal_position=None):
        """Create posted NF-e SEFAZ accepted, the only documents that may end up on a label."""
        moves = self.env["account.move"].create([{
            "move_type": "out_invoice",
            "partner_id": self.partner_customer.id,
            "invoice_date": "2026-04-06",
            "fiscal_position_id": (fiscal_position or self.avatax_fp).id,
            "invoice_line_ids": [Command.create({"product_id": self.product_screens.product_variant_id.id})],
        } for _ in range(count)])
        self._post_nfe(moves)
        moves.journal_id.l10n_br_invoice_serial = "1"
        moves.l10n_br_last_edi_status = "accepted"
        return moves

    def _invoice_sale_order(self):
        """Invoice the sale order through the Avatax fiscal position a Brazilian sale needs."""
        invoice = self.sale_order._create_invoices()
        invoice.fiscal_position_id = self.avatax_fp
        self.partner_customer.property_account_position_id = self.avatax_fp
        self._post_nfe(invoice)
        return invoice

    def _validate_packed_picking(self):
        """Confirm the sale order and validate its delivery with everything in one package."""
        self.sale_order.action_confirm()
        picking = self.sale_order.order_line.move_ids.picking_id[0]
        picking.move_ids[0].quantity = picking.move_ids[0].product_uom_qty
        picking.action_put_in_pack()
        picking.button_validate()
        return picking

    def test_nfe_with_transport_info(self):
        self.sale_order.action_confirm()
        picking = self.sale_order.order_line.move_ids.picking_id[0]
        picking.move_ids[0].quantity = picking.move_ids[0].product_uom_qty
        picking.action_put_in_pack()
        picking.move_line_ids.result_package_id.package_type_id = self.package_type
        picking.button_validate()

        invoice = self.sale_order._create_invoices()
        invoice.fiscal_position_id = self.avatax_fp  # only set it on the invoice to avoid patching out calls on sale order
        invoice.l10n_br_package_ids = invoice.l10n_br_related_package_ids  # select all related packages

        self.partner_customer.property_account_position_id = self.avatax_fp
        with self.with_patched_account_move("_l10n_br_iap_request"), self.with_patched_account_move("_get_and_set_external_taxes_on_eligible_records"):
            invoice.action_post()
        invoice.l10n_br_edi_avatax_data = {"header": {}}  # normally set by account.external.tax.mixin
        invoice.l10n_br_plate_number = "12345678"

        wizard = self.env["account.move.send.wizard"].create({"move_id": invoice.id})

        with self.with_patched_account_move("_l10n_br_iap_request") as patched_submit:
            wizard.action_send_and_print(allow_fallback_pdf=True)  # allow_fallback_pdf to avoid raising on errors

        sent_request = patched_submit.call_args.args[3]

        self.assertIn("volumes", sent_request["header"]["goods"]["transport"], "Transport data wasn't sent in request.")
        self.assertEqual(len(sent_request["header"]["goods"]["transport"]["volumes"]), 1, "Exactly one volume should be sent.")
        self.assertDictEqual(
            sent_request["header"]["goods"]["transport"]["vehicle"], {"automobile": {"licensePlate": "12345678"}}
        )
        self.assertDictEqual(
            sent_request["header"]["goods"]["transport"]["volumes"][0],
            {
                "qVol": 1,
                "volumeNumeration": "1 of 1",
                "netWeight": 7.0 * 12,
                "grossWeight": 7.0 * 12 + 3,
                "brand": "BR brand",
                "specie": "Box",
            },
        )

    def test_origin_invoice_precedence(self):
        picking = self._validate_packed_picking()
        package = picking.move_line_ids.result_package_id
        transfer_nfe, package_nfe = self._create_accepted_nfe(count=2)
        no_invoice = self.env["account.move"]

        self.assertEqual(
            picking._l10n_br_get_origin_invoice(package.name),
            (True, no_invoice),
            "Goods with no NF-e at all are waited for and resolve to nothing.",
        )
        self.assertTrue(picking._l10n_br_has_missing_nfe_packages(), "The package should hold the label back.")

        sale_nfe = self._invoice_sale_order()
        sale_nfe.journal_id.l10n_br_invoice_serial = "1"
        sale_nfe.l10n_br_last_edi_status = "accepted"
        self.assertEqual(package.l10n_br_move_id, sale_nfe, "Invoicing assigns the packages it bills to the NF-e.")
        self.assertFalse(picking._l10n_br_has_missing_nfe_packages(), "An accepted NF-e lets the label be requested.")

        package.l10n_br_move_id = False
        self.assertEqual(
            picking._l10n_br_get_origin_invoice(package.name),
            (True, sale_nfe),
            "An unassigned package falls back on the NF-e of the sale order that shipped it.",
        )

        picking.l10n_br_related_move_id = transfer_nfe
        self.assertEqual(
            picking._l10n_br_get_origin_invoice(package.name),
            (True, transfer_nfe),
            "The invoice referenced on the transfer should win over the sale order's.",
        )

        package.l10n_br_move_id = package_nfe
        self.assertEqual(
            picking._l10n_br_get_origin_invoice(package.name),
            (True, package_nfe),
            "A package assigned to its own NF-e should not use the transfer's.",
        )

        package_nfe.l10n_br_last_edi_status = "pending"
        self.assertEqual(
            picking._l10n_br_get_origin_invoice(package.name),
            (True, no_invoice),
            "An NF-e SEFAZ hasn't accepted should never end up on a shipping label.",
        )

    def test_only_avatax_invoices_are_waited_for(self):
        picking = self._validate_packed_picking()
        not_avatax_nfe = self._create_accepted_nfe(
            fiscal_position=self.env["account.fiscal.position"].create({"name": "Not Avatax"}),
        )
        picking.l10n_br_related_move_id = not_avatax_nfe

        self.assertEqual(
            picking._l10n_br_get_origin_invoice(picking.move_line_ids.result_package_id.name),
            (False, not_avatax_nfe),
            "An invoice Odoo never sends to Avalara resolves, but is not one the goods wait for.",
        )
        self.assertFalse(picking._l10n_br_has_missing_nfe_packages(), "Goods billed outside Avatax should not wait.")

    def test_authorized_nfe_relates_itself_to_its_transfers(self):
        picking = self._validate_packed_picking()
        invoice = self._invoice_sale_order()
        self.assertFalse(picking.l10n_br_related_move_id, "Posting says nothing about what SEFAZ will answer.")

        with self.with_patched_account_move("_l10n_br_prepare_invoice_payload", {"header": {}}), \
             self.with_patched_account_move("_l10n_br_submit_invoice", (invoice_1_submit_success_response, None)):
            invoice._l10n_br_edi_send()

        self.assertEqual(
            picking.l10n_br_related_move_id,
            invoice,
            "Authorizing the NF-e should relate it to the transfer shipping its goods, unprompted.",
        )
