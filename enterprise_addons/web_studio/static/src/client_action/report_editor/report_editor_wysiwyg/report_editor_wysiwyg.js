import { Editor } from "@html_editor/editor";
import { LocalOverlayContainer } from "@html_editor/local_overlay_container";
import { closestElement } from "@html_editor/utils/dom_traversal";
import {
    Component,
    computed,
    onWillStart,
    onWillUnmount,
    proxy,
    signal,
    t,
    useEffect,
    usePlugin,
    useProps,
    useScope,
} from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { _t } from "@web/core/l10n/translation";
import { uniqueId } from "@web/core/utils/functions";
import { useBus, useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { Record as _Record } from "@web/model/record";
import { CharField } from "@web/views/fields/char/char_field";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { OptionsContainer, UndoRedo } from "../report_editor_components";
import { ReportEditorIframe } from "../report_editor_iframe";
import { ReportEditorSidebarPlugin } from "../report_editor_sidebar";
import { REPORT_EDITOR_PLUGINS } from "./editor_plugins/report_editor_plugin";

class __Record extends _Record.components._Record {
    setup() {
        super.setup();
        useBus(this.env.reportEditorModel.bus, "WILL_SAVE_URGENTLY", () =>
            this.model.bus.trigger("WILL_SAVE_URGENTLY")
        );
    }
}

class Record extends _Record {
    static components = { ..._Record.components, _Record: __Record };
}

export class ReportEditorWysiwygSidebar extends Component {
    static template = "web_studio.ReportEditorWysiwyg.Sidebar";
    static components = {
        Record,
        OptionsContainer,
        CharField,
        Many2OneField,
        Many2ManyTagsField,
    };

    sidebarPlugin = usePlugin(ReportEditorSidebarPlugin);
    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.action = useService("action");
        this.addDialog = useOwnedDialogs();
        this.reportEditorModel = proxy(this.env.reportEditorModel);
        this.reportRecordHooks = {
            onRecordChanged: (rec) => (this.reportEditorModel.reportData = rec.data),
        };
    }

    get reportRecordProps() {
        const model = this.reportEditorModel;
        return {
            fields: model.reportFields,
            activeFields: model.reportActiveFields,
            values: model.reportData,
        };
    }

    async openReportFormView() {
        await this.sidebarPlugin._saveFn?.();
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ir.actions.report",
                res_id: this.reportEditorModel.editedReportId,
                views: [[false, "form"]],
                target: "current",
            },
            { clearBreadcrumbs: true }
        );
    }

    openPrintDomainEditor(record) {
        this.addDialog(DomainSelectorDialog, {
            resModel: this.reportEditorModel.reportResModel,
            domain: record.data.domain || "[]",
            isDebugMode: this.debugMode.isActive(),
            onConfirm: (domain) => record.update({ domain }),
        });
    }
}

export class ReportEditorWysiwyg extends Component {
    static components = {
        ReportEditorIframe,
        LocalOverlayContainer,
    };
    static template = "web_studio.ReportEditorWysiwyg";

    props = useProps({ paperFormatStyle: t.string() });
    debugMode = usePlugin(DebugModePlugin);
    sidebarPlugin = usePlugin(ReportEditorSidebarPlugin);
    scope = useScope();

    setup() {
        this.overlayRef = signal.ref();
        this.localOverlayContainerKey = uniqueId("report_editor");

        this._reportQweb = computed(() => {
            const model = this.reportEditorModel;
            void model.renderKey;
            const tree = new DOMParser().parseFromString(
                this.reportEditorModel.reportQweb,
                "text/html"
            );
            const htmlNode = tree.firstElementChild;
            htmlNode.translate = false;
            return htmlNode;
        });

        this._iframeSource = computed(() => this._reportQweb().outerHTML);
        this.reportEditorModel = proxy(this.env.reportEditorModel);

        useEffect(() => {
            this._iframeSource();
            if (this.editor) {
                this.editor.destroy();
                this.editor = null;
            }
        });

        this.reportRecordHooks = {
            onRecordChanged: (rec) => (this.reportEditorModel.reportData = rec.data),
        };

        this.undoRedoState = proxy({
            canUndo: false,
            canRedo: false,
        });

        onWillStart(() => this.reportEditorModel.loadReportQweb());

        onWillUnmount(() => {
            this.reportEditorModel.bus.trigger("WILL_SAVE_URGENTLY");
            this.save({ urgent: true });
            if (this.editor) {
                this.editor.destroy(true);
            }
        });

        this.sidebarPlugin.useSave({
            isDirty: computed(() => this.reportEditorModel.isDirty),
            save: () => this.save(),
            discard: () => this.discard(),
        });
        this.sidebarPlugin.addComponent(UndoRedo, "start", {
            canUndo: computed(() => this.undoRedoState.canUndo),
            canRedo: computed(() => this.undoRedoState.canRedo),
            undo: () => this.editor?.shared.history.undo(),
            redo: () => this.editor?.shared.history.redo(),
        });
        this.scope = useScope();
    }

    instantiateEditor({ editable } = {}) {
        const onEditorChange = () => {
            this.undoRedoState.canUndo = this.editor.shared.history.canUndo();
            this.undoRedoState.canRedo = this.editor.shared.history.canRedo();
            this.reportEditorModel.isDirty = this.undoRedoState.canUndo;
        };

        editable.querySelectorAll("[ws-view-id]").forEach((el) => {
            el.setAttribute("contenteditable", "true");
        });
        const editor = new Editor(
            this.scope,
            {
                Plugins: REPORT_EDITOR_PLUGINS,
                onChange: onEditorChange,
                getRecordInfo: () => {
                    const { anchorNode } = this.editor.shared.selection.getEditableSelection();
                    if (!anchorNode) {
                        return {};
                    }
                    const lastViewParent = closestElement(anchorNode, "[ws-view-id]");
                    if (!lastViewParent) {
                        return {};
                    }
                    return {
                        resModel: "ir.ui.view",
                        resId: parseInt(lastViewParent.getAttribute("ws-view-id")),
                        field: "arch",
                    };
                },
                dynamicResModel: this.reportEditorModel.reportResModel,
                allowVideo: false,
                allowImageTransform: false,
                allowImageResize: false,
                localOverlayContainers: {
                    key: this.localOverlayContainerKey,
                    ref: this.overlayRef,
                },
                setEditingReport: (name, shared) => {
                    this.reportEditorModel.sharedReport.set(shared ? name : null);
                },
                cleanEmptyStructuralContainers: false,
            },
            this.env.services
        );
        editor.attachTo(editable);
        // disable the qweb's plugin class: its style is too complex and confusing
        // in the case of reports
        editable.classList.remove("odoo-editor-qweb");
        return editor;
    }

    onIframeLoaded({ iframeRef }) {
        if (this.editor) {
            this.editor.destroy(true);
            this.editor = null;
        }
        this.scope.run(() => {
            useEffect(() => {
                if (!iframeRef()) {
                    if (this.editor) {
                        this.editor.destroy(true);
                        this.editor = null;
                    }
                }
            });
        });
        this.iframeRef = iframeRef;
        const doc = iframeRef().contentDocument;
        doc.body.classList.remove("container");

        if (this.debugMode.isActive()) {
            ["t-esc", "t-out", "t-field"].forEach((tAtt) => {
                doc.querySelectorAll(`*[${tAtt}]`).forEach((e) => {
                    // Save the previous title to set it back before saving the report
                    if (e.hasAttribute("title")) {
                        e.setAttribute("data-oe-title", e.getAttribute("title"));
                    }
                    e.setAttribute("title", e.getAttribute(tAtt));
                });
            });
        }
        if (!this.reportEditorModel._errorMessage && this.reportEditorModel.mode === "wysiwyg") {
            this.editor = this.instantiateEditor({ editable: doc.querySelector("#wrapwrap") });
        }
    }

    get iframeSource() {
        return this._iframeSource();
    }

    async save({ urgent = false } = {}) {
        if (!this.editor) {
            await this.reportEditorModel.saveReport({ urgent });
            return;
        }
        const htmlParts = {};
        const editable = this.editor.getElContent();

        // Clean technical title
        if (this.debugMode.isActive()) {
            editable.querySelectorAll("*[t-field],*[t-out],*[t-esc]").forEach((e) => {
                if (e.hasAttribute("data-oe-title")) {
                    e.setAttribute("title", e.getAttribute("data-oe-title"));
                    e.removeAttribute("data-oe-title");
                } else {
                    e.removeAttribute("title");
                }
            });
        }

        editable.querySelectorAll("[ws-view-id].o_dirty").forEach((el) => {
            el.classList.remove("o_dirty");
            el.removeAttribute("contenteditable");
            const viewId = el.getAttribute("ws-view-id");
            if (!viewId) {
                return;
            }
            Array.from(el.querySelectorAll("[t-call]")).forEach((el) => {
                el.removeAttribute("contenteditable");
                el.replaceChildren();
            });

            Array.from(el.querySelectorAll("[oe-origin-t-out]")).forEach((el) => {
                el.replaceChildren();
            });
            if (!el.hasAttribute("oe-origin-class") && el.getAttribute("class") === "") {
                el.removeAttribute("class");
            }

            const callGroupKey = el.getAttribute("ws-call-group-key");
            const type = callGroupKey ? "in_t_call" : "full";

            const escaped_html = el.outerHTML;
            htmlParts[viewId] = htmlParts[viewId] || [];

            htmlParts[viewId].push({
                call_key: el.getAttribute("ws-call-key"),
                call_group_key: callGroupKey,
                type,
                html: escaped_html,
            });
        });
        await this.reportEditorModel.saveReport({ htmlParts, urgent });
    }

    async discard() {
        if (this.editor) {
            const selection = this.editor.document.getSelection();
            if (selection) {
                selection.removeAllRanges();
            }
        }
        this.env.services.dialog.add(ConfirmationDialog, {
            body: _t(
                "If you discard the current edits, all unsaved changes will be lost. You can cancel to return to edit mode."
            ),
            confirm: () => this.reportEditorModel.discardReport(),
            cancel: () => {},
        });
    }
}
