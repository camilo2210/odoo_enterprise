import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { accountTourSteps } from "@account/js/tours/account";

registry.category("web_tour.tours").add("l10n_mx_edi_bank_rec_factoring", {
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
            content: "Unfold Factoring Statement Line",
            trigger: "div[name='bank_statement_line'] div.o_payment_ref span:contains(Factoring)",
            run: "click",
        },
        {
            content: "line is unfolded",
            trigger: "div.o_button_line",
        },
        {
            content: "Reconcile button",
            trigger: "button.reconcile-btn",
            run: "click",
        },
        {
            content: "Search view is opened",
            trigger: "div.modal-dialog",
        },
        {
            content: "Factoring button is disabled",
            trigger: "button.o_factoring_button[disabled]",
        },
        {
            content: "Select line",
            trigger: "tbody > tr > td > div.o-checkbox > input",
            run: "check",
        },
        {
            content: "Click Factoring button",
            trigger: "button.o_factoring_button:not([disabled])",
            run: "click",
        },
        {
            content: "Factoring Wizard is open",
            trigger: "h4.modal-title:contains('Distribute Payment')",
        },
        {
            content: "Statement Amount Due",
            trigger: "div[name='amount_residual']:contains('$ 900.00')",
        },
        {
            content: "Click amount to pay",
            trigger: "td[name='amount_trans_currency']",
            run: "click",
        },
        {
            content: "Set amount to pay",
            trigger: "td[name='amount_trans_currency'] input",
            run: "edit 900.00",
        },
        {
            content: "Click compensation",
            trigger: "td[name='compensation_amount_trans_currency']",
            run: "click",
        },
        {
            content: "Set amount to pay",
            trigger: "td[name='compensation_amount_trans_currency'] input",
            run: "edit 100.00",
        },
        {
            content: "No due to settle",
            trigger: "div[name='amount_residual']:contains('$ 0.00')",
        },
        {
            content: "Register factoring payments",
            trigger: "button.o_form_button_save",
            run: "click",
        },
        {
            content: "Statement line is reconciled",
            trigger: "div[name='reconciled_line_name']",
        },
        {
            content: "Unfold Reconciled Factoring Statement Line",
            trigger: "i[data-icon='keyboard_arrow_down']",
            run: "click",
        },
        {
            content: "line is unfolded",
            trigger: "i[data-icon='keyboard_arrow_up']",
        },
        {
            content: "A payment line was created",
            trigger: "div.o_grid_container span:contains('$ -900.00')",
        },
        {
            content: "A compensation line was created",
            trigger: "div.o_grid_container span:contains('$ -100.00')",
        },
        {
            content: "A factoring cost line was created",
            trigger: "div.o_grid_container span:contains('$ 100.00')",
        },
    ],
});
