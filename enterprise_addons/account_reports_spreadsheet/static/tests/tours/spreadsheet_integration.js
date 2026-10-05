import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_report_spreadsheet_integration", {
    steps: () => [
        {
            content: "Open Review menu",
            trigger: "button[data-menu-xmlid='account.account_audit_menu']",
            run: "click",
        },
        {
            content: "Click Working Files",
            trigger: "a[data-menu-xmlid='account_reports.menu_action_working_files']",
            run: "click",
        },
        {
            content: "Click New button",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            content: "Click Generate Return button",
            trigger: "button[name='action_create_manual_account_returns']",
            run: "click",
        },
        {
            content: "Open Balances",
            trigger: "button span:contains('Balances')",
            run: "click",
        },
        {
            content: "Select Line 1",
            trigger: "tbody input[type='checkbox']",
            run: "check",
        },
        {
            content: "Click Actions button",
            trigger: "button span:contains('Actions')",
            run: "click",
        },
        {
            content: "Click Insert in spreadsheet",
            trigger: "span.o-dropdown-item:contains('Insert in spreadsheet')",
            run: "click",
        },
        {
            content: "Insert Balances into spreadsheet",
            trigger: "footer.modal-footer button:contains('Insert')",
            run: "click",
        },
        {
            content: "Check sheet is present and alone",
            trigger: ".o-sheet-list > :only-child",
        },
        {
            content: "Check sheet name",
            trigger: ".o-sheet-list .o-sheet-name:contains('Balances')",
        },
        {
            content: "Click Breadcrumb",
            trigger: ".o-sp-breadcrumb",
            run: "click",
        },
        {
            content: "Open Accounting menu",
            trigger: "button[data-menu-xmlid='account.menu_finance_entries']",
            run: "click",
        },
        {
            content: "Click Journal Entries",
            trigger: "a[data-menu-xmlid='account.menu_action_move_journal_line_form']",
            run: "click",
        },
        {
            content: "Wait for the view to be loaded",
            trigger: ".o_last_breadcrumb_item span:contains('Journal Entries')",
        },
        {
            content: "Select first element",
            trigger: "tbody input[type='checkbox']",
            run: "check",
        },
        {
            content: "Click Actions button",
            trigger: "button span:contains('Actions')",
            run: "click",
        },
        {
            content: "Click Insert in spreadsheet",
            trigger: "span.o-dropdown-item:contains('Insert in spreadsheet')",
            run: "click",
        },
        {
            content: "Click working file tab",
            trigger: ".nav-tabs button:contains('Working Files')",
            run: "click",
        },
        {
            content: "Click Input",
            trigger: "input[id='working_file_input_field']",
            run: "click",
        },
        {
            content: "Click Input",
            trigger: "a[id='working_file_input_field_0_0']",
            run: "click",
        },
        {
            content: "Set name",
            trigger: "input[id='name']",
            run: "edit Journal Entries",
        },
        {
            content: "Insert Balances into spreadsheet",
            trigger: "footer.modal-footer button:contains('Insert')",
            run: "click",
        },
        {
            content: "Check new sheet is present and there are 2 sheets at maximum",
            trigger: ".o-sheet-list > :nth-child(2):last-child",
        },
        {
            content: "Check sheet name",
            trigger: ".o-sheet-list > :nth-child(1) .o-sheet-name:contains('Balances')",
        },
        {
            content: "Check sheet name",
            trigger: ".o-sheet-list > :nth-child(2) .o-sheet-name:contains('Journal Entries')",
        },
    ],
});
