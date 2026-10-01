import { registry } from "@web/core/registry";
import * as Utils from "@pos_self_order/../tests/tours/utils/common";
import * as CartPage from "@pos_self_order/../tests/tours/utils/cart_page_util";
import * as ProductPage from "@pos_self_order/../tests/tours/utils/product_page_util";

registry.category("web_tour.tours").add("takeaway_order_with_phone", {
    steps: () =>
        [
            Utils.checkIsNoBtn("My Order"),
            Utils.clickBtn("Order Now"),
            ProductPage.clickProduct("Test Multi Category Product"),
            Utils.clickBtn("Checkout"),
            CartPage.checkProduct("Test Multi Category Product", "2.20", "1"),
            Utils.clickBtn("Order"),
            CartPage.fillInput("Name", "Dr Dre"),
            {
                content: `select +32 in the phone country select`,
                trigger: `.input-group .position-relative select:not(:visible)`,
                run: "selectByLabel +32",
            },
            CartPage.fillInput("Phone", "455667788"),
            Utils.clickBtn("Continue"),
            Utils.clickBtn("Ok"),
        ].flat(),
});
