import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { markup } from "@odoo/owl";

// common steps
function getCommonSteps() {
    return [
        {
            trigger: '.o_app[data-menu-xmlid="documents.menu_root"]',
            content: markup(
                _t("Want to become a <b>paperless company</b>? Let's discover Odoo Documents.")
            ),
            tooltipPosition: "bottom",
            run: "click",
        },
        {
            trigger: ".o_search_panel_label:contains('" + _t("Company") + "')",
            content: markup(
                _t("<b>Go to 'Company'</b> to view all your company's files and folders.")
            ),
            run: "click",
        },
        {
            trigger: ".o_documents_kanban_view .btn-primary",
            content: markup(_t("Click on <b>'New'</b> to create a new folder")),
            run: "click",
        },
        {
            trigger: ".o-dropdown-item.o_documents_kanban_folder",
            content: markup(_t("<b>Create a new folder</b>")),
            run: "click",
        },
        {
            trigger: ".modal-body textarea.o_input",
            content: _t("And give it a proper name"),
            run: "edit",
        },
        {
            trigger: ".modal-footer button.o_form_button_save",
            content: _t("Let's save your new folder."),
            run: "click",
        },
        {
            trigger: ".o_documents_kanban_view .o_kanban_record:first",
            content: markup(_t("<b>Now, click on your folder</b> to open it")),
            run: "click",
        },
        {
            trigger: ".o_documents_kanban_view .btn-primary",
            content: _t("And upload a new file"),
            run: "click",
        },
        {
            trigger: ".o-dropdown-item.o_documents_kanban_upload",
            content: _t("Upload a new file"),
            run: "click",
        },
        {
            trigger: ".o_control_panel_actions .o_unselect_all",
            content: _t("Unselect the document you just uploaded."),
            run: "click",
        },
        {
            trigger: ".o_documents_kanban_view .o_kanban_record:first",
            content: markup(
                _t("Hold <b>CTRL</b> and click on the document to view the available actions.")
            ),
            run: "click",
        },
        {
            trigger: ".o_control_panel_actions button:contains('" + _t("Share") + "')",
            content: markup(
                _t(
                    "Great! Now that the file has been added, <b>let's manage its access rights.</b>"
                )
            ),
            run: "click",
        },
        {
            trigger: ".modal-body .o_field_many2many_tags_email",
            content: markup(
                _t(
                    "From here, you can <b>grant personal access rights by selecting a specific person.</b>"
                )
            ),
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: markup(_t("All set. Let's <b>Validate</b>")),
            run: "click",
        },
        {
            trigger: ".o_control_panel_breadcrumbs button:has([data-icon='settings'])",
            content: markup(_t("Discover all actions to perform on the <b>current folder.</b>")),
            run: "click",
        },
        {
            trigger: ".o-dropdown-item:has([data-icon='settings'])",
            content: markup(_t("<b>Set an action</b> to apply on the files of this folder")),
            run: "click",
        },
        {
            trigger: ".o_control_panel .o_cp_action_menus:last",
            content: markup(_t("And all actions to perform on the <b>selected file(s).</b>")),
            run: "click",
        },
    ];
}

// ending steps when contacts is not installed
function getEndingWithoutContactsSteps() {
    return [
        {
            isActive: ["body:not(.hasContactsApp)"],
            trigger: "nav .o_menu_toggle",
            content: _t("We're all set, this concludes our onboarding of the documents app!"),
            run: "click",
        },
    ];
}

// steps when contacts is installed
function getContactsSteps() {
    return [
        {
            trigger: "nav .o_menu_toggle",
            content: _t("We're all set! Let's go the home page."),
            run: "click",
        },
        {
            trigger: ".o_app[data-menu-xmlid='contacts.menu_contacts']",
            content: markup(
                _t(
                    "Awesome! Let's explore how you can <b>access your files from anywhere in Odoo.</b>"
                )
            ),
            run: "click",
        },
        {
            trigger: ".o_list_view .o_data_row:first .o_list_char",
            content: markup(_t("Let's start by <b>accessing a contact form.</b>")),
            run: "click",
        },
        {
            trigger: ".o-mail-Chatter-logNote",
            content: markup(_t("And <b>add a note.</b>")),
            run: "click",
        },
        {
            trigger: ".o-mail-ActionList-button[name='add-documents']",
            content: markup(_t("Now let's <b>attach a file to this note.</b>")),
            run: "click",
        },
        {
            trigger: ".o_documents_content .o_data_row .form-check-input",
            content: markup(
                _t(
                    "From here you can access all your files. </br> <b>Let's select the file that you uploaded earlier.</b>"
                )
            ),
            run: "click",
        },
        {
            trigger: ".modal-footer .btn-primary",
            content: markup(
                _t(
                    "Now let's <b>add the link of your file</b> to give access to it in the chatter."
                )
            ),
            tooltipPosition: "top",
            run: "click",
        },
        {
            trigger: ".o-mail-Chatter .o-mail-Composer-send",
            content: markup(
                _t("Finally, <b>log the note</b> to complete this Documents onboarding tour!")
            ),
            run: "click",
        },
    ].map((step) => (step.isActive = ["body.hasContactsApp"]));
}

registry.category("web_tour.tours").add("documents_tour", {
    steps: () => [
        {
            trigger: "body",
            async run() {
                await rpc("/web/session/modules").then((modules) => {
                    if (modules.includes("contacts")) {
                        document.querySelector("body").classList.add("hasContactsApp");
                    }
                });
            },
        },
        ...getCommonSteps(),
        ...getContactsSteps(),
        ...getEndingWithoutContactsSteps(),
    ],
});
