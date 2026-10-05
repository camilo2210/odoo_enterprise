import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";
import * as rentalUtils from "@website_sale_renting/../tests/tours/tour_utils";

registry.category("web_tour.tours").add("shop_buy_rental_stock_product", {
    steps: () => [
        ...tourUtils.searchProduct("computer", { select: true }),
        tourUtils.waitForInteractionToLoad(),
        ...rentalUtils.chooseFutureRentalDates({ offset: { hours: 8 }, duration: { hours: 4 } }),
        tourUtils.increaseProductPageQuantity(),
        ...tourUtils.addToCartFromProductPage(),
        tourUtils.goToCart({ quantity: 2 }),
        ...tourUtils.assertCartContains({
            productName: "Computer",
            quantity: "2",
            price: "28.00",
        }),
        {
            content: "Go back on the Computer",
            trigger: '#cart_products div h6:contains("Computer")',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Verify there is a warning message",
            trigger:
                'div#threshold_message_renting:contains("Only 3 Units still available during the selected period.")',
        },
        tourUtils.goToCart({ quantity: 2 }),
        tourUtils.goToCheckout(),
        tourUtils.confirmOrder(),
        ...tourUtils.payWithTransfer({
            redirect: true,
            expectUnloadPage: true,
            waitFinalizeYourPayment: true,
        }),
    ],
});

registry.category("web_tour.tours").add("website_availability_update", {
    steps: () => [
        ...tourUtils.searchProduct("Test Product with Variants", { select: true }),
        {
            trigger:
                '#threshold_message_renting:contains("Only 1 Units still available during the selected period.")',
        },
        {
            trigger: '.o_wsale_product_attribute li:eq(1) input[type="radio"]',
            run: "click",
        },
        {
            trigger: "#out_of_stock_message",
        },
    ],
});

registry.category("web_tour.tours").add("test_website_availability_while_continuing_selling", {
    steps: () => [
        ...tourUtils.searchProduct("Computer", { select: true }),
        {
            trigger:
                "#threshold_message_renting:contains('Only 2 Units still available during the selected period.')",
        },
        tourUtils.waitForInteractionToLoad(),
        ...rentalUtils.chooseFutureRentalDates({ duration: { days: 3 }, select_hours: false }),
        {
            trigger:
                "#threshold_message_renting:contains('Only 5 Units still available during the selected period.')",
        },
    ],
});
