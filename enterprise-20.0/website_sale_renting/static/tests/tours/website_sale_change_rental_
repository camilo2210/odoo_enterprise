import { registry } from "@web/core/registry";
import { Time } from "@web/core/l10n/time";
import { session } from "@web/session";
import * as tourUtils from "@website_sale/js/tours/tour_utils";
import * as rentalUtils from "@website_sale_renting/../tests/tours/tour_utils";

const selectedDate = luxon.DateTime.now()
    .setZone(session.website_tz).set({hour: 8, minute: 0, second: 0, millisecond: 0});

registry.category("web_tour.tours").add("rental_cart_update_duration", {
    steps: () => [
        ...tourUtils.searchProduct("computer", { select: true }),
        tourUtils.waitForInteractionToLoad(),
        ...rentalUtils.chooseFutureRentalDates({ offset: { hours: 6 }, duration: { hours: 6 }}),
        ...tourUtils.addToCartFromProductPage(),
        tourUtils.goToCart(),
        ...tourUtils.assertCartContains({
            productName: "Computer",
            quantity: "1",
        }),
        {
            content: "Select dropped down time start",
            trigger: "select[name='rental_start_time']",
            run: `select ${Time.from(selectedDate).toString()}`,
        },
        {
            content: "Verify order line rental duration",
            trigger: 'div.text-muted.small span:contains("4 Hours")',
        },
    ],
});

registry.category("web_tour.tours").add("date_based_rental_duration", {
    steps: () => [
        ...tourUtils.searchProduct("Computer", { select: true }),
        tourUtils.waitForInteractionToLoad(),
        ...rentalUtils.chooseFutureRentalDates({ duration: { days: 1 }, select_hours: false }),
        ...tourUtils.addToCartFromProductPage(),
        {
            content: "Rental duration should display 2 days",
            trigger: "span.o_renting_details:contains(2 Days)",
        },
        tourUtils.goToCart(),
        {
            content: "Wait for cart to load",
            trigger: "#shop_cart",
        },
        ...tourUtils.assertCartAmounts({ untaxed: "40.00" }), // $ 20.00 per day
    ],
});
