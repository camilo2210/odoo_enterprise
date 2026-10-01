import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";

function checkReceipt(invoiceNumber) {
    return FeedbackScreen.checkTicketData({
        cssRules: [
            {
                css: "body div",
                text: "ISSUED IN SANDBOX ENVIRONMENT - WITHOUT FISCAL VALUE",
            },
            {
                css: "body div",
                text: "Auxiliary Document of Consumer Invoice",
            },
            {
                css: "body div",
                text: `NFC-e nº ${invoiceNumber}`,
            },
        ],
    });
}

function checkNoExcludedTaxesProducts() {
    return [
        ProductScreen.searchProduct("Cabinet with doors"),
        {
            content: "Should find no products",
            trigger: ".product-screen:contains('No products found for')",
        },
        {
            content: "Click search more",
            trigger: ".search-more-button > button",
            run: "click",
        },
        {
            trigger: ".status-buttons:has(.oi-spin)",
        },
        Chrome.isSynced(), // wait for async search to complete
        {
            content: "Should still find no products",
            trigger: ".product-screen:contains('No products found for')",
        },
    ].flat();
}

export function generateTour(invoiceNumber, customerName) {
    return [
        Chrome.freezeDateTime(1738796117000),
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),
        ...(customerName
            ? [ProductScreen.clickPartnerButton(), ProductScreen.clickCustomer(customerName)]
            : []),
        ProductScreen.addOrderline("Acoustic Bloc Screens", 3),
        checkNoExcludedTaxesProducts(),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        FeedbackScreen.isContinueEnabled(),
        checkReceipt(invoiceNumber),
        FeedbackScreen.clickNextOrder(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrder("001"),
        Chrome.endTour(),
    ].flat();
}
