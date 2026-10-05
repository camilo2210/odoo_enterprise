import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";
import { patch } from "@web/core/utils/patch";
import { parseXML, serializeXML } from "@web/core/utils/xml";
import { assertEqual, stepNotInStudio, nextTick } from "@web_studio/../tests/tours/tour_helpers";
import { cookie } from "@web/core/browser/cookie";
import { editorsWeakMap } from "@html_editor/../tests/tours/helpers/editor";
import { nodeSize } from "@html_editor/utils/position";

const getBoundingClientRect = Element.prototype.getBoundingClientRect;

function normalizeXML(str) {
    const doc = parseXML(str);
    /* Recursively trim text nodes conditionally
     * if they start or end with a newline (\n).
     * In that case we make the assumption that all whitespaces
     * are materializing indentation.
     * If there are only spaces (\s), we make the assumption that they
     * are actual spaces that are visible to the naked eye of the user.
     */
    const nodes = [...doc.childNodes];
    for (const node of nodes) {
        if (node.nodeType === Node.TEXT_NODE) {
            let nodeValue = node.nodeValue;
            if (nodeValue.startsWith("\n")) {
                nodeValue = nodeValue.trimStart();
            }
            if (nodeValue.endsWith("\n")) {
                nodeValue = nodeValue.trimEnd();
            }
            node.nodeValue = nodeValue;
        }
        if (node.nodeType === Node.ELEMENT_NODE) {
            nodes.push(...node.childNodes);
        }
    }

    return serializeXML(doc);
}

function insertText(element, text, offsets = null) {
    const doc = element.ownerDocument;
    const sel = doc.getSelection();
    let range;
    if (sel && sel.rangeCount) {
        range = sel.getRangeAt(sel.rangeCount - 1);
    }
    if (offsets || !range) {
        const { start, end } = offsets || {};
        sel.removeAllRanges();
        range = doc.createRange();
        range.setStart(element, start || 0);
        range.setEnd(element, end || start || 0);
        sel.addRange(range);
    }

    const evOptions = {
        view: doc.defaultView,
        bubbles: true,
        composed: true,
        cancelable: true,
        isTrusted: true,
    };

    for (const char of text) {
        element.dispatchEvent(
            new KeyboardEvent("keydown", {
                ...evOptions,
                key: char,
            })
        );
        element.dispatchEvent(
            new KeyboardEvent("keypress", {
                ...evOptions,
                key: char,
            })
        );
        element.dispatchEvent(
            new InputEvent("beforeinput", {
                ...evOptions,
                inputType: "insertText",
                data: char,
            })
        );

        const newNode = doc.createTextNode(char);
        element.append(newNode);

        // Move the caret after the inserted character
        // and collapse the selection.
        range.setStart(newNode, newNode.length);
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);

        element.dispatchEvent(
            new InputEvent("input", {
                ...evOptions,
                inputType: "insertText",
                data: char,
            })
        );

        element.dispatchEvent(
            new KeyboardEvent("keyup", {
                ...evOptions,
                key: char,
            })
        );
    }
}

function openEditorPowerBox(element, offsets = null) {
    return insertText(element, "/", offsets);
}

/* global ace */

// This function allows to use and test the feature that automatically
// saves when we leave the reportEditor.
// Implem detail: it is done at willUnmount, so we need to wait for the promise
// to be sure we leave the tour when the save is done.
function patchReportEditorModelForSilentSave() {
    const saveProms = [];
    const { ReportEditorModel } = odoo.loader.modules.get(
        "@web_studio/client_action/report_editor/report_editor_model"
    );
    const _unpatch = patch(ReportEditorModel.prototype, {
        saveReport() {
            const prom = super.saveReport(...arguments);
            saveProms.push(prom);
            return prom;
        },
    });

    return {
        wait: async (unpatch = true) => {
            await Promise.all(saveProms);
            if (unpatch) {
                _unpatch();
            }
        },
        saveProms,
        unpatch: _unpatch,
    };
}

registry
    .category("web_tour.tours")
    .add("web_studio.test_disable_fields_commands_when_unavailable", {
        steps: () => [
            {
                trigger:
                    ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p.some_p",
                async run(helpers) {
                    const el = this.anchor;
                    openEditorPowerBox(el, { start: 0 });
                },
            },
            {
                trigger: ".o-we-powerbox .o-we-command-name",
                run: (target) => {
                    const commands = Array.from(
                        document.querySelectorAll(".o-we-command-name")
                    ).map((e) => e.textContent);

                    if (commands.includes("Field") || commands.includes("Dynamic Table")) {
                        throw new Error(
                            "`Field`|`Dynamic Table` shouldn't be present when we don't have a record"
                        );
                    }
                },
            },
        ],
    });

let silentPatch;
registry.category("web_tour.tours").add("web_studio.test_basic_report_edition", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar input[id='name']",
            run: "edit modified in test && click body",
        },
        {
            trigger: ".o_web_studio_menu .breadcrumb-item.active:contains(modified in test)",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0)",
            run: "editor edited with odoo editor",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(2)",
            run: "editor edited with odoo editor 2",
        },
        {
            // Don't explicitly save, this is a feature
            trigger: ".o_web_studio_leave a",
            run(helpers) {
                silentPatch = patchReportEditorModelForSilentSave();
                helpers.click();
            },
        },
        ...stepNotInStudio(),
        {
            trigger: "body",
            run() {
                return silentPatch.wait();
            },
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_basic_report_edition_xml", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-sidebar button[name='web_studio.test_report_document'].active",
        },
        {
            trigger: `.ace_content:contains(<p t-field="doc.name" lock-id="2"/>)`,
        },
        {
            trigger: ".o_web_studio_code_editor.ace_editor",
            run() {
                ace.edit(this.anchor)
                    .getSession()
                    .insert(
                        { row: 2, column: 0 },
                        '<span class="test-added-0">in document view</span>\n'
                    );
            },
        },
        {
            trigger: `.ace_content:contains(<span class="test-added-0">in document view</span>)`,
        },
        {
            trigger:
                ".o-web-studio-report-editor-sidebar button[name='web_studio.studio_test_report_view']",
            run: "click",
        },
        {
            trigger: `.ace_content:contains(<t t-call="web_studio.test_report_document" lock-id="6"/>)`,
        },
        {
            trigger: ".o_web_studio_code_editor.ace_editor",
            run() {
                ace.edit(this.anchor)
                    .getSession()
                    .insert(
                        { row: 2, column: 0 },
                        '<span class="test-added-1">in main view</span>\n'
                    );
            },
        },
        {
            trigger: `.ace_content:contains(<span class="test-added-1">in main view</span>)`,
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
        {
            trigger:
                ".o-web-studio-report-container :iframe body .test-added-0:contains(in document view)",
        },
        {
            trigger:
                ".o-web-studio-report-container :iframe body .test-added-1:contains(in main view)",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_basic_report_edition_discard", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar input[id='name']",
            run: "edit modified in test && click body",
        },
        {
            trigger: ".o_web_studio_menu .breadcrumb-item.active:contains(modified in test)",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0)",
            run: "editor edited with odoo editor",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(2)",
            run: "editor edited with odoo editor 2",
        },
        {
            trigger: ".o-web-studio-discard-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".modal-dialog .btn-primary",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0):text()",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_basic_report_edition_cancel_discard", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar input[id='name']",
            run: "edit modified in test && click body",
        },
        {
            trigger: ".o_web_studio_menu .breadcrumb-item.active:contains(modified in test)",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0)",
            run: "editor edited with odoo editor",
        },
        {
            trigger: ".o-web-studio-discard-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".modal-dialog .btn-secondary",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0):contains(edited with odoo editor)",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_basic_report_edition_xml_discard", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o_web_studio_code_editor.ace_editor",
            run() {
                ace.edit(this.anchor)
                    .getSession()
                    .insert({ row: 2, column: 0 }, '<span class="test-added">in main view</span>');
            },
        },
        {
            trigger: ".o-web-studio-discard-report:not([disabled])",
            run: "click",
        },
        {
            content: "The changes should have been discarded",
            trigger: ".o-web-studio-report-container :iframe body:not(:has(.test-added))",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_basic_report_edition_error", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0)",
            run: "editor edited with odoo editor",
        },
        {
            // Brutally add a t-else: this will crash in python on save
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable",
            run() {
                const editor = editorsWeakMap.get(this.anchor.ownerDocument);
                const telse = editor.document.createElement("t");
                telse.setAttribute("t-else", "");
                editor.shared.dom.insert(telse);
                editor.shared.history.commit();
            },
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(2)",
            run: "editor edited with odoo editor 2",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o_notification:contains(Report edition failed)",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0):contains(edited with odoo editor)",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_basic_report_edition_xml_error", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o_web_studio_code_editor.ace_editor",
            run() {
                ace.edit(this.anchor)
                    .getSession()
                    .insert(
                        { row: 2, column: 0 },
                        '<span t-else="" class="test-added">in main view</span>'
                    );
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o_notification:contains(Report edition failed)",
        },
        {
            content: `The changes should have been discarded`,
            trigger: ".o-web-studio-report-container :iframe body:not(:has(.test-added))",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_report_reset_archs", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor-xml-resource:text('bad view')",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor-xml button[name='view_diff']",
            run: "click",
        },
        {
            trigger: "[name='reset_mode'] input[data-value='hard']",
            run: "click",
        },
        {
            trigger: ".modal-footer button[name='reset_view_button']",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor :iframe p:text(from file)",
        },
    ],
});

let downloadProm;
const steps = [];
registry.category("web_tour.tours").add("web_studio.test_print_preview", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='preview_mode']",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar button:text(Print)",
            run(helpers) {
                downloadProm = new Promise((resolve) => {
                    const unpatch = patch(download, {
                        _download(options) {
                            steps.push("download report");
                            const context = JSON.parse(options.data.context);
                            assertEqual(context["report_pdf_no_attachment"], true);
                            assertEqual(context["discard_logo_check"], true);
                            assertEqual(context["active_ids"].length, 1);
                            unpatch();
                            resolve();
                        },
                    });
                });
                return helpers.click();
            },
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar",
            async run() {
                await downloadProm;
                assertEqual(steps.length, 1);
                assertEqual(steps[0], "download report");
            },
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_table_rendering", {
    steps: () => [
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable .valid_table",
            run() {
                assertEqual(
                    this.anchor.outerHTML.replace(/\n\s*/g, ""),
                    `<table class="valid_table" o-diff-key="3">
                        <tbody o-diff-key="4"><tr o-diff-key="5"><td o-diff-key="6">I am valid</td></tr>
                    </tbody></table>`.replace(/\n\s*/g, "")
                );
            },
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable .invalid_table",
            run() {
                assertEqual(
                    this.anchor.outerHTML.replace(/\n\s*/g, ""),
                    `<q-table class="invalid_table oe_unbreakable" o-diff-key="7" style="--q-table-col-count: 1;">
                    <t t-foreach="doc.child_ids" t-as="child" o-diff-key="8" oe-context="{&quot;docs&quot;: {&quot;model&quot;: &quot;res.partner&quot;, &quot;name&quot;: &quot;Contact&quot;, &quot;in_foreach&quot;: false}, &quot;company&quot;: {&quot;model&quot;: &quot;res.company&quot;, &quot;name&quot;: &quot;Company&quot;, &quot;in_foreach&quot;: false}, &quot;doc&quot;: {&quot;model&quot;: &quot;res.partner&quot;, &quot;name&quot;: &quot;Contact&quot;, &quot;in_foreach&quot;: true}, &quot;child&quot;: {&quot;model&quot;: &quot;res.partner&quot;, &quot;name&quot;: &quot;Contact&quot;, &quot;in_foreach&quot;: true}}">
                        <q-tr o-diff-key="9" class="oe_unbreakable"><q-td o-diff-key="10" class="oe_unbreakable">I am not valid</q-td></q-tr>
                    </t>
                </q-table>`.replace(/\n\s*/g, "")
                );
            },
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable .invalid_table q-td",
            run: "editor edited with odooEditor",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(1)",
            run: "editor p edited with odooEditor",
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar input[id='name']",
            run: "edit modified && click body",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_field_placeholder", {
    steps: () => [
        {
            // 1 sec delay to make sure we call the download route
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable:has(.o-we-hint) p:eq(2)",
            async run(helpers) {
                const el = this.anchor;
                openEditorPowerBox(el, { start: 0 });
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command-description:contains(Insert a field)",
            run: "click",
        },

        {
            trigger: ".o-dynamic-field-popover",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg div:has(> .o-web-studio-report-container)",
            async run({ waitUntil }) {
                const placeholderBox = getBoundingClientRect.call(
                    document.querySelector(".o-dynamic-field-popover")
                );
                assertEqual(this.anchor.scrollTop, 0);
                this.anchor.scrollTop = 9999;
                await waitUntil(() => {
                    const newPlaceholderbox = getBoundingClientRect.call(
                        document.querySelector(".o-dynamic-field-popover")
                    );
                    // The field placeholder should have followed its anchor, and it happens that the anchor's container
                    // has been scrolled, so the anchor has moved upwards (and is actually outside of the viewPort, to the top)
                    return placeholderBox.top > newPlaceholderbox.top;
                });
                this.anchor.scrollTop = 0;
                await new Promise(requestAnimationFrame);
            },
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit Job Position",
        },
        {
            trigger: ".o_model_field_selector_popover_item_name:contains(Job Position)",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit some default value",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable span[t-field='doc.function'][title='doc.function']",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(0)",
            run() {
                insertText(this.anchor, "edited with odooEditor");
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_add_field_blank_report", {
    steps: () => [
        {
            // edit reports
            trigger: ".o_web_studio_menu button:contains(Reports)",
            run: "click",
        },
        {
            // create a new report
            trigger: ".o_control_panel .o-kanban-button-new",
            run: "click",
        },
        {
            // select basic layout
            trigger: '.o_web_studio_report_layout_dialog div[data-layout="web.basic_layout"]',
            run: "click",
        },
        {
            trigger: ":iframe .odoo-editor-editable .page div",
            async run(helpers) {
                const el = this.anchor;
                openEditorPowerBox(el);
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command-description:contains(Insert a field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg div:has(> .o-web-studio-report-container)",
            async run({ waitUntil }) {
                const placeholderBox = getBoundingClientRect.call(
                    document.querySelector(".o-dynamic-field-popover")
                );
                assertEqual(this.anchor.scrollTop, 0);
                this.anchor.scrollTop = 9999;
                await waitUntil(() => {
                    const newPlaceholderbox = getBoundingClientRect.call(
                        document.querySelector(".o-dynamic-field-popover")
                    );
                    // The field placeholder should have followed its anchor, and it happens that the anchor's container
                    // has been scrolled, so the anchor has moved upwards (and is actually outside of the viewPort, to the top)
                    return placeholderBox.top > newPlaceholderbox.top;
                });
                this.anchor.scrollTop = 0;
                await new Promise(requestAnimationFrame);
            },
        },
        {
            trigger: ".o_model_field_selector_popover_search input:visible",
            run: "edit Job Position",
        },
        {
            trigger: ".o_model_field_selector_popover_item_name:contains(Job Position)",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit some default value",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']:value(some default value)",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o-dynamic-field-popover))",
        },
        {
            // check that field was added successfully
            trigger:
                ":iframe .odoo-editor-editable .page div > span[data-oe-demo='some default value']:contains(some default value)",
        },
        {
            trigger: ":iframe .odoo-editor-editable .page div",
            run() {
                insertText(this.anchor, "Custo");
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_toolbar_appearance", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable .to_edit",
            run() {
                const anchor = this.anchor;
                const doc = anchor.ownerDocument;
                const selection = doc.getSelection();
                selection.removeAllRanges();
                const range = doc.createRange();
                range.selectNode(anchor.firstChild);
                selection.addRange(range);
            },
        },
        {
            trigger: ".o-we-toolbar",
        },
        {
            trigger: ".o-we-toolbar button[name='bold']",
            run: "click",
        },
        {
            trigger: ".o-we-toolbar button[name='italic']",
            run: "click",
        },
        {
            trigger: ".o-web-studio-discard-report:not([disabled])",
            run: "click",
        },
        {
            trigger: "body:not(:has(.o-we-toolbar))",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_edition_without_lang", {
    steps: () => [
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(1):contains(original term)",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(1)",
            async run() {
                insertText(this.anchor, " edited");
            },
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-xml-resource:text('Odoo Studio: web_studio.test_report_document report customization')",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor-xml button.o-translate-button",
            run: "click",
        },
        {
            trigger: ".o_translation_dialog .modal-title:contains(Translate Report)",
        },
        {
            trigger: ".o-translate-lang-buttons button:contains(French)",
            run: "click",
        },
        {
            trigger: ".o-translate-lang-buttons button.active:contains(French)",
        },
        {
            trigger: ".o_translation_dialog input:value(original term edited)",
            run: "edit translated edited term && click body",
        },
        {
            trigger: ".modal-footer button.btn-primary",
            run: "click",
        },
        {
            trigger: ".o_web_studio_editor",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_report_xml_other_record", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o_web_studio_xml_editor",
        },
        {
            trigger: ".o-web-studio-report-container :iframe body p:contains(partner_1)",
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar input:value(partner_1)",
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar .o_pager_next",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-container :iframe body p:contains(partner_2)",
        },
        {
            trigger: ".o-web-studio-report-editor-sidebar input:value(partner_2)",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_partial_eval", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-container :iframe .odoo-editor-editable .lol",
            run() {
                const closestContextElement = this.anchor.closest("[oe-context]");
                const oeContext = closestContextElement.getAttribute("oe-context");
                const expected = {
                    docs: { model: "res.partner", name: "Contact", in_foreach: false },
                    company: { model: "res.company", name: "Company", in_foreach: false },
                    doc: { model: "res.partner", name: "Contact", in_foreach: true },
                    my_children: { model: "res.partner", name: "Contact", in_foreach: false },
                    child: { model: "res.partner", name: "Contact", in_foreach: true },
                };
                assertEqual(JSON.stringify(JSON.parse(oeContext)), JSON.stringify(expected));
            },
        },
        {
            trigger: ".o-web-studio-report-container :iframe .odoo-editor-editable .couic",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_render_multicompany", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-container :iframe .odoo-editor-editable .test_layout",
        },
        {
            trigger: ".o-web-studio-report-container :iframe .odoo-editor-editable img",
            run() {
                const cids = cookie.get("cids").split("-");
                assertEqual(this.anchor.getAttribute("src"), `/logo.png?company=${cids[0]}`);
            },
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_add_non_searchable_field", {
    steps: () => [
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable:has(.o-we-hint) p:eq(2)",
            async run(helpers) {
                const el = this.anchor;
                openEditorPowerBox(el, { start: 0 });
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command-description:contains(Insert a field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit Avatar",
        },
        {
            trigger: "[data-name=avatar_1024] > button.o_model_field_selector_popover_item_name",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit file default value",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_report_edition_binary_field", {
    steps: () => [
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable:has(.o-we-hint) p:eq(2)",
            async run(helpers) {
                const el = this.anchor;
                openEditorPowerBox(el, { start: 0 });
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command-description:contains(Insert a field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit Company",
        },
        {
            trigger: "[data-name=company_id] > button.o_model_field_selector_popover_item_relation",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit New File",
        },
        {
            trigger:
                ".o_model_field_selector_popover_item_name:contains(New File):not(:contains(filename))",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit file default value",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(2)",
            async run(helpers) {
                await new Promise((r) => setTimeout(r, 500));
                const el = this.anchor;
                openEditorPowerBox(el, { start: nodeSize(el) }); // after the file field
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command-description:contains(Insert a field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit Company",
        },
        {
            trigger: "[data-name=company_id] > button.o_model_field_selector_popover_item_relation",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit New Image",
        },
        {
            trigger: ".o_model_field_selector_popover_item_name:contains(New Image)",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit image default value",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_report_edition_dynamic_table", {
    steps: () => [
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable:has(.o-we-hint) p:eq(2)",
            async run(helpers) {
                const el = this.anchor;
                openEditorPowerBox(el, { start: 0 });
            },
        },
        {
            trigger:
                ".o-we-powerbox .o-we-command-description:contains(Insert a table based on a relational field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit Activities",
        },
        {
            trigger: "[data-name=activity_ids] > button.o_model_field_selector_popover_item_name",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable table tr td:contains(Activities)",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable table tr[t-foreach]",
            run() {
                const el = this.anchor;
                const context = JSON.parse(el.getAttribute("oe-context"));
                assertEqual(context.x2many_record.model, "mail.activity");
            },
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable table tr td:contains(Insert a field...)",
            run() {
                openEditorPowerBox(this.anchor);
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command-description:contains(Insert a field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_search input",
            run: "edit Summary",
        },
        {
            trigger: ".o_model_field_selector_popover_item_name:contains(/^Summary/)",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit Some Summary",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable table td span[t-field='x2many_record.summary']",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_saving_xml_editor_reload", {
    steps: () => [
        {
            trigger: "button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
        {
            trigger: ".o_web_studio_xml_editor .ace_editor",
            async run() {
                await nextTick(); // Wait for ace to be fully operational
                const editor = ace.edit(this.anchor);
                editor.selection.moveToPosition({
                    row: 2,
                    column: 0,
                });
                editor.insert('<span class="test-added-0">in document view</span>');
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
        {
            trigger: ".o_web_studio_xml_editor .ace_editor",
            async run() {
                const editor = ace.edit(this.anchor);
                const aceValue = editor.getSession().getValue();

                assertEqual(
                    normalizeXML(aceValue),
                    normalizeXML(`
                        <t t-name="web_studio.test_report_document" lock-id="0">
                            <div lock-id="1"><p t-field="doc.name" lock-id="2"/></div>
                            <span class="test-added-0">in document view</span>
                            <p lock-id="3"><br lock-id="4" /></p>
                        </t>`)
                );

                const cursor = editor.getCursorPosition();
                assertEqual(cursor.row, 2);
                assertEqual(cursor.column, 50);
            },
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_error_at_loading", {
    steps: () => [
        {
            trigger: "body:not(:has(.o_error_dialog)) .o-web-studio-report-editor",
            run: "click",
        },
        {
            trigger: ":iframe div:contains(The report could not be rendered due to an error)",
        },
        {
            trigger: "button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o_web_studio_xml_editor",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_error_at_loading_debug", {
    steps: () => [
        {
            trigger: "body:not(:has(.o_error_dialog)) .o-web-studio-report-editor",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-container:not(:has(iframe))",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-container strong:contains(builtins.ValueError)",
            run: "click",
        },
        {
            trigger: "button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger: ".o_web_studio_xml_editor",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-container:not(:has(iframe))",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-container strong:contains(odoo.addons.base.models.ir_qweb.QWebError)",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_xml_and_form_diff", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable p:eq(2)",
            run() {
                insertText(this.anchor, "edited with odooEditor");
            },
        },
        {
            trigger: "button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-sidebar button:contains('test_report_document report customization')",
            run: "click",
        },
        {
            trigger: "button[name='view_diff']",
            run: "click",
        },
        {
            trigger: ".o_form_view table.diff",
        },
        {
            trigger:
                ".o_form_view .o_field_widget[name='view_name']:contains('test_report_document report customization')",
        },
        {
            trigger: ".o_form_view .o_field_widget [data-value='other_view']",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='compare_view_id'] input:value()",
        },
        {
            trigger: ".modal-footer button:text(Discard)",
            run: "click",
        },
        {
            trigger: ":not(.o_form_view)",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_remove_branding_on_copy", {
    steps: () => [
        {
            trigger: "body :iframe .odoo-editor-editable#wrapwrap",
            async run() {
                const doc = this.anchor.ownerDocument;
                const editor = editorsWeakMap.get(doc);
                const originNode = this.anchor.querySelector(`[ws-view-id]`);
                const copy = originNode.cloneNode(true);
                originNode.insertAdjacentElement("afterend", copy);
                editor.shared.history.commit();
                // Wait for a full macrotask tick and a frame to let the mutation observer
                // of the ReportEditorWysiwyg to catch up on the change and finish its operations
                await nextTick();
                const attributeCopy = {};
                for (const attr of copy.attributes) {
                    attributeCopy[attr.name] = attr.value;
                }
                assertEqual(JSON.stringify(attributeCopy), `{"contenteditable":"true"}`);
            },
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_different_view_document_name", {
    steps: () => [
        {
            trigger: ".o-web-studio-report-editor-sidebar button[name='report_edit_sources']",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-sidebar button[name='web_studio.test_report_document_1']",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_edit_main_arch", {
    steps: () => [
        {
            trigger: ":iframe .odoo-editor-editable .outside-t-call",
            async run() {
                const doc = this.anchor.ownerDocument;
                const editor = editorsWeakMap.get(doc);
                const newNode = doc.createElement("div");
                newNode.classList.add("added");
                this.anchor.insertAdjacentElement("beforebegin", newNode);
                editor.shared.history.commit();
                await nextTick();
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_edit_in_t_call", {
    steps: () => [
        {
            trigger: ":iframe .odoo-editor-editable .in-t-call",
            async run() {
                const doc = this.anchor.ownerDocument;
                const editor = editorsWeakMap.get(doc);
                const newNode = doc.createElement("div");
                newNode.classList.add("added");
                this.anchor.insertAdjacentElement("beforebegin", newNode);
                editor.shared.history.commit();
                await nextTick();
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_edit_main_and_in_t_call", {
    steps: () => [
        {
            trigger: ":iframe .odoo-editor-editable#wrapwrap",
            async run() {
                const doc = this.anchor.ownerDocument;
                const editor = editorsWeakMap.get(doc);
                const newNode0 = doc.createElement("div");
                newNode0.classList.add("added0");
                const target0 = this.anchor.querySelector(".outside-t-call");
                target0.insertAdjacentElement("beforebegin", newNode0);
                editor.shared.history.commit();
                await nextTick();
                const newNode1 = doc.createElement("div");
                newNode1.classList.add("added1");
                const target1 = this.anchor.querySelector(".in-t-call");
                target1.insertAdjacentElement("beforebegin", newNode1);
                editor.shared.history.commit();
                await nextTick();
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_image_crop", {
    steps: () => [
        {
            trigger: "body :iframe .odoo-editor-editable .myimg",
            run: "click",
        },
        {
            trigger: ".o-we-toolbar button[name='image_crop']",
            run: "click",
        },
        {
            trigger: ".o-main-components-container .o_we_crop_widget .cropper-container",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_translations_are_copied", {
    steps: () => [
        {
            trigger: "body :iframe .odoo-editor-editable#wrapwrap div:contains(term2)",
            run() {
                const doc = this.anchor.ownerDocument;
                const editor = editorsWeakMap.get(doc);
                const newNode = doc.createElement("div");
                (newNode.textContent = "term3 from edition"),
                    this.anchor.insertAdjacentElement("beforebegin", newNode);
                editor.shared.history.commit();
                return nextTick();
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_reports_view_concurrence", {
    steps: () => [
        {
            trigger: ".o_menu_sections button:contains('Reports')",
            run: "click",
        },
        {
            trigger: ".o_kanban_record[data-id] ",
            run: "dblclick",
        },
        {
            trigger: ".o-web-studio-report-editor",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_dont_translate_on_save", {
    steps: () => [
        {
            trigger: "body :iframe .odoo-editor-editable#wrapwrap p.test-origin",
            async run() {
                const doc = this.anchor.ownerDocument;
                const el = doc.createElement("span");
                el.textContent = "new content";
                this.anchor.insertAdjacentElement("beforebegin", el);
                const editor = editorsWeakMap.get(doc);
                editor.shared.history.commit();
                await nextTick();
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
        {
            trigger: "body :iframe .odoo-editor-editable#wrapwrap span",
            run() {
                const doc = this.anchor.ownerDocument;
                const selection = doc.getSelection();
                selection.removeAllRanges();
                const range = doc.createRange();
                range.selectNode(this.anchor);
                selection.addRange(range);
            },
        },
        {
            trigger: ".o-we-toolbar button[name='bold']",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_do_not_delete_unspecial_spans", {
    steps: () => [
        {
            trigger: "body :iframe .odoo-editor-editable#wrapwrap span",
            run() {
                insertText(this.anchor, "added");
            },
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_edit_header_only_company", {
    steps: () => [
        {
            trigger: "body :iframe .odoo-editor-editable#wrapwrap .header img",
            run() {
                const el = this.anchor;
                const span = el.ownerDocument.createElement("span");
                span.classList.add("studio-added");
                el.insertAdjacentElement("afterend", span);
                const sel = el.ownerDocument.getSelection();
                sel.removeAllRanges();
                openEditorPowerBox(span);
            },
        },
        {
            trigger: ".o-web-studio-options-container-header:contains(web.external_layout_standard)",
        },
        {
            trigger: ".o-we-powerbox .o-we-command:contains(Insert a field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_popover_item_name:contains(Company Name)",
            run: "click",
        },
        {
            trigger: ".o-dynamic-field-popover input[name='label_value']",
            run: "edit studio company id",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger:
                "body :iframe .odoo-editor-editable#wrapwrap .header [t-field][data-oe-demo='studio company id']",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_report_without_view", {
    steps: () => [
        {
            trigger: ".o_menu_sections button:contains('Reports')",
            run: "click",
        },
        {
            trigger: ".o_kanban_record:contains('Test Report(No view)')",
            run: "click",
        },
        {
            trigger: ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable",
        },
    ],
});

registry.category("web_tour.tours").add("web_studio.test_can_insert_bare_x2many", {
    steps: () => [
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable div.spot-on",
            async run(helpers) {
                const el = this.anchor;
                openEditorPowerBox(el, { start: 0 });
            },
        },
        {
            trigger: ".o-we-powerbox .o-we-command:contains(Field)",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value",
            run: "click",
        },
        {
            trigger:
                ".o_model_field_selector_popover_item:contains(Related Contacts):not(:has(.o_model_field_selector_popover_item_relation)) button",
            run: "click",
        },
        {
            trigger: ".o_model_field_selector_value:contains(Related Contacts)",
        },
        {
            trigger: ".o-dynamic-field-popover button.btn-primary",
            run: "click",
        },
        {
            trigger:
                ".o-web-studio-report-editor-wysiwyg :iframe .odoo-editor-editable span[t-field='doc.child_ids']",
        },
        {
            trigger: ".o-web-studio-save-report:not([disabled])",
            run: "click",
        },
        {
            trigger: ".o-web-studio-save-report[disabled]",
        },
    ],
});
