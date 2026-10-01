import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

/**
 * Tests that renting_warning_message is shown
 * when picking an unavailable date range
 */
registry.category("web_tour.tours").add("website_sale_renting_select_unavailable_date", {
    steps: () => [
        {
            content: "Select Product Renting Planning",
            trigger: '.oe_product_cart:first a:contains("Product Renting Planning")',
            run: "click",
            expectUnloadPage: true,
        },
        tourUtils.waitForInteractionToLoad(),
        {
            content: "Pick an available start date",
            trigger: "input[name=renting_start_date]",
            run: "edit 03/12/2999 && press Tab",
        },
        {
            content: "Pick an available end date",
            trigger: "input[name=renting_end_date]",
            run: "edit 03/15/2999 && press Tab",
        },
        {
            content: "Check that the add to cart button is enabled",
            trigger: "button[name='add_to_cart']:not([disabled])",
        },
        {
            content: "Pick an unavailable start date",
            trigger: "input[name=renting_start_date]",
            run: "edit 03/15/2999 && press Tab",
        },
        {
            content: "Pick an unavailable end date",
            trigger: "input[name=renting_end_date]",
            run: "edit 03/18/2999 && press Tab",
        },
        {
            content: "Check that the add to cart button is disabled",
            trigger: "button[name='add_to_cart'][disabled]",
        },
    ],
});
