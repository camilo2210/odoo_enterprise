import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_audit", {
    steps: () => [
        {
            trigger: "button.o-kanban-button-new",
            content: "Create a new Audit",
            run: "click",
        },
        {
            isActive: ["auto"],
            trigger: ".modal",
            content: "Wait for the modal to open",
        },
        {
            trigger: "div[name='return_type_id'] .o_selection_badge:contains('Audit')",
            content: "Select the Return Type",
            run: "click",
        },
        {
            trigger: ".modal-footer button.btn-primary",
            content: "Generate the Audit",
            run: "click",
        },
        {
            trigger: "a[data-tooltip='Back to \"Working Files\"']",
            content: "Back to the Audit Kanban",
            run: "click",
        },
        {
            trigger: ".o_account_return_audit_kanban_view .o_kanban_record:nth-child(1)",
            content: "Open the working file",
            run: "click",
        },
        {
            trigger: ".o_embedded_actions button:contains('Balances')",
            content: "Switch to the 'Balances' tab",
            run: "click",
        },
        {
            trigger: ".o_data_row .o_data_cell",
            content: "Open the chatter for the first row",
            run: "click",
        },
        {
            content: "Add a log note",
            trigger: ".o-mail-Chatter-logNote",
            run: "click",
        },
        {
            content: "Add text to annotate",
            trigger: ".o-mail-Composer-inputContainer textarea",
            run: "edit Annotation from the audit",
        },
        {
            content: "Submit by logging the note",
            trigger: ".o-mail-Composer-send",
            run: "click",
        },
        {
            content: "Annotation is posted",
            trigger:
                ".o-mail-Message:last-child .o-mail-Message-textContent:text(Annotation from the audit)",
        },
        {
            trigger:
                ".o_account_reports_annotation:contains(/^Annotated for [0-9]{2}/[0-9]{2}/[0-9]{4}$/)",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        {
            content: "Check that the chatter is closed",
            trigger: ".o_account_report_chatter:not(:visible)",
        },
    ],
});
