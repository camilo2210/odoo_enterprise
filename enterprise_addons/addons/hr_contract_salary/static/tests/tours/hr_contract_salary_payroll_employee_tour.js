import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("hr_contract_salary_payroll_employee_offers_button_tour", {
    //url: "/odoo/employees/<employee_id>",
    steps: () => [
        {
            content:
                "If there are too many smart buttons, open the More dropdown to avoid missing the Generate Offer button",
            trigger: ".o_control_panel_main",
            run: function (actions) {
                const more_smart_button = this.anchor.querySelectorAll(".o_button_more");
                if (more_smart_button.length != 0) {
                    actions.click(".o_button_more");
                }
            },
        },
        {
            trigger: 'button[name="action_generate_offer"]',
            content: 'Click on "Offer" smart button',
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='budget_type'] input:value('Yearly Employer Cost')",
            content: "Yearly Employer Cost as default budget_type",
        },
        {
            trigger: ".o_field_widget[name='salary_amount'] input:value(104,400.00)",
            content: "Check salary_amount",
        },
        ...stepUtils.saveForm(),
        {
            trigger: ".o_back_button",
            content: "Go back to employee form",
            run: "click",
        },
        {
            trigger: "button:contains('Simulation')",
            content: 'Click on "Simulate" button',
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='budget_type'] input:value('Yearly Employer Cost')",
            content: "Yearly Employer Cost as default budget_type",
        },
        {
            trigger: ".o_field_widget[name='salary_amount'] input:value(104,400.00)",
            content: "Check salary_amount",
        },
    ],
});
