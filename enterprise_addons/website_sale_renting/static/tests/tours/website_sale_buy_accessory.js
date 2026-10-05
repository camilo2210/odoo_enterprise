import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_buy_accessory_rental_product", {
    steps: () => [
        ...tourUtils.addToCart({ productName: "Parent product", expectUnloadPage: true }),
        tourUtils.goToCart(),
        ...tourUtils.assertCartContains({
            productName: "Parent Product",
            quantity: "1",
        }),
        {
            content: "Add Accessory product to cart via the quick add button",
            trigger: 'button:contains("Add to cart")',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Check product added to the cart",
            trigger: ".my_cart_quantity:contains(2)",
        },
    ],
});
