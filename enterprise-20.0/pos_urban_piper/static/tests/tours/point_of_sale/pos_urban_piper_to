/* global posmodel */

import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as UrbanPiper from "@pos_urban_piper/../tests/tours/point_of_sale/utils/pos_urban_piper_utils";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Notification from "@point_of_sale/../tests/generic_helpers/notification_util";
import { inLeftSide } from "@point_of_sale/../tests/pos/tours/utils/common";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("OrderFlowTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(3),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.nbOrdersIs(3),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(2),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.onDropdownStatus("Ongoing"),
            TicketScreen.nbOrdersIs(1),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.nbOrdersIs(2),
            TicketScreen.selectOrder("002"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.orderHasText("002", "Acknowledged"),
            TicketScreen.selectOrderByPrice("100.00"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
            TicketScreen.selectFilter("Active"),
            TicketScreen.selectOrder("002"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("002", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("OrderWithInstructionTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            Order.hasCustomerNote("Make it spicy.."),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("OrderWithChargesAndDiscountTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_payment_method_close_session", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Product 1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("UrbanPiper"),
            PaymentScreen.clickValidate(),
            Chrome.clickMenuOption("Close Register"),
            Dialog.confirm("Close Register"),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("OrderPrepTime", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.isReady(),
            UrbanPiper.clickPrepTime(),
            UrbanPiper.clickPrepTime(),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_reject_order", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Reject"),
            {
                content: "select reason 'Product is out of Stock'",
                trigger: ".selection-item:contains('Product is out of Stock')",
                run: "click",
            },
        ].flat(),
});
registry.category("web_tour.tours").add("test_urban_piper_orders_filter_button", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            Chrome.createFloatingOrder(),
            ProductScreen.clickDisplayedProduct("product 2"),
            Chrome.clickOrders(),
            TicketScreen.nbOrdersIs(2),
            TicketScreen.clickFilterButton("Food Platform"),
            TicketScreen.nbOrdersIs(1),
            UrbanPiper.orderHasText("001", "Just Eat"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_dynamic_product_variant_creation", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            inLeftSide(
                Order.hasLine({
                    productName: "T-Shirt",
                    quantity: 2,
                    attributeLine: "Red, Large",
                })
            ),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_dynamic_with_never_create_variant_attribute", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            inLeftSide(
                Order.hasLine({
                    productName: "T-Shirt",
                    quantity: 2,
                    attributeLine: "Red, Large, Cotton",
                })
            ),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_to_check_attribute", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            inLeftSide(
                Order.hasLine({
                    productName: "Configurable Chair",
                    quantity: 2,
                    attributeLine: "Red, Metal, Wool, Cushion, Cup Holder",
                })
            ),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_receipt_data_urban_piper", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            Order.hasCustomerNote("Make it spicy.."),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
            UrbanPiper.orderHasText("001", "Just Eat"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.orderHasText("001", "Food Ready"),
            {
                content: "Throw receipt data to check in backend",
                trigger: "body",
                run: async () => {
                    const order = posmodel.getOrder();
                    const data = posmodel.ticketPrinter.getOrderReceiptData(order);
                    try {
                        await posmodel.data.call("pos.order", "get_order_frontend_receipt_data", [
                            [order.id],
                            data,
                        ]);
                    } finally {
                        // Ignore any error, the main test is in the backend
                    }
                },
            },
        ].flat(),
});

registry.category("web_tour.tours").add("test_pos_urbanpiper_future_delivery_order", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            TicketScreen.selectOrder("001"),
            inLeftSide({
                content: "Check if delivery order is a future order",
                trigger: ".leftpane div:contains(Scheduled time:)",
            }),
            UrbanPiper.orderButtonClick("Accept"),
            UrbanPiper.fetchDeliveryData(),
            {
                content: "Trigger future order preparation notification",
                trigger: "body",
                run: async () => {
                    await posmodel.data.call("pos.order", "notify_future_deliveries");
                },
            },
            Notification.has("Scheduled Delivery Order"),
            UrbanPiper.checkNewOrderCount(0),
            UrbanPiper.orderHasText("001", "Acknowledged"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_product_level_discount", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            UrbanPiper.fetchDeliveryData(),
            {
                content: "Check 20% discount applied on orderline",
                trigger: ".orderline .info-list li.price-per-unit em:contains(20%)",
            },
            UrbanPiper.checkNewOrderCount(1),
            UrbanPiper.onDropdownStatus("New"),
            UrbanPiper.orderButtonClick("Accept"),
            TicketScreen.selectOrder("001"),
            UrbanPiper.orderButtonClick("Mark as ready"),
            UrbanPiper.fetchDeliveryData(),
            TicketScreen.selectFilter("Paid"),
            UrbanPiper.orderHasText("001", "Food Ready"),
        ].flat(),
});
