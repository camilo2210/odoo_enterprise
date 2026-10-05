import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("account_reports_annotations", {
    steps: () => [
        //--------------------------------------------------------------------------------------------------------------
        // Annotations
        //--------------------------------------------------------------------------------------------------------------
        // Test the initial status of annotations - There are 2 annotations to display
        {
            content: "Initial annotations",
            trigger: "body:has(.o_content):not(:has(.annotations)",
        },
        {
            content: "Unfold first line",
            trigger: "tr:nth-child(5) td:first()",
            run: "click",
        },
        {
            content: "Wait for the line to load",
            trigger: "tr:nth-child(6).line_level_6"
        },
        {
            content: "Unfold second line",
            trigger: "tr:nth-child(8) td:first()",
            run: "click",
        },
        {
            content: "Wait for the line to load",
            trigger: "tr:nth-child(9).line_level_6"
        },
        {
            content: "Unfold third line",
            trigger: "tr:nth-child(11) td:first()",
            run: "click",
        },
        {
            content: "Wait for the line to load",
            trigger: "tr:nth-child(12).line_level_6"
        },
        {
            content: "Extra Trigger step",
            trigger: "tr:nth-child(6) .o_account_report_chatter_annotated",
        },
        {
            content: "Extra Trigger step",
            trigger: "tr:nth-child(13) .o_account_report_chatter_annotated",
        },
        {
            content: "Check there are two lines annotated initially",
            trigger: ".o_content:has(.btn_annotation.o_account_report_chatter_annotated:count(2))",
        },
        // Test that we can add a new annotation
        {
            content: "Click to show caret option",
            trigger: "tr:nth-child(9) .btn_annotation:not(:visible)",
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
            run: "edit Annotation 121000",
        },
        {
            content: "Submit by logging the note",
            trigger: ".o-mail-Composer-send",
            run: "click",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        {
            content: "Wait for annotation created",
            trigger: "tr:nth-child(9) .o_account_report_chatter_annotated",
        },
        {
            content: "Check there are now three lines annotated",
            trigger: ".o_content:has(.btn_annotation.o_account_report_chatter_annotated:count(3))",
        },
        // Test that we can edit an annotation
        {
            content: "Open second annotated line annotation popover",
            trigger: "tr:nth-child(9) .btn_annotation",
            run: "click",
        },
        {
            content: "Open the message actions menu",
            trigger: ".o-mail-Message:last-child [title='Expand']:not(:visible)",
            run: "click",
        },
        {
            content: "Select the edit button",
            trigger: ".o-mail-Message-moreMenu .btn[name='edit']",
            run: "click",
        },
        {
            content: "Annotate contains previous text value",
            trigger:
                ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea:value(Annotation 121000)",
        },
        {
            content: "Add text to annotate",
            trigger: ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea",
            run: "edit Annotation 121000 edited",
        },
        {
            content: "Annotation is edited",
            trigger:
                ".o-mail-Message:last-child .o-mail-Composer-inputContainer textarea:value(Annotation 121000 edited)",
        },
        {
            content: "Save the annotation",
            trigger: ".o-mail-Message:last-child .btn[data-type='save']",
            run: "click",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        // Test that we dont show there is an annotation if we delete the only annotation of a line
        {
            content: "Open Third annotated line annotation popover",
            trigger: "tr:nth-child(13) .btn_annotation",
            run: "click",
        },
        {
            content: "Wait for the messages to load",
            trigger: ".o-mail-Message",
        },
        {
            content: "Expand the options of the message",
            trigger: ".o-mail-Message:last-child button:has(i.oi[data-icon='more_vert']):not(:visible)",
            run: "click",
        },
        {
            content: "Click on trash can",
            trigger: ".o_popover .o-dropdown-item:has(i[data-icon='delete'])",
            run: "click",
        },
        {
            content: "Wait for the modal to appear",
            trigger: ".modal",
        },
        {
            content: "Confirm deletion of the annotation",
            trigger: ".modal-footer .btn-danger",
            run: "click",
        },
        {
            content: "Close Chatter",
            trigger: ".o_control_panel .btn-secondary[data-tooltip='Chatter']",
            run: "click",
        },
        {
            content: "Check there are now only two lines annotated",
            trigger: "tr:nth-child(13):not(:has([data-icon='mode_comment'].oi-filled))",
        },
        {
            trigger: `.btn_annotation.o_account_report_chatter_annotated:count(2)`,
        },
    ],
});
