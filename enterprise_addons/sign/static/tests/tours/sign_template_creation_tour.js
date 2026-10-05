import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import tourUtils from "@sign/js/tours/tour_utils";

export function createSelectionRectangle(viewerContainer, page, startPos = 0.25, endPos = 0.75) {
    const pageRect = page.getBoundingClientRect();

    const startX = pageRect.left + pageRect.width * startPos;
    const startY = pageRect.top + pageRect.height * startPos;
    const endX = pageRect.left + pageRect.width * endPos;
    const endY = pageRect.top + pageRect.height * endPos;

    const mousedownEvent = new MouseEvent("mousedown", {
        bubbles: true,
        clientX: startX,
        clientY: startY,
        button: 0,
    });
    viewerContainer.dispatchEvent(mousedownEvent);

    const mousemoveEvent2 = new MouseEvent("mousemove", {
        bubbles: true,
        clientX: endX,
        clientY: endY,
    });
    viewerContainer.dispatchEvent(mousemoveEvent2);

    const mouseupEvent = new MouseEvent("mouseup", {
        bubbles: true,
        clientX: endX,
        clientY: endY,
    });
    viewerContainer.dispatchEvent(mouseupEvent);
}

registry.category("web_tour.tours").add("sign_template_creation_tour", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Sign App",
            trigger: '.o_app[data-menu-xmlid="sign.menu_document"]',
            run: "click",
        },
        {
            content: "Click on Template Menu",
            trigger: 'a[data-menu-xmlid="sign.sign_template_menu"]',
            run: "click",
        },
        {
            trigger: ".o_last_breadcrumb_item > span:contains('Templates')",
        },
        {
            content: "Remove My Favorites filter",
            trigger: ".o_cp_searchview .o_facet_remove",
            run: "click",
        },
        {
            content: 'Search template "blank_template"',
            trigger: ".o_cp_searchview input",
            run: "fill blank_template",
        },
        {
            content: "Search Document Name",
            trigger: ".o_searchview_autocomplete .o-dropdown-item:first",
            run: "click",
        },
        {
            content: "Enter Template Edit Mode",
            trigger: '.o_kanban_record span:contains("blank_template")',
            run: "click",
        },
        {
            content: "Wait for iframe to load PDF",
            trigger: ":iframe #viewerContainer",
        },
        {
            content: "Wait for page to be loaded",
            trigger: ":iframe .page[data-page-number='1'] .textLayer",
            timeout: 30000, //In view mode, pdf loading can take a long time
        },
        {
            content: "Enter Template Edit Mode",
            trigger: "[data-icon='edit'].me-2:not(:visible)",
            run: "click",
        },
        {
            content: "Edit Signer Role",
            trigger: ".o_input.form-control.bg-transparent.rounded-0.pe-1",
            run: "edit Signer 1-Test && click body",
        },
        {
            content: "Drop Signature Item",
            trigger: ".o_sign_field_type_button:contains(Signature)",
            async run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                await tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.5, 0.25);
            },
        },
        {
            trigger: ":iframe .page:has(.o_sign_item_display:count(1))",
        },
        {
            content: "Click on Add Signer",
            trigger: "button[title='Add signer']",
            run: "click",
        },
        {
            content: "Open Sign Item Dropdown",
            trigger: ".o_sign_sidebar_signer:contains(signer 2) .o_sign_sidebar_icon.o-dropdown",
            run: "click",
        },
        {
            content: "Click on Edit",
            trigger: ".o-dropdown-item:contains('Edit')",
            run: "click",
        },
        {
            content: "Edit Name",
            trigger: ".modal input#name_0",
            run: "edit Test Signer",
        },
        {
            content: "Click on Save",
            trigger: ".modal .btn.btn-primary.o_form_button_save",
            run: "click",
        },
        {
            content: "Drop Signature Item",
            trigger: ".o_sign_field_type_button:contains(Signature)",
            async run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                await tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.25, 0.15);
            },
        },
        {
            trigger: ":iframe .page:has(.o_sign_item_display:count(2))",
        },
        {
            content: "Drop Name Sign Item",
            trigger: ".o_sign_field_type_button:contains(Name)",
            async run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                await tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.25, 0.25);
            },
        },
        {
            trigger: ":iframe .page:has(.o_sign_item_display:count(3))",
        },
        {
            content: "Drop Text Sign Item",
            trigger: ".o_sign_field_type_button:contains(Text)",
            async run({ queryFirst }) {
                const to = queryFirst(`:iframe .page[data-page-number="1"]`);
                await tourUtils.dragAndDropSignItemAtHeight(this.anchor, to, 0.15, 0.25);
            },
        },
        {
            trigger: ":iframe .page:has(.o_sign_item_display:count(4))",
        },
        {
            content: "Test multi-select by creating a selection rectangle",
            trigger: ":iframe .page[data-page-number='1']",
            run({ anchor, queryFirst }) {
                const viewerContainer = queryFirst(`:iframe #viewerContainer`);
                createSelectionRectangle(viewerContainer, anchor, 0.02, 0.4);
            },
        },
        {
            content: "Verify items are selected",
            trigger: ":iframe .page:has(.o_sign_sign_item.multi_selected:count(3))",
        },
        {
            content: "Test copy functionality with Ctrl+C",
            trigger: ":iframe .o_sign_sign_item.multi_selected",
            run() {
                const keyEvent = new KeyboardEvent("keydown", {
                    key: "c",
                    code: "KeyC",
                    ctrlKey: true,
                    bubbles: true,
                });
                document.querySelector("iframe").contentDocument.dispatchEvent(keyEvent);
            },
        },
        {
            content: "Click elsewhere to prepare for paste",
            trigger: ":iframe .page[data-page-number='1']",
            run({ anchor, click }) {
                const pageRect = anchor.getBoundingClientRect();
                click({
                    x: pageRect.left + pageRect.width * 0.8,
                    y: pageRect.top + pageRect.height * 0.8,
                });
            },
        },
        {
            content: "Test paste functionality with Ctrl+V",
            trigger: ":iframe .page[data-page-number='1']",
            run() {
                const keyEvent = new KeyboardEvent("keydown", {
                    key: "v",
                    code: "KeyV",
                    ctrlKey: true,
                    bubbles: true,
                });
                document.querySelector("iframe").contentDocument.dispatchEvent(keyEvent);
            },
        },
        {
            trigger: ":iframe .page:has(.o_sign_item_display:count(7))",
        },
        {
            content: "Test multi-select by creating a selection rectangle",
            trigger: ":iframe .page[data-page-number='1']",
            async run({ anchor, queryFirst }) {
                const viewerContainer = queryFirst(`:iframe #viewerContainer`);
                createSelectionRectangle(viewerContainer, anchor, 0.3, 0.6);
            },
        },
        {
            content: "Verify items are selected",
            trigger: ":iframe .page:has(.o_sign_sign_item.multi_selected:count(4))",
        },
        // Testing if search works by searching for letter 'a'.
        {
            content: "Click on the find button",
            trigger: ":iframe #viewFindButton",
            run: "click",
        },
        {
            content: "Search for letter 'a'",
            trigger: ":iframe #findInput",
            run: "fill a",
        },
        {
            content: "Verify the letter is highlighted",
            trigger: ":iframe .highlight",
        },
        {
            content: "Click on document name text to make it editable",
            trigger: ".o_sign_sidebar_document_name_text",
            run: "click",
        },
        {
            content: "Click document name edit button",
            trigger: ".o_sign_sidebar_document_name [data-icon='edit']:not(:visible)",
            run: "click",
        },
        {
            content: "Change document name",
            trigger: ".o_sign_document_name_input",
            run: "edit new-document-name && click body",
        },
        {
            trigger: ".breadcrumb .o_back_button",
            run: "click",
        },
    ],
});
