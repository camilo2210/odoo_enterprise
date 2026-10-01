import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("test_chile_address", {
    steps: () => [
        ...tourUtils.addToCart({
            productName: "Chile test product",
            search: false,
            expectUnloadPage: true,
        }),
        tourUtils.goToCart({ quantity: 1 }),
        tourUtils.goToCheckout(),
        {
            content: "base_address_extended should not be shown",
            trigger: 'select[name="city_id"]:not(:visible)',
        },
        {
            content: "Set Chile first",
            trigger: 'select[name="country_id"]',
            run: "selectByLabel Chile",
        },
        // Verify that the city_id dropdown is visible for Chile Country.
        {
            content: "base_address_extended should be visible",
            trigger: "select[name='city_id']:visible",
        },
        {
            content: "Set State Valparaíso",
            trigger: 'select[name="state_id"]',
            run: "selectByLabel Valparaíso",
        },
        {
            content: "Select Algarrobo",
            trigger: 'select[name="city_id"]',
            run: "selectByLabel Algarrobo"
        },
    ],
});
