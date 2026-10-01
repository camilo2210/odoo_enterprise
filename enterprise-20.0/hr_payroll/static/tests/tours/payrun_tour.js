import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add('payroll_payrun_tour', {
    steps: () => [
    stepUtils.showAppsMenuItem(),
    {
        content: "Log into US Company",
        trigger: ".o_menu_systray .o_switch_company_menu",
        run: "click",
    },
    {
        content: "Log into US Company",
        trigger:
            ".o-dropdown--menu .dropdown-item div span:contains('Company US')",
        run: "click",
        expectUnloadPage: true,
    },
    {
        trigger:
            ".o_menu_systray .o_switch_company_menu span:contains('Company US')",
    },
    {
        content: "Open payroll app",
        trigger: '.o_app[data-menu-xmlid="hr_payroll.menu_hr_payroll_root"]',
        run: "click",
    },
    {
        content: "Click Payslips",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_payslips"]',
        run: "click",
    },
    {
        content: "Click Pay Runs",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payslip_run"]',
        run: "click",
    },
    {
        content: "Open the Pay Run",
        trigger: '.o_kanban_record',
        run: "click",
    },
    {
        content: "Check that the payrun cost is correctly displayed",
        trigger: '.o_payrun_metrics .o_payrun_metric_value:not(:contains("$0.00"))',
    },
    {
        content: "Check that the payrun net is correctly displayed",
        trigger: '.o_payrun_metrics .o_payrun_metric_value:not(:contains("$0.00"))',
    },
    {
        content: "confirm the payrun",
        trigger: ".btn[name='action_validate']",
        run: "click",
    },
    {
        content: "Confirm the validation",
        trigger: ".modal-footer button.btn-primary:contains('Ok')",
        run: "click",
    },
    {
        content: "Mark the payrun as paid",
        trigger: ".btn[name='action_paid']",
        run: "click",
    },
    {
        id: "submit_end",
        content: "Go back to Pay Runs",
        trigger: ".o_back_button",
        run: "click",
    },
    {
        content: "Wait for Payrun View",
        trigger: "button.o_switch_view.o_kanban.active",
    },
    {
        content: "Create New Payrun",
        trigger: "button.btn-primary:contains('New')",
        run: "click",
    },
    {
        content: "Open select Salary Structure",
        trigger: "input[id*=structure_id]",
        run: "click",
    },
    {
        content: "Select the Salary Structure for Software Developer",
        trigger: '.o_field_many2one_selection .dropdown-item:contains("Salary Structure for Software Developer")',
        run: "click",
    },
    {
        content: "Click continue",
        trigger: "button.btn-primary:contains('Continue')",
        run: "click",
    },
    {
        content: "Employee Richard should be in the list",
        trigger: 'tbody tr:contains("Richard")',
    },
    {
        content: "Employee test amah should be in the list",
        trigger: 'tbody tr:contains("test amah")',
    },
    {
        content: "Select all employees",
        trigger: 'thead tr th.o_list_record_selector',
        run: "click",
    },
    {
        content: "Click Select",
        trigger: 'footer button:contains("Select"):not(disabled)',
        run: "click",
    },
    {
        content: "Open chatter panel",
        trigger: ".o_control_panel_navigation > button",
        run: "click",
    },
    {
        content: "Wait for the chatter to load",
        trigger: ".o_payrun_chatter_container",
    },
    {
        trigger: ".o-mail-Chatter-logNote",
        run: "click",
    },
    {
        trigger: ".o-mail-Composer-input",
        run: "edit Chatter from payrun employees",
    },
    {
        trigger: ".o-mail-Composer-send",
        run: "click",
    },
    {
        content: "Chatter Message",
        trigger: ".o-mail-Message-textContent:contains('Chatter from payrun employees')",
    },
    {
        content: "Check payslip amount",
        trigger: 'tbody tr td[name="basic_wage"]:not(:text(0.00))',
    },
    {
        content: "Net should be computed.",
        trigger: `tbody tr td[name="net_wage"]:not(:text(0.00))`,
    },
    {
        trigger: ".o-mail-Chatter-logNote",
        run: "click",
    },
    {
        trigger: ".o-mail-Composer-input",
        run: "edit Chatter from payrun payslips",
    },
    {
        trigger: ".o-mail-Composer-send",
        run: "click",
    },
    {
        content: "Chatter Message",
        trigger: ".o-mail-Message-textContent:contains('Chatter from payrun payslips')",
    },
    {
        trigger: ".btn[name='action_validate']",
        run: "click",
    },
    {
        trigger: ".o_technical_modal button:nth-child(1)",
        run: "click",
    },
    {
        content: "Wait for payslips to be confirmed",
        trigger: ".btn[name='action_payment_report'], .btn[name='action_paid']",
    },
    {
        content: "Chatter Update Status",
        trigger: ".o-mail-Message-textContent:contains('Done')",
    },
    {
        trigger: ".btn[name='action_paid']",
        run: "click",
    },
    {
        content: "Wait for payrun to be marked as paid",
        trigger: ".btn[name='action_unpaid']",
    },
    {
        content: "Chatter Update Status",
        trigger: ".o-mail-Message-textContent:contains('Paid')",
    },
]});
