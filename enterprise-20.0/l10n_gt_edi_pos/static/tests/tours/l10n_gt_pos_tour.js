import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import * as PartnerList from "@point_of_sale/../tests/pos/tours/utils/partner_list_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import { registry } from "@web/core/registry";

function createOrderFlow({
    customerName,
    orderLineProductName = "Test Product",
    productQuantity = 1,
    productUnitPrice = 2500,
    expectAlerts = true,
    saleOrderNumber,
    refundOrderNumber,
}) {
    function alertExceedsLimit() {
        return [
            Dialog.is({ title: "Limit Exceeded" }),
            Dialog.bodyIs(
                "This order exceeds the maximum amount allowed for an unidentified customer."
            ),
            Dialog.bodyIs(
                "Please select a customer with a valid Identification Type and Number before continuing."
            ),
            Dialog.confirm("Ok"),
        ];
    }
    function alertLinkedOrderNotInvoiced() {
        return [
            Dialog.is({ title: "Linked Order Not Invoiced" }),
            Dialog.bodyIs(
                "The order linked to this refund has not been electronically invoiced. Please make sure the original order has an electronic invoice before trying to create an electronic credit note for this refund."
            ),
            Dialog.confirm("Ok"),
        ];
    }

    const steps = [
        ProductScreen.isShown(),
        ProductScreen.clickPartnerButton(),
        PartnerList.searchCustomerValue(customerName, true),
        PartnerList.clickPartner(customerName),
        ProductScreen.addOrderline(orderLineProductName, productQuantity, productUnitPrice),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.isInvoiceButtonChecked(),
        PaymentScreen.validateButtonIsHighlighted(),
        PaymentScreen.clickValidate(),
    ];

    if (expectAlerts) {
        steps.push(
            alertExceedsLimit(),
            PaymentScreen.clickInvoiceButton(false),
            PaymentScreen.isInvoiceButtonUnchecked(),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            Chrome.clickOrders(),
            TicketScreen.selectFilter("Paid"),
            TicketScreen.selectOrder(saleOrderNumber),
            TicketScreen.clickControlButton("Invoice"),
            alertExceedsLimit(),
            TicketScreen.selectOrder(saleOrderNumber),
            TicketScreen.confirmRefund(),
            PaymentScreen.isShown(),
            PaymentScreen.clickInvoiceButton(false),
            PaymentScreen.isInvoiceButtonUnchecked(),
            alertLinkedOrderNotInvoiced(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            Chrome.clickOrders(),
            TicketScreen.selectFilter("Paid"),
            TicketScreen.selectOrder(refundOrderNumber),
            TicketScreen.clickControlButton("Invoice"),
            alertLinkedOrderNotInvoiced()
        );
    } else {
        steps.push(FeedbackScreen.isShown());
    }
    return steps.flat();
}

registry.category("web_tour.tours").add("test_gt_pos_unidentified_customer_threshold_limit", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.customerIsSelected("Guatemala Consumidor Final"),

            createOrderFlow({
                customerName: "Guatemala Consumidor Final",
                saleOrderNumber: "0001",
                refundOrderNumber: "0002",
            }),

            Chrome.createFloatingOrder(),
            createOrderFlow({
                customerName: "GT Unidentified Customer",
                saleOrderNumber: "0003",
                refundOrderNumber: "0004",
            }),

            Chrome.createFloatingOrder(),
            createOrderFlow({
                customerName: "Foreign Unidentified Customer",
                saleOrderNumber: "0005",
                refundOrderNumber: "0006",
            }),

            Chrome.createFloatingOrder(),
            createOrderFlow({ customerName: "GT Identified Customer", expectAlerts: false }),

            Chrome.createFloatingOrder(),
            createOrderFlow({ customerName: "Foreign Identified Customer", expectAlerts: false }),

            Chrome.endTour(),
        ].flat(),
});
