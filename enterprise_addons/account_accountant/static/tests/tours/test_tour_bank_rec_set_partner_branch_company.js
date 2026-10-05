import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { accountTourSteps } from "@account/js/tours/account";

/**
 * Verifies that when setting a partner on a statement line from a branch company,
 * contacts owned by the parent company are visible in the lookup dialog.
 *
 * The partner lookup domain uses `parent_of` so that contacts belonging to any
 * ancestor company of the statement line's company are included.
 */
registry.category("web_tour.tours").add("account_accountant_bank_rec_set_partner_branch_company", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        ...accountTourSteps.goToAccountMenu("Open the accounting module"),
        {
            content: "Open the branch bank reconciliation widget",
            trigger: "a.oe_kanban_action span:contains('Branch Bank')",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_kanban_renderer",
        },
        {
            content: "Unfold the statement line",
            trigger: "div[name='bank_statement_line']",
            run: "click",
        },
        {
            content: "Line is unfolded",
            trigger: "div.o_button_line",
        },
        {
            content: "Open the Set Partner dialog",
            trigger: "button.set-partner-btn",
            run: "click",
        },
        {
            content: "Search dialog is open",
            trigger: "div.modal-dialog",
        },
        {
            // The parent company's contact must appear even though the statement line
            // belongs to a branch company — this validates the `parent_of` domain fix.
            content: "Parent company contact is visible in the results",
            trigger: "tbody > tr > td[name='display_name']:contains('AAAA Parent Partner')",
        },
        {
            content: "Select the parent company contact",
            trigger: "tbody > tr > td[name='display_name']:contains('AAAA Parent Partner')",
            run: "click",
        },
        {
            content: "Partner is set on the statement line",
            trigger: "span[name='statement_line_partner_name']:contains('AAAA Parent Partner')",
        },
    ],
});
