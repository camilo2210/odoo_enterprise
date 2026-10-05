import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("hr_contract_salary_hidden_simulation_offer_tour", {
    steps: () => [
        {
            content: "Open Payroll App",
            trigger: ".o_app:contains('Payroll')",
            run: "click",
        },
        {
            content: "Open Employees Menu",
            trigger: ".o_menu_sections button.dropdown-toggle:contains('Employees')",
            run: "click",
        },
        {
            content: "Click Salary Calculator",
            trigger: ".dropdown-item:contains('Salary Calculator')",
            run: "click",
        },
        {
            content: "Select employee",
            trigger: "div[name='employee_id'] input",
            run: "edit Simulation Test Employee",
        },
        {
            content: "Select employee from autocomplete",
            trigger: ".o-autocomplete--dropdown-item span:contains('Simulation Test Employee')",
            run: "click",
        },
        {
            content: "Enter salary amount",
            trigger: "div[name='salary_amount'] input",
            run: "edit 120000",
        },
        {
            content: "Wait for the backend computation to finish",
            trigger: "[name='yearly_employer_cost']:contains('120')",
        },
        {
            content: "Click Close Button",
            trigger: ".o_technical_modal footer button:contains('Close')",
            run: "click",
        },
        {
            content: "Go back to Home",
            trigger: ".o_menu_toggle, .o_menu_brand",
            run: "click",
        },
        {
            content: "Open Recruitment App",
            trigger: ".o_app:contains('Recruitment')",
            run: "click",
        },
        {
            content: "Open Applications Menu",
            trigger: ".o_menu_sections button.dropdown-toggle:contains('Applications')",
            run: "click",
        },
        {
            content: "Open Offers",
            trigger: ".dropdown-item:contains('Offers')",
            run: "click",
        },
        {
            content: 'Write Simulation Test Employee to Search Bar',
            trigger: '.o_searchview_input:visible',
            run: 'edit Simulation Test Employee',
        },
        {
            content: "Select Employee search field",
            trigger: ".o_searchview_autocomplete .o-dropdown-item:contains('Employee')",
            run: "click",
        },
        {
            content: "Ensure simulation offer is hidden",
            trigger: ".o_nocontent_help",
        },
    ],
});
