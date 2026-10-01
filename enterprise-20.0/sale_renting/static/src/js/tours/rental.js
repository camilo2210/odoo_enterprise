import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add("rental_tour", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            trigger: '.o_app[data-menu-xmlid="sale_renting.rental_menu_root"]',
            content: markup(_t("Want to <b>rent products</b>? \n Let's discover Odoo Rental App.")),
            run: "click",
        },
        {
            trigger: '.dropdown[data-menu-xmlid="sale_renting.menu_catalog"]',
            content: _t("At first, let's create some products to rent."),
            run: "click",
        },
        {
            trigger: '.dropdown-item[data-menu-xmlid="sale_renting.menu_catalog_products"]',
            content: _t("At first, let's create some products to rent."),
            tooltipPosition: "right",
            run: "click",
        },
        {
            trigger: ".o_breadcrumb .active:contains(Products)",
        },
        {
            trigger: ".o-kanban-button-new",
            content: _t("Click here to set up your first rental product."),
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='name'] textarea",
            content: _t("Enter the product name."),
            run: "edit Test",
        },
        {
            trigger: ".nav-item button.nav-link:contains(Sales)",
            content: _t("The rental configuration is available here."),
            tooltipPosition: "top",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='rent_periodicity'] input",
            content: _t("Select the periodicity at which you want to rent this product."),
            run: "click",
        },
        {
            trigger: ".o_select_menu_item[data-choice-index='0']",
            run: "click",
        },
        {
            trigger: 'button[data-menu-xmlid="sale_renting.rental_order_menu"]:enabled',
            content: _t("Let's now create an order."),
            run: "click",
        },
        {
            trigger: '.dropdown-item[data-menu-xmlid="sale_renting.rental_orders_all"]',
            content: _t("Go to the orders menu."),
            run: "click",
        },
        {
            trigger: ".o_list_button_add",
            content: _t("Click here to create a new quotation."),
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=partner_id] input",
            content: _t("Create or select a customer here."),
            run: "edit Agrolait",
        },
        {
            content: _t("Select the customer in the list."),
            trigger: ".o_field_widget[name=partner_id] .dropdown-item:not(.o_loading)",
            run: "click",
        },
        {
            trigger: "button:contains('Add Line')",
            content: _t("Click here to start filling the quotation."),
            run: "click",
        },
        {
            trigger: ".o_field_sol_label_text textarea.o_input",
            content: _t("Select your rental product."),
            run: "edit Test",
        },
        {
            content: _t("Select the product in the list."),
            trigger: ".ui-menu-item a:contains('Test')",
            run: "click",
        },
        {
            trigger: ".o_field_sol_label_text textarea.o_has_product:value(Test\n1 hour)",
        },
        {
            trigger: "button[name=action_confirm]:enabled",
            content: _t("Confirm the order when the customer agrees with the terms."),
            run: "click",
        },
        {
            trigger: ".o_sale_order",
        },
        {
            trigger: "button[name=action_open_pickup]:enabled",
            content: _t("Click here to register the pickup."),
            run: "click",
        },
        {
            trigger: "button[name='apply']",
            content: _t("Validate the operation after checking the picked-up quantities."),
            run: "click",
        },
        {
            trigger: ".o_sale_order",
        },
        {
            trigger: "button[name='action_open_return']:enabled",
            content: _t("Once the rental is done, you can register the return."),
            run: "click",
        },
        {
            trigger: "button[name='apply']:enabled",
            content: _t("Confirm the returned quantities and hit Validate."),
            run: "click",
        },
        {
            trigger: '.text-bg-default:contains("Returned")',
            content: _t("You're done with your fist rental. Congratulations!"),
        },
    ],
});
