import { registry } from '@web/core/registry';
import { stepUtils } from '@web_tour/tour_utils';

registry.category('web_tour.tours').add('sale_renting_product_display', {
    steps: () => [
        ...stepUtils.goToAppSteps('sale_renting.rental_menu_root', "Open the rental app"),
        {
            content: "Create a new SO",
            trigger: '.o_list_button_add',
            run: 'click',
        },
        {
            content: "Add a product",
            trigger: '.o_field_sol_o2m .o_field_x2many_list_row_add button:first',
            run: 'click'
        },
        {
            content: "Enter partial product name",
            trigger: '.o_field_sol_label_text textarea.o_input',
            run: 'fill product:'
        },
        {
            content: "Search for a product displayed in sale and rental",
            trigger: '.o-autocomplete .dropdown-item:contains("sale_ok=True,bool(rent_periodicity)=True")',
        },
        {
            content: "Search for non displayed product",
            trigger: '.o-autocomplete .dropdown-item:not(:contains("bool(rent_periodicity)=False"))',
        },
        {
            content: "Search for non displayed product",
            trigger: '.o-autocomplete .dropdown-item:not(:contains("sale_ok=False"))',
        },
        {
            content: "discard the form",
            trigger: ".o_form_button_cancel",
            run: "click"
        },
        {
            content: "wait for cancellation to complete",
            trigger: ".o_view_controller.o_list_view, .o_form_view > div > main > .o_form_readonly, .o_form_view > div > main > .o_form_saved"
        },
    ],
});

registry.category('web_tour.tours').add('sale_product_display', {
    steps: () => [
        ...stepUtils.goToAppSteps('sale.sale_menu_root', "Open the sale app"),
        {
            content: "Create a new SO",
            trigger: '.o_list_button_add',
            run: 'click',
        },
        {
            content: "Add a product",
            trigger: '.o_field_sol_o2m .o_field_x2many_list_row_add button:first',
            run: 'click'
        },
        {
            content: "Enter partial product name",
            trigger: '.o_field_sol_label_text textarea.o_input',
            run: 'fill product:'
        },
        {
            content: "Search for a product displayed in sale and rental",
            trigger: '.o-autocomplete .dropdown-item:contains("sale_ok=True,bool(rent_periodicity)=False")',
        },
        {
            content: "Search for a product displayed in rental only",
            trigger: '.o-autocomplete .dropdown-item:not(:contains("sale_ok=True,bool(rent_periodicity)=True"))',
        },
        {
            content: "Search for non displayed product",
            trigger: '.o-autocomplete .dropdown-item:not(:contains("sale_ok=False"))',
        },
        {
            content: "discard the form",
            trigger: ".o_form_button_cancel",
            run: "click"
        },
        {
            content: "wait for cancellation to complete",
            trigger: ".o_view_controller.o_list_view, .o_form_view > div > main > .o_form_readonly, .o_form_view > div > main > .o_form_saved"
        },
    ],
});
