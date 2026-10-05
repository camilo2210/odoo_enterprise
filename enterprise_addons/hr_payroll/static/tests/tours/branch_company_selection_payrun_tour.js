import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add('branch_company_selection_payrun_tour', {
    steps: () => [
    stepUtils.showAppsMenuItem(),
    {
        content: "Open company switcher",
        trigger: ".o_menu_systray .o_switch_company_menu",
        run: "click",
    },
    {
        content: "Select branch company",
        trigger: ".o_switch_company_menu_dropdown [aria-label='Branch Company']",
        run: "click",
    },
    {
        content: "Click confirm to apply company changes",
        trigger: ".o_switch_company_menu_buttons button:contains('Confirm')",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Open payroll app",
        trigger: '.o_app[data-menu-xmlid="hr_payroll.menu_hr_payroll_root"]',
        run: "click",
    },
    {
        content: "Click payslips",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_payslips"]',
        run: "click",
    },
    {
        content: "Click pay runs",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payslip_run"]',
        run: "click",
    },
    {
        content: "Click on the new button to start a pay run",
        trigger: ".o_control_panel_main_buttons button.o-kanban-button-new",
        run: "click",
    },
    {
        content: "Click company dropdown field",
        trigger: "[name='company_id'] input",
        run: "click",
    },
    {
        content: "Select branch company from autocomplete list",
        trigger: ".ui-autocomplete .ui-menu-item a:contains('Branch Company')",
        run: "click",
    },
    {
        content: "Click pay structure field",
        trigger: "[name='structure_id'] input",
        run: "click",
    },
    {
        content: "Select Test Salary Structure salary structure from autocomplete list",
        trigger: ".ui-autocomplete .ui-menu-item a:contains('Test Salary Structure')",
        run: "click",
    },
    {
        content: "Click the continue button to proceed with the pay run", 
        trigger: ".modal-footer button:contains('Continue')",
        run: "click",
    },
    {
        content: "Select the record corresponding to test Faruk",
        trigger: ".o_list_view tbody tr:has(td[name='name']:contains('test Faruk')) .o_list_record_selector",
        run: "click",
    },
    {
        content: "Click the select button to proceed with the pay run",
        trigger: ".modal-footer button.btn-primary:enabled:contains('Select')",
        run: "click",
    },
    {
        content: "Wait for the payrun dialog to close",
        trigger: "body:not(:has(.modal-content))",
    },
    {
        content: "Wait for payslips list after selection",
        trigger: ".o_list_view .o_data_row",
    },
    {
        content: "Click the optional columns dropdown button",
        trigger: "th.o_list_actions_header .o_optional_columns_dropdown_toggle",
        run: "click",
    },
    {
        content: "Select company from the optional columns list",
        trigger: ".o_popover .dropdown-item:contains('Company')",
        run: "click",
    },
    {
        content: "Verify that the company column displays branch company",
        trigger: ".o_list_view tbody tr:has(td[name='employee_id']:contains('test Faruk')) td:contains('Branch Company')",
    },
]});
