import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

function assertStateCity(fieldName, expectedState) {
    // :checked doesn't seem to work in the trigger, so let's check manually.
    const select = document.querySelector(`select[name="${fieldName}"]`);
    if (!select) {
        throw new Error(`Field ${fieldName} not found`);
    }

    const selectedValue = select.value;
    const option = select.querySelector(`option[value="${selectedValue}"]`);

    if (!option.innerText.includes(expectedState)) {
        throw new Error("The right state was not auto-selected.");
    }
}

registry.category("web_tour.tours").add("test_brazilian_address", {
    steps: () => [
        ...tourUtils.addToCart({
            productName: "Brazilian test product",
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
            content: "Set Brazil first",
            trigger: 'select[name="country_id"]',
            run: "selectByLabel Brazil",
        },
        {
            content: "Click to select a city",
            trigger: 'select[name="city_id"]',
            run: "click",
        },
        {
            content: "Select Abadia de Goiás",
            trigger: 'select[name="city_id"]',
            run: "selectByLabel Abadia de Goiás",
        },
        {
            content: "Check that Goiás state is automatically selected based on the city.",
            trigger: 'select[name="country_id"]',
            run: () => assertStateCity("state_id", "Goiás"),
        },
        {
            content: "Input a zip",
            trigger: 'input[name="zip"]',
            run: "fill 12345-000",
        },
        {
            content: "Check that Jacareí is automatically selected based on the zip,",
            trigger: 'select[name="city_id"]',
            run: () => assertStateCity("city_id", "Jacareí"),
        },
        {
            content: "Check that São Paulo state is automatically selected based on the city.",
            trigger: 'select[name="country_id"]',
            run: () => assertStateCity("state_id", "São Paulo"),
        },
    ],
});
