import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";

registry.category("web_tour.tours").add("test_ec_pos_order_refund", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Acme Corporation"),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            ProductScreen.totalAmountIs("5.10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.clickNextOrder(),
            ProductScreen.clickRefund(),
            TicketScreen.search("Customer", "Acme Corporation"),
            TicketScreen.selectOrder("001"),
            ProductScreen.clickNumpad("1"),
            TicketScreen.confirmRefund(),
            {
                content: `customer 'Acme Corporation' is selected`,
                trigger: `button.partner-button:contains('Acme Corporation')`,
            },
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_max_consumer_final_limit_validation_from_frontend", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.addOrderline("product_a", "1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            Dialog.is({ title: "Alert" }),
            Dialog.bodyIs(
                "This sale exceeds the maximum amount allowed for an unidentified consumer. Please select the real customer with a valid RUC/ID before continuing."
            ),
            Dialog.confirm("Ok"),
            PaymentScreen.clickInvoiceButton(false),
            PaymentScreen.isInvoiceButtonUnchecked(),
            PaymentScreen.clickValidate(),
            FeedbackScreen.clickNextOrder(),
            Chrome.clickOrders(),
            TicketScreen.selectFilter("Paid"),
            TicketScreen.selectOrder("0001"),
            TicketScreen.clickControlButton("Invoice"),
            Dialog.is({ title: "Alert" }),
            Dialog.bodyIs(
                "This order exceeds the maximum amount allowed for an unidentified consumer. Please select the real customer with a valid RUC/ID before continuing."
            ),
            Dialog.confirm("Ok"),
            Chrome.endTour(),
        ].flat(),
});
