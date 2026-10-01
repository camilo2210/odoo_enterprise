import { registry } from "@web/core/registry";
import * as wsTourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_buy_subscription_product", {
    steps: () => [
        ...wsTourUtils.goToProductPage({ productName: "Streaming SUB Weekly" }),
        wsTourUtils.increaseProductPageQuantity(),
        ...wsTourUtils.addToCartFromProductPage(),
        {
            content: "See added to cart + try to add other recurrence",
            trigger: '.my_cart_quantity:contains("2")',
            run: function () {
                window.location.href = "/shop";
            },
            expectUnloadPage: true,
        },
        ...wsTourUtils.goToProductPage({ productName: "Streaming SUB Monthly" }),
        wsTourUtils.goToCart({ quantity: 2 }),
        {
            content: "Order summary",
            trigger: 'h4:contains("Order summary")',
        },
    ],
});
