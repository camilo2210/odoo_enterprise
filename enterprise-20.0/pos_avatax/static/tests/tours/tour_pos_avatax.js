import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import { registry } from "@web/core/registry";

function checkReceipt() {
    // The taxes are the ones returned by Avatax, not the ones Odoo would calculate based on the (deliberately
    // misconfigured) tax percentages. The CA STATE tax is configured at 1% but Avatax returns 0.36 (6% of 5.94).
    return FeedbackScreen.checkTicketData({
        cssRules: [
            { css: "div[name='prices']", text: "5.94" },
            { css: "tr[name='taxes_line']", text: "CA STATE" },
            { css: "tr[name='taxes_line']", text: "0.36" },
            { css: "tr[name='taxes_line']", text: "CA COUNTY" },
            { css: "tr[name='taxes_line']", text: "0.01" },
            { css: "tr[name='taxes_line']", text: "CA SPECIAL" },
            { css: "tr[name='taxes_line']", text: "0.14" },
            { css: ".total-amount", text: "6.45" },
        ],
    });
}

function generateTour() {
    const product_name = "Wall Shelf Unit";
    const extra_product_name = "Small Shelf";
    return [
        Chrome.freezeDateTime(1742238133000),
        Chrome.startPoS(),
        Dialog.confirm("Open Register"),

        // The first order is created before freezeDateTime() is executed, create a new one to have the right date.
        Chrome.createFloatingOrder(),

        ProductScreen.addOrderline(product_name, 3),
        ProductScreen.clickPayButton(), // calculate taxes with RPC
        Chrome.waitRequest(),

        // head back to test recalculation
        PaymentScreen.clickBackToProductScreen(),
        // The tax is deliberately misconfigured (see test_01_order), so Odoo would compute a different amount. This
        // displays the $ amount returned by Avatax as-is.
        ProductScreen.orderLineHas(product_name, 3, "$ 6.45"),
        ProductScreen.totalAmountIs("$ 6.45"),

        ProductScreen.addOrderline(extra_product_name, 1), // add new line to test recalculation
        ProductScreen.orderLineHas(product_name, 3, "$ 6.45"), // should still display the amount from avatax
        ProductScreen.orderLineHas(extra_product_name, 1, "$ 2.83"),

        ProductScreen.clickLine(product_name, 3), // change the original line's qty to test if it recalculates
        ProductScreen.clickNumpad("Qty", "4"),
        ProductScreen.orderLineHas(product_name, 4, "$ 8.43"), // base recalculates, the avatax tax amount is kept

        // Set back to the original quantity, the amount from avatax applies again
        ProductScreen.clickNumpad("⌫", "3"),
        ProductScreen.orderLineHas(product_name, 3, "$ 6.45"),

        // Remove the extra line
        ProductScreen.clickLine(extra_product_name, 1),
        ProductScreen.clickNumpad("⌫", "⌫"),
        ProductScreen.totalAmountIs("$ 6.45"), // wait for the line to be removed

        ProductScreen.clickPayButton(),
        Chrome.waitRequest(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        FeedbackScreen.isShown(),
        checkReceipt(),
        Chrome.endTour(),
    ].flat();
}

registry.category("web_tour.tours").add("pos_avatax.tour_order", {
    steps: () => generateTour(),
});
