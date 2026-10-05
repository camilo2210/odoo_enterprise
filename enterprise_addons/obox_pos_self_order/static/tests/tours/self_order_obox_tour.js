/* global posmodel */

import { registry } from "@web/core/registry";
import * as Utils from "@pos_self_order/../tests/tours/utils/common";
import * as ProductPage from "@pos_self_order/../tests/tours/utils/product_page_util";
import * as ConfirmationPage from "@pos_self_order/../tests/tours/utils/confirmation_page_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as CartPage from "@pos_self_order/../tests/tours/utils/cart_page_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";

registry.category("web_tour.tours").add("test_obox_request_and_callback_mobile_each", {
    steps: () => [
        Utils.checkIsNoBtn("My Order"),
        Utils.clickBtn("Order Now"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        Utils.clickBtn("Order"),
        Utils.clickBtn("Ok"),
        Utils.checkBtn("My Orders"),
        Utils.clickBtn("Order Now"),
        ProductPage.clickProduct("Fanta"),
        Utils.clickBtn("Checkout"),
        Utils.clickBtn("Order"),
        ConfirmationPage.isShown(),
        refresh(),
        Utils.clickBtn("Ok"),
        Utils.checkIsNoBtn("Order Now"),
        Utils.checkBtn("My Order"),
        Chrome.endTour(),
    ],
});

registry.category("web_tour.tours").add("test_obox_request_and_callback_mobile_meal", {
    steps: () =>
        [
            Utils.checkIsNoBtn("My Order"),
            Utils.clickBtn("Order Now"),
            ProductPage.clickProduct("Coca-Cola"),
            ProductPage.clickProduct("Fanta"),
            Utils.clickBtn("Checkout"),
            Utils.clickBtn("Order"),
            ConfirmationPage.isShown(),
            Utils.clickBtn("Ok"),
            Utils.clickBtn("Order Now"),
            ProductPage.clickProduct("Coca-Cola"),
            ProductPage.clickProduct("Fanta"),
            Utils.clickBtn("Checkout"),
            Utils.clickBtn("Order"),
            ConfirmationPage.isShown(),
            Utils.clickBtn("Ok"),
            Chrome.endTour(),
        ].flat(),
});

const checkPreparationIsntLoaded = {
    content: "No prep.order and no prep.order.line loaded",
    trigger: "body",
    run: async () => {
        await new Promise((resolve) => {
            const checkSync = () => {
                if (typeof posmodel.currentOrder.id === "number") {
                    resolve();
                } else {
                    setTimeout(checkSync, 100);
                }
            };

            checkSync();
        });
        const prepOrder = posmodel.models["pos.prep.order"].filter((p) => typeof p.id === "number");
        const prepOrderLine = posmodel.models["pos.prep.line"].filter(
            (p) => typeof p.id === "number"
        );

        if (prepOrder.length !== 0 || prepOrderLine.length !== 0) {
            throw new Error(
                `Prep order and prep order line should not be loaded in self-ordering mode, but got ${prepOrder.length} prep orders and ${prepOrderLine.length} prep order lines`
            );
        }
    },
};

registry.category("web_tour.tours").add("test_pos_self_order_preparation_each", {
    steps: () => [
        Utils.clickBtn("Order Now"),
        ProductPage.clickProduct("Coca-Cola"),
        Utils.clickBtn("Checkout"),
        Utils.clickBtn("Order"),
        checkPreparationIsntLoaded,
    ],
});

registry.category("web_tour.tours").add("test_pos_self_order_preparation_meal", {
    steps: () =>
        [
            Utils.clickBtn("Order Now"),
            ProductPage.clickProduct("Coca-Cola"),
            Utils.clickBtn("Checkout"),
            Utils.clickBtn("Order"),
            ...CartPage.selectTable("1"),
            checkPreparationIsntLoaded,
            Utils.clickBtn("Ok"),
        ].flat(),
});

registry.category("web_tour.tours").add("test_pos_self_order_preparation_kiosk", {
    steps: () =>
        [
            Utils.clickBtn("Order Now"),
            ProductPage.clickProduct("Coca-Cola"),
            Utils.clickBtn("Checkout"),
            Utils.clickBtn("Order"),
            {
                content: "Fill number",
                trigger: ".numpad-button[value='1']",
                run: "click",
            },
            Utils.clickBtn("Order"),
            checkPreparationIsntLoaded,
            Utils.clickBtn("Close"),
        ].flat(),
});
