import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("hr_payroll_form_view_date_input_tour", {
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
            content: "Create a new Payslip",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Open employee list",
            trigger: "#employee_id_0",
            run: "click",
        },
        {
            content: "Assign employee",
            trigger: "#employee_id_0_0_0",
            run: "click",
        },
        {
            content: "Open end date widget",
            trigger: "#date_to_0",
            run: "click",
        },
        {
            content: "Wait the popover is shown",
            trigger: "body:has(.o_popover .o_datetime_picker)",
        },
        {
            content: "Clear end date",
            trigger: "#date_to_0",
            run: "clear",
        },
        {
            content: "Click outside",
            trigger: ".o_form_sheet",
            run: "click",
        },
        ...stepUtils.discardForm(),
    ],
});
