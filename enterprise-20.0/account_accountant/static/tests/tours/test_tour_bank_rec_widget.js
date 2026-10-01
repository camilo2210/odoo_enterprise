import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { accountTourSteps } from "@account/js/tours/account";

registry.category("web_tour.tours").add("account_accountant_bank_rec_widget", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        ...accountTourSteps.goToAccountMenu("Open the accounting module"),

        {
            content: "Open the bank reconciliation widget",
            trigger: "a.oe_kanban_action span:contains('Bank')",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_kanban_renderer",
        },
        {
            content: "Create New statement",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_quick_create",
        },
        {
            content: "Write Label",
            trigger: "div[name='payment_ref'] input",
            run: "edit test",
        },
        {
            content: "Add a amount",
            trigger: "div[name='amount'] input",
            run: "edit 100",
        },
        {
            content: "Save & close",
            trigger: "div.button_group button.o_kanban_edit",
            run: "click",
        },
        {
            content: "Statement is created",
            trigger: "div[name='bank_statement_line']",
        },
        {
            content: "Unfold statement line",
            trigger: "div[name='bank_statement_line']",
            run: "click",
        },
        {
            content: "line is unfolded",
            trigger: "div.o_button_line",
        },
        {
            content: "Set Partner",
            trigger: "button.set-partner-btn",
            run: "click",
        },
        {
            content: "Search view is opened",
            trigger: "div.modal-dialog",
        },
        {
            content: "Select first partner",
            trigger: "tbody > tr > td[name='display_name']",
            run: "click",
        },
        {
            content: "Partner is set",
            trigger: "span[name='statement_line_partner_name']",
        },
        {
            content: "Fold statement line",
            trigger: "div[name='bank_statement_line']",
            run: "click",
        },
        {
            content: "Statement line is reconciled because move with same partner and amount",
            trigger: "div[name='reconciled_line_name']",
        },
        {
            content: "Create New statement",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_quick_create",
        },
        {
            content: "Write Label",
            trigger: "div[name='payment_ref'] input",
            run: "edit test",
        },
        {
            content: "Add a amount",
            trigger: "div[name='amount'] input",
            run: "edit 150",
        },
        {
            content: "Save & close",
            trigger: "div.button_group button.o_kanban_edit",
            run: "click",
        },
        {
            content: "Open Ellipsis button",
            trigger: "button.btn-secondary i[data-icon='more_vert']",
            run: "click",
        },
        {
            content: "Reconcile button",
            trigger: "span.btn-link:contains('Reconcile')",
            run: "click",
        },
        {
            content: "Search view is opened",
            trigger: "div.modal-dialog",
        },
        {
            content: "Select first move line",
            trigger: "tbody > tr > td[name='partner_id']",
            run: "click",
        },
        {
            content: "Statement line is reconciled",
            trigger: "div[name='reconciled_line_name']",
        },
        // ensure statement can be added for multiple statement lines at once
        {
            content: "Switch to list view",
            trigger: "button.o_switch_view.o_list",
            run: "click",
        },
        {
            content: "Select the statement lines",
            trigger: "div.o-checkbox",
            run: "click",
        },
        {
            content: "Open the Many2One to set statement",
            trigger: "td.o_bank_rec_list_many2one_multi_id_cell",
            run: "click",
        },
        {
            content: "Search for the created statement",
            trigger: "input.o-autocomplete--input",
            run: "click",
        },
        {
            content: "Select the created statement",
            trigger: "a.dropdown-item:contains('test')",
            run: "click",
        },
        {
            content: "Update setting statement on both lines",
            trigger: "button.btn-primary:contains('Update')",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("account_accountant_set_partner_with_child_contact", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        ...accountTourSteps.goToAccountMenu("Open the accounting module"),

        {
            content: "Open the bank reconciliation widget",
            trigger: "a.oe_kanban_action span:contains('Bank')",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_kanban_renderer",
        },
        {
            content: "Create New statement",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_quick_create",
        },
        {
            content: "Write Label",
            trigger: "div[name='payment_ref'] input",
            run: "edit test",
        },
        {
            content: "Add a amount",
            trigger: "div[name='amount'] input",
            run: "edit 100",
        },
        {
            content: "Save & close",
            trigger: "div.button_group button.o_kanban_edit",
            run: "click",
        },
        {
            content: "Statement is created",
            trigger: "div[name='bank_statement_line']",
        },
        {
            content: "Set Partner",
            trigger: "button.set-partner-btn",
            run: "click",
        },
        {
            content: "Search view is opened",
            trigger: "div.modal-dialog",
        },
        {
            content: "Select partner",
            trigger: "body:not(:has(tbody > tr > td[name='display_name']:contains('test child contact')))",
        },
    ]
});

registry.category("web_tour.tours").add("account_accountant_bank_reconciliation_ui_context_keys", {
    steps: () => [
        {
            trigger: "div.o_bank_reconciliation_kanban_renderer",
        },
        {
            content: "Create New statement",
            trigger: "button.o-kanban-button-new",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_quick_create",
        },
        {
            content: "Write Label",
            trigger: "div[name='payment_ref'] input",
            run: "edit test",
        },
        {
            content: "Add a amount",
            trigger: "div[name='amount'] input",
            run: "edit 100",
        },
        {
            content: "Save & close",
            trigger: "div.button_group button.o_kanban_edit",
            run: "click",
        },
        {
            content: "Statement is created",
            trigger: "div[name='bank_statement_line']",
        },
        {
            content: "Statement line is reconciled",
            trigger: "div[name='reconciled_line_name']",
        },
        {
            content: "Upload button is not shown for a synchronized journal (Kanban View)",
            trigger: "div.o_control_panel_main_buttons:not(:has(.o_button_upload_bill))",
        },
        {
            content: "Switch to List View",
            trigger: "button.o_switch_view.o_list",
            run: "click",
        },
        {
            content: "Upload button is not shown for a synchronized journal (List View)",
            trigger: "div.o_control_panel_main_buttons:not(:has(.o_button_upload_bill))",
        },
    ]
});
