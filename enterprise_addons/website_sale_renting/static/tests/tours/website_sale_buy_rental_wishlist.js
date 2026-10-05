import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";
import * as wishlisttourUtils from "@website_sale/js/tours/wishlist_tour_utils";

registry.category("web_tour.tours").add("shop_buy_rental_product_wishlist", {
    steps: () => [
        {
            content: "Hover on image and click on add to wishlist",
            trigger: "img[alt=Computer]",
            run: "hover && click .o_add_wishlist",
        },
        wishlisttourUtils.goToWishlist(),
        {
            content: "click on add to cart",
            trigger: "button[name='add_to_cart']",
            run: "click",
            expectUnloadPage: true,
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
