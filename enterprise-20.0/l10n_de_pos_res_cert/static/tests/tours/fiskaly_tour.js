/* global posmodel */
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreenPos from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ProductScreenResto from "@pos_restaurant/../tests/tours/utils/product_screen_util";
const ProductScreen = { ...ProductScreenPos, ...ProductScreenResto };
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("FiskalyTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("AA Test Partner"),
            ProductScreen.addOrderline("Coca-Cola", "1", "3"),
            // Each change triggers a request; without waiting, the non-awaitable mutex causes failures.
            Chrome.waitRequest(),
            ProductScreen.clickOrderButton(),
            Chrome.waitForOrdersSync(),
            FloorScreen.clickTable("5"),
            ProductScreen.orderlinesHaveNoChange(),
            Chrome.clickPlanButton(),
            FloorScreen.clickTable("5"),
            Order.hasLine({
                productName: "Coca-Cola",
            }),
            ProductScreen.addOrderline("Coca-Cola", "1", "5"),
            ProductScreen.clickOrderButton(),
            Chrome.waitForOrdersSync(),
            FloorScreen.clickTable("5"),
            ProductScreen.isShown(),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickInvoiceButton(),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isContinueEnabled(),
            FeedbackScreen.checkTicketData({
                cssRules: [
                    {
                        css: ".tss-info tr",
                        length: 11,
                    },
                    {
                        css: ".tss-info tr:nth-child(1) td:nth-child(1)",
                        text: "TSE-Transaktion",
                    },
                    {
                        css: ".tss-info tr:nth-child(1) td:nth-child(2)",
                        empty: true,
                    },
                    {
                        css: ".tss-info tr:nth-child(2) td:nth-child(1)",
                        text: "Bonnummer",
                    },
                    {
                        css: ".tss-info tr:nth-child(2) td:nth-child(2)",
                        empty: true,
                        negation: true,
                    },
                    {
                        css: ".tss-info tr:nth-child(3) td:nth-child(1)",
                        text: "TSE-Start",
                    },
                    {
                        css: ".tss-info tr:nth-child(3) td:nth-child(2)",
                        text: "1970-01-01T02:46:40.000Z",
                    },
                    {
                        css: ".tss-info tr:nth-child(4) td:nth-child(1)",
                        text: "TSE-Stop",
                    },
                    {
                        css: ".tss-info tr:nth-child(4) td:nth-child(2)",
                        text: "1970-01-01T05:33:20.000Z",
                    },
                    {
                        css: ".tss-info tr:nth-child(5) td:nth-child(1)",
                        text: "TSE-Seriennummer",
                    },
                    {
                        css: ".tss-info tr:nth-child(5) td:nth-child(2)",
                        text: "12345-abcdes",
                    },
                    {
                        css: ".tss-info tr:nth-child(6) td:nth-child(1)",
                        text: "TSE-Zeitformat",
                    },
                    {
                        css: ".tss-info tr:nth-child(6) td:nth-child(2)",
                        text: "format",
                    },
                    {
                        css: ".tss-info tr:nth-child(7) td:nth-child(1)",
                        text: "TSE-Signatur",
                    },
                    {
                        css: ".tss-info tr:nth-child(7) td:nth-child(2)",
                        text: "12345",
                    },
                    {
                        css: ".tss-info tr:nth-child(8) td:nth-child(1)",
                        text: "TSE-Hashalgorithmus",
                    },
                    {
                        css: ".tss-info tr:nth-child(8) td:nth-child(2)",
                        text: "fake_algo",
                    },
                    {
                        css: ".tss-info tr:nth-child(9) td:nth-child(1)",
                        text: "TSE-PublicKey",
                    },
                    {
                        css: ".tss-info tr:nth-child(9) td:nth-child(2)",
                        text: "fake_key",
                    },
                    {
                        css: ".tss-info tr:nth-child(10) td:nth-child(1)",
                        text: "Client Serial No.",
                    },
                    {
                        css: ".tss-info tr:nth-child(10) td:nth-child(2)",
                        empty: true,
                    },
                ],
            }),
            FeedbackScreen.clickNextOrder(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_fiskaly_tss_payload", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.addOrderline("Coca-Cola", "1", "5"),
            ProductScreen.clickPayButton(false),
            PaymentScreen.clickPaymentMethod("Random Name"),
            {
                content: "Check if the payload is correct",
                trigger: "body",
                run: () => {
                    const payment = posmodel.getOrder()._createAmountPerPaymentTypeArray();
                    if (payment[0].payment_type != "CASH") {
                        throw new Error("Payment type should be CASH");
                    }
                },
            },
        ].flat(),
});

registry.category("web_tour.tours").add("test_fiskaly_receipt_printer", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.addOrderline("Coca-Cola", "1", "3"),
            // Each change triggers a request; without waiting, the non-awaitable mutex causes failures.
            Chrome.waitRequest(),
            ProductScreen.clickPayButton(false),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            Dialog.is({ title: "Printing Failed" }),
            Dialog.cancel(),
            Chrome.waitRequest(),
        ].flat(),
});
