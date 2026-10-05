import { registry } from "@web/core/registry";
import * as tourUtils from "@website_sale/js/tours/tour_utils";

registry.category("web_tour.tours").add("website_sale_renting_planning_max_qty", {
    steps: () => [
        {
            content: "Select Product Renting Planning",
            trigger: ".oe_product_cart:first a:contains('Product Renting Planning')",
            run: "click",
            expectUnloadPage: true,
        },
        tourUtils.waitForInteractionToLoad(),
        {
            content: "Pick a valid start date",
            trigger: "input[name=renting_start_date]",
            run: "edit 03/12/2999 && press Tab",
        },
        {
            content: "Pick a valid end date",
            trigger: "input[name=renting_end_date]",
            run: "edit 03/15/2999 && press Tab",
        },
        tourUtils.increaseProductPageQuantity(),
        {
            content: "One quantity should be added",
            trigger: "input[name=add_qty]:value('2')",
        },
        tourUtils.increaseProductPageQuantity(),
        {
            content: "No quantity should be added",
            trigger: "input[name=add_qty]:value('2')",
        },
        {
            content: "Pick a valid end date",
            trigger: "input[name=renting_end_date]",
            run: "edit 03/18/2999 && press Tab",
        },
        {
            content: "Check that add to cart button is disabled",
            trigger: "button[name='add_to_cart'][disabled]",
        },
        {
            content: "Pick a valid end date",
            trigger: "input[name=renting_end_date]",
            run: "edit 03/15/2999 && press Tab",
        },
        {
            content: "Add product to cart",
            trigger: "button[name='add_to_cart']",
            run: "click",
        },
        tourUtils.goToCart(),
        {
            content: "Add one quantity",
            trigger: "div[name='website_sale_cart_line_quantity'] button i[data-icon='add']",
            run: "click",
        },
        {
            content: "One quantity should be added",
            trigger: "div[name='website_sale_cart_line_quantity'] input.quantity:value('2')",
        },
        {
            content: "Try to add one quantity",
            trigger: "div[name='website_sale_cart_line_quantity'] button i[data-icon='add']",
            run: "click",
        },
        {
            content: "No quantity should be added",
            trigger: "div[name='website_sale_cart_line_quantity'] input.quantity:value('2')",
        },
    ],
});
