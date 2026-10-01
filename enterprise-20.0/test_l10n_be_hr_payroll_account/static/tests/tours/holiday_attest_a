import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("holiday_attest_allocation", {
    steps: () => [
        {
            content: "Open the company switcher",
            trigger: ".o_menu_systray .o_switch_company_menu",
            run: "click",
        },
        {
            content: "Switch to 'My Belgian Company - TEST'",
            trigger: ".dropdown-menu .dropdown-item div span:contains('My Belgian Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Wait for the company switch to complete",
            trigger:
                ".o_menu_systray .o_switch_company_menu span:contains('My Belgian Company - TEST')",
        },
        {
            content: "Open the Employees app",
            trigger: ".o_app[data-menu-xmlid='hr\\.menu_hr_root']",
            run: "click",
        },
        {
            content: "Open Management menu",
            trigger: "[data-menu-xmlid='hr\\.menu_hr_employee_payroll']",
            run: "click",
        },
        {
            content: "Click the New button and create a new employee",
            trigger: ".o-kanban-button-new",
            run: "click",
        },
        {
            content: "Set the employee name to Bananilson da Silva",
            trigger: ".o_field_widget[name='name'] .o_input",
            run: "edit Samuel Lopatin",
        },
        {
            content: "Save the initial employee record",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Go to the Payroll tab on the employee form",
            trigger: ".o_notebook_headers button[name='payroll_information']",
            run: "click",
        },
        {
            content: "Open the contract start date picker",
            trigger: ".o_field_widget[name='contract_date_start'] .o_input",
            run: "click",
        },
        {
            content: "Select a contract start date",
            trigger: ".o_date_item_cell:nth-child(11)",
            run: "click",
        },
        {
            content: "Set the wage to 3123",
            trigger: ".o_field_widget[name='wage'] input.o_input",
            run: "edit 3123",
        },
        {
            content: "Save the payroll information",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Go to the Holiday Attests tab",
            trigger: ".o_notebook_headers li > button:contains('Holiday Attest')",
            run: "click",
        },
        {
            content: "Add a new holiday attestation",
            trigger: "button:contains('Add Holiday Attestation')",
            run: "click",
        },
        {
            content: "Set the remaining holiday days to 12",
            trigger: ".modal .o_field_widget[name='prev_days_earned'] input",
            run: "edit 12",
        },
        {
            content: "Set the simple holiday pay amount 3000",
            trigger: ".modal .o_field_widget[name='prev_simple_holiday_pay_paid'] input",
            run: "edit 3000",
        },
        {
            content: "Set the double holiday pay amount 3000",
            trigger: ".modal .o_field_widget[name='prev_double_holiday_pay_paid'] input",
            run: "edit 3000 && press Tab",
        },
        {
            content: "Verify the computed Simple Holiday Pay cap is 2,885.50",
            trigger: ".modal .o_field_widget[name='simple_holiday_pay_cap']:contains('2,885.50')",
        },
        {
            content: "Verify the computed Double Holiday Pay cap is 2873.16",
            trigger: ".modal .o_field_widget[name='double_holiday_pay_cap']:contains('2,873.16')",
        },
        {
            content: "Verify the computed number of days to allocate is 12",
            trigger: ".modal .o_field_widget[name='days_to_allocate']:contains('12.00')",
        },
        {
            content: "Save and close the allocation dialog",
            trigger: ".o_dialog:not(.o_inactive_modal) .o_form_button_save",
            run: "click",
        },
        {
            content: "Save the employee form to create the holiday attestation",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Wait for the form to be saved",
            trigger: ".o_form_renderer.o_form_saved",
        },
        {
            content: "Open up the holiday attestation again",
            trigger: "article.o_kanban_record",
            run: "click",
        },
        {
            content: "Open the leave allocation dialog",
            trigger: "button[name='action_open_allocation']",
            run: "click",
        },
        {
            content: "Verify the allocation start date is 1st of January 2025",
            trigger:
                ".o_dialog:not(.o_inactive_modal) .o_field_widget[name='date_from'] button:contains('Jan 1, 2025')",
        },
        {
            content: "Verify the allocation end date is 31st of December 2025",
            trigger:
                ".o_dialog:not(.o_inactive_modal) .o_field_widget[name='date_to'] button:contains('Dec 31, 2025')",
        },
        {
            content: "Verify the number of allocated days is 12",
            trigger:
                ".o_dialog:not(.o_inactive_modal) .o_field_widget[name='number_of_days_display'] input",
            run: async function () {
                const expectedValue = "12.00";
                if (this.anchor.value !== expectedValue) {
                    throw new Error(
                        `Expected 'number_of_days_display' to be "${expectedValue}", got "${this.anchor.value}"`
                    );
                }
            },
        },
        {
            content: "Approve the leave allocation",
            trigger: "button[name='action_approve']",
            run: "click",
        },
        {
            content: "Save and close the allocation dialog",
            trigger: ".o_dialog:not(.o_inactive_modal) .o_form_button_save",
            run: "click",
        },
        {
            content: "Save and close the holiday attestation dialog",
            trigger: ".modal .o_form_button_save",
            run: "click",
        },
        {
            content: "Save the employee record",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Wait for the form to be saved",
            trigger: ".o_form_renderer.o_form_saved",
        },
        {
            content: "Return to the dashboard",
            trigger: "a[href='/odoo']",
            run: "click",
        },
    ],
});
