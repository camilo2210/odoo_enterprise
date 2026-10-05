import { registry } from "@web/core/registry";
import * as tourUtils from '@website_sale/js/tours/tour_utils';
import * as rentalUtils from "@website_sale_renting/../tests/tours/tour_utils";


registry.category("web_tour.tours").add('shop_buy_rental_product', {
    steps: () => [
        ...tourUtils.searchProduct("computer", { select: true }),
        tourUtils.waitForInteractionToLoad(),
        ...rentalUtils.chooseFutureRentalDates({ offset: { hours: 6 }, duration: { hours: 6 } }),
        tourUtils.increaseProductPageQuantity(),
        ...tourUtils.addToCartFromProductPage(),
        tourUtils.goToCart({quantity: 2}),
        ...tourUtils.assertCartContains({
            productName: "Computer",
            quantity: '2',
        }),
        tourUtils.goToCheckout(),
        tourUtils.confirmOrder(),
        {
            content: "verify checkout page",
            trigger: 'div[name="step_name"].fw-bold:contains("Payment")',
        },
    ]
});
