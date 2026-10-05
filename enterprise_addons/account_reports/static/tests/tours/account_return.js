import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_return_flow_tax_return", {
    steps: () => [
        {
            content: "Open Tax Returns",
            trigger: "button[name='account_reports.action_server_open_view_account_return']",
            run: "click",
        },
        {
            content: "Check First Group Header",
            trigger: ".o_account_return_padding:text(December 2023)",
        },
        {
            content: "Open Return",
            trigger: ".o_account-return-kanban .o_kanban_record span:contains('DUMMY_TAX')",
            run: "click",
        },
        {
            content: "Wait for Checks",
            trigger: ".kanban_checks_view",
        },
        {
            content: "Approve Company Data",
            trigger: "div.o_field_account_review_state_selection_badge > button.btn-outline-danger",
            run: "click",
        },
        {
            content: "Select Valid Ckeck Status",
            trigger: "div.o_popover > span:nth-child(3)",
            run: "click",
        },
        {
            content: "Validate Return",
            trigger: "button[name='action_validate']",
            run: "click",
        },
        {
            content: "Verify State Advancement",
            trigger: ".o_account_return_state > div.active:count(1)",
        },
        {
            content: "Open Tax Return Report",
            trigger: "button.btn-primary[name='action_open_report']",
            run: "click",
        },
        {
            content: "Wait for report to be shown",
            trigger: ".account_report",
        },
        {
            content: "Go back To Return",
            trigger: ".o_breadcrumb .breadcrumb-item a",
            run: "click",
        },
        {
            content: "Submit Return",
            trigger: "button[name='action_submit']",
            run: "click",
        },
        {
            content: "Verify State Advancement",
            trigger: ".o_account_return_state > div.active:count(3)",
        },
    ],
});
