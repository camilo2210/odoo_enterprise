# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from odoo.addons.sale_amazon.tests import common
from odoo.addons.stock.tests.common import TestStockCommon


@tagged("post_install", "-at_install")
class TestStock(common.TestAmazonCommon, TestStockCommon):
    # As this test class is exclusively intended to test Amazon-related check on pickings, the
    # normal flows of stock are put aside in favor of manual updates on quantities.

    _test_user_groups = None  # FIXME list needed groups

    def setUp(self):
        super().setUp()

        # Create sales order
        self.partner = self.env["res.partner"].create({"name": "Gederic Frilson"})
        self.amazon_offer = self.account._find_or_create_offer(
            "test SKU", self.account.base_marketplace_id
        )
        self.sale_order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "name": "test",
                        "product_id": self.productA.id,
                        "product_uom_qty": 2,
                        "amazon_item_ref": "123456789",
                        "amazon_offer_id": self.amazon_offer.id,
                    },
                )
            ],
            "amazon_order_ref": "123456789",
        })

        # Create picking
        self.picking = self.PickingObj.create({
            "picking_type_id": self.picking_type_in.id,
            "location_id": self.supplier_location.id,
            "location_dest_id": self.customer_location.id,
        })
        move_vals = {
            "product_id": self.productA.id,
            "product_uom_qty": 1,
            "uom_id": self.productA.uom_id.id,
            "picking_id": self.picking.id,
            "location_id": self.supplier_location.id,
            "location_dest_id": self.customer_location.id,
            "sale_line_id": self.sale_order.order_line[0].id,
        }
        self.move_1 = self.MoveObj.create(move_vals)
        self.move_2 = self.MoveObj.create(move_vals)
        self.picking.sale_id = self.sale_order.id  # After creating the moves as it clears the field

    def test_confirm_picking_trigger_sol_check(self):
        """Test that confirming a picking triggers a check on sales order lines completion."""
        with patch(
            "odoo.addons.sale_amazon.models.stock_picking.StockPicking"
            "._check_sales_order_line_completion",
            new=Mock(),
        ) as mock:
            self.picking.date_done = fields.Datetime.now()  # Trigger the check for SOL completion
            self.assertEqual(
                mock.call_count,
                1,
                "confirming a picking should trigger a check on the sales order lines completion",
            )

    def test_check_sol_completion_no_move(self):
        """Test that the check on SOL completion passes if no move is confirmed."""
        self.assertIsNone(
            self.picking._check_sales_order_line_completion(),
            "the check of SOL completion should not raise for pickings with completions of 0% (no"
            "confirmed move for a given sales order line)",
        )

    def test_check_sol_completion_all_moves(self):
        """Test that the check on SOL completion passes if all moves are confirmed."""
        self.move_1.quantity = 1
        self.move_2.quantity = 1
        self.assertIsNone(
            self.picking._check_sales_order_line_completion(),
            "the check of SOL completion should not raise for pickings with completions of 100% "
            "(all moves related to a given sales order line are confirmed)",
        )

    def test_check_sol_completion_some_moves(self):
        """Test that the check on SOL completion fails if only some moves are confirmed."""
        self.move_1.quantity = 1
        with self.assertRaises(UserError):
            # The check of SOL completion should raise for pickings with completions of ]0%, 100%[
            # (some moves related to a given sales order line are confirmed, but not all)
            self.picking._check_sales_order_line_completion()

    def test_get_carrier_details_returns_other_when_unsupported(self):
        """Test that we fall back to 'Other' as CarrierCode if the carrier is not supported."""
        self.picking.carrier_id = self.carrier
        carrier_code, carrier_name = self.picking._get_amazon_carrier_code_and_name()
        self.assertEqual(carrier_code, "Other")
        self.assertEqual(carrier_name, self.carrier.name)

    def test_get_carrier_details_returns_formatted_carrier_name_when_supported(self):
        """Test that we use the formatted carrier name when it is supported by Amazon."""
        self.carrier.name = "d_H l)"
        self.picking.carrier_id = self.carrier
        carrier_code, _carrier_name = self.picking._get_amazon_carrier_code_and_name()
        self.assertEqual(carrier_code, "DHL")

    def test_sync_orders_confirms_pickings_with_a_pending_status(self):
        """Test pickings with a status of pending in odoo are updated when receiving the
        information that the order is delivered from Amazon."""

        def get_sp_api_response_mock(_account, operation_, **_kwargs):
            """Return a mock response without making an actual call to the Selling Partner API."""
            base_response_ = common.OPERATIONS_RESPONSES_MAP[operation_]
            if operation_ == "getOrder":
                order_mock = base_response_["order"]
                return {
                    "order": {
                        **order_mock,
                        "fulfillment": {
                            **order_mock["fulfillment"],
                            "fulfillmentStatus": "SHIPPED",
                        },
                    }
                }
            return base_response_

        with patch(
            "odoo.addons.sale_amazon.utils.make_sp_api_request", new=get_sp_api_response_mock
        ):
            # Set up the test pickings
            self.picking.update({"amazon_sync_status": "error", "state": "cancel"})
            # Create a new picking
            pending_picking = self.PickingObj.create({
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.customer_location.id,
            })
            move_vals = {
                "product_id": self.productA.id,
                "product_uom_qty": 1,
                "uom_id": self.productA.uom_id.id,
                "picking_id": pending_picking.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.customer_location.id,
                "sale_line_id": self.sale_order.order_line[0].id,
            }
            self.MoveObj.create(move_vals)
            pending_picking.sale_id = self.sale_order.id

            self.account._sync_order_by_reference(self.sale_order.amazon_order_ref)
            self.assertEqual(
                self.picking.amazon_sync_status,
                "error",
                msg="Picking with an errored Amazon sync status should not be updated when there is"
                "another pending picking and the picking is confirmed by Amazon.",
            )
            self.assertEqual(
                pending_picking.amazon_sync_status,
                "done",
                msg="Picking with a pending Amazon sync status should be updated when the picking "
                "is confirmed by Amazon.",
            )

    def test_sync_orders_confirms_pickings_with_an_errored_status(self):
        """Test pickings with a status of errored in odoo are updated when receiving the
        information that the order is delivered from Amazon."""

        def get_sp_api_response_mock(_account, operation_, **_kwargs):
            """Return a mock response without making an actual call to the Selling Partner API."""
            base_response_ = common.OPERATIONS_RESPONSES_MAP[operation_]
            if operation_ == "getOrder":
                order_mock = base_response_["order"]
                return {
                    "order": {
                        **order_mock,
                        "fulfillment": {
                            **order_mock["fulfillment"],
                            "fulfillmentStatus": "SHIPPED",
                        },
                    }
                }
            return base_response_

        with patch(
            "odoo.addons.sale_amazon.utils.make_sp_api_request", new=get_sp_api_response_mock
        ):
            # Set up the test pickings
            self.picking.update({"amazon_sync_status": "error"})

            self.account._sync_order_by_reference(self.sale_order.amazon_order_ref)
            self.assertEqual(
                self.picking.amazon_sync_status,
                "done",
                msg="Picking with an errored Amazon sync status should be updated when the picking "
                "is confirmed by Amazon and there is no pending picking.",
            )

    @mute_logger("odoo.addons.sale_amazon.models.amazon_account")
    def test_action_retry_amazon_sync_dont_resync_when_picking_is_confirmed_from_amazon(self):
        self.picking.amazon_sync_status = "error"

        with patch(
            "odoo.addons.sale_amazon.models.amazon_account.AmazonAccount._sync_order_by_reference",
            new=lambda _self, *_args: self.picking.update({"amazon_sync_status": "done"}),
        ):
            self.picking.action_retry_amazon_sync()
        msg = "Picking with Amazon sync status updated during the sync order should stay as done."
        self.assertEqual(self.picking.amazon_sync_status, "done", msg=msg)

    def test_action_retry_amazon_sync_set_waiting_state_after_resync(self):
        # Make sure we have those fields set on the company.
        self.env.company.partner_id.write({
            "street": "Company Street Office 2",
            "country_id": self.env.ref("base.be").id,
        })
        self.picking.amazon_sync_status = "error"
        with (
            patch(
                "odoo.addons.sale_amazon.models.amazon_account.AmazonAccount._sync_order_by_reference"
            ),
            patch("odoo.addons.sale_amazon.utils.submit_feed", return_value="Mock feed ID"),
        ):
            self.picking.action_retry_amazon_sync()
        msg = "Picking with Amazon sync status not updated in the sync order should be re-submitted"
        self.assertEqual(self.picking.amazon_sync_status, "processing", msg=msg)
        msg = "Picking re-submitted have the new feed ID set."
        self.assertEqual(self.picking.amazon_feed_ref, "Mock feed ID", msg=msg)

    def test_generate_stock_moves_for_not_tracked_product_sets_move_done(self):
        self.product.tracking = False
        self.env["stock.quant"].create({
            "product_id": self.product.id,
            "location_id": self.stock_location.id,
            "quantity": 30,
        })
        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({
                    "product_id": self.product.id,
                    "amazon_item_ref": "item_ref",
                    "product_uom_qty": 2,
                })
            ],
            "amazon_order_ref": "test_ref",
            "state": "sale",
            "locked": True,
        })
        StockMove = self.env["stock.move"]
        initial_moves = StockMove.search([("product_id", "=", self.product.id)])
        self.assertFalse(initial_moves, msg="No stock move should be created yet.")

        self.account._generate_stock_moves(sale_order)

        new_moves = StockMove.search([
            ("product_id", "=", self.product.id),
            ("id", "not in", initial_moves.ids),
        ])

        msg = "All moves should be set as done."
        self.assertEqual(new_moves.state, "done", msg=msg)

    def test_move_reference_without_picking(self):
        """Ensure an Amazon move correctly references the SO when not linked to a picking."""
        amazon_sale_order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [
                Command.create({
                    "name": "test",
                    "product_id": self.productA.id,
                    "product_uom_qty": 2,
                    "amazon_item_ref": "0123456789",
                    "amazon_offer_id": self.amazon_offer.id,
                })
            ],
            "amazon_order_ref": "0123456789",
            "amazon_channel": "fba",
        })

        self.account._generate_stock_moves(amazon_sale_order)

        amazon_move = amazon_sale_order.order_line.move_ids
        self.assertEqual(amazon_move.reference, f"Amazon move: {amazon_sale_order.name}")
