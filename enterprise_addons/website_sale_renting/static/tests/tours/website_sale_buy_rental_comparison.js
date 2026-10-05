import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("shop_buy_rental_product_comparison", {
    steps: () => [
        {
            content: "hover on computer and click on add to comparison",
            trigger: "img[alt=Computer]",
            run: "hover && click .o_add_compare",
        },
        ...tourUtils.searchProduct("Color T-Shirt"),
        {
            trigger: ".o_wsale_comparison_bottom_bar .badge:contains(1)",
        },
        {
            content: "add first product 'Color T-Shirt' in a comparison list",
            trigger: `img[alt="Color T-Shirt"]`,
            run: "hover && click .o_add_compare",
        },
        {
            content: "check the compare button contains two products",
            trigger: ".o_wsale_comparison_bottom_bar .badge:contains(2)",
        },
        {
            content: "click on compare button",
            trigger: 'a:contains("Compare")',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "click on add to cart",
            trigger: '.product_summary:contains("Computer") button:contains("Add to Cart")',
            run: "click",
        },
        tourUtils.goToCart(),
        ...tourUtils.assertCartContains({
            productName: "Computer",
            quantity: "1",
            price: "3.50",
        }),
        tourUtils.goToCheckout(),
        tourUtils.confirmOrder(),
        {
            content: "verify checkout page",
            trigger: 'div[name="step_name"].fw-bold:contains("Payment")',
        },
    ],
});
