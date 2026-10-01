import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("hr_payroll_view_header_buttons_tour", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Payroll app",
            trigger: '.o_app[data-menu-xmlid="hr_payroll.menu_hr_payroll_root"]',
            run: "click",
        },
        {
            content: "Open Payslips Menu",
            trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_payslips"]',
            run: "click",
        },
        {
            content: "Click Payslips",
            trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_employee_payslips"]',
            run: "click",
        },
        {
            content: "Select draft payslip",
            trigger: ".o_data_row input",
            run: "check",
        },
        {
            content: "Check header buttons and click on compute",
            trigger: ".o_selection_container:has(button[name='compute_sheet'])",
            run: (actions) => {
                if (
                    actions.anchor.querySelector(
                        ".o_selection_container > button[name='action_print_payslip']"
                    )
                ) {
                    return actions.click("button[name='compute_sheet']");
                } else {
                    throw new Error("Compute Sheet and Print buttons should be displayed");
                }
            },
        },
        {
            content: "Waiting for the end of the compute action",
            trigger: ".o_searchview",
        },
        {
            content: "Select draft payslip",
            trigger: ".o_data_row input",
            run: "check",
        },
        {
            content: "Check header buttons and click on validate",
            trigger: ".o_selection_container:has(button[name='action_validate'])",
            run: (actions) => {
                if (
                    actions.anchor.querySelector(
                        ".o_selection_container > button[name='action_print_payslip']"
                    )
                ) {
                    return actions.click("button[name='action_validate']");
                } else {
                    throw new Error("Validate and Print buttons should be displayed");
                }
            },
        },
        {
            content: "Waiting for the end of the done action",
            trigger: ".o_searchview",
        },
        {
            content: "Select draft payslip",
            trigger: ".o_data_row input",
            run: "check",
        },
        {
            content: "Check header buttons and click on mark as paid",
            trigger: ".o_selection_container:has(button[name='action_payslip_paid'])",
            run: (actions) => {
                if (
                    actions.anchor.querySelector(
                        ".o_selection_container > button[name='action_print_payslip']"
                    )
                ) {
                    return actions.click("button[name='action_payslip_paid']");
                } else {
                    throw new Error("Mark as paid and Print buttons should be displayed");
                }
            },
        },
    ],
});
