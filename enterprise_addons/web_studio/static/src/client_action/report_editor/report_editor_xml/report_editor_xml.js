import {
    Component,
    computed,
    onWillStart,
    onWillUnmount,
    useConfig,
    usePlugin,
    Plugin,
    useProps,
    proxy,
    signal,
    t,
} from "@odoo/owl";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { throttleForAnimation } from "@web/core/utils/timing";

import { _t } from "@web/core/l10n/translation";
import { useCodeEditorState } from "@web/core/code_editor/code_editor";
import { IrUiViewCodeEditor } from "@web/core/ir_ui_view_code_editor/code_editor";
import { ResizablePanel } from "@web/core/resizable_panel/resizable_panel";

import { loadResources } from "@web_studio/client_action/xml_resource_editor/xml_resource_editor";
import { OptionsContainer, UndoRedo } from "../report_editor_components";
import { ReportEditorIframe } from "../report_editor_iframe";
import { ReportEditorSidebarPlugin } from "../report_editor_sidebar";
import { TranslationButton } from "./translate_xml";

function isCustomization(resource) {
    return resource && resource.name.endsWith(" report customization");
}

export class ReportEditorResourcesPlugin extends Plugin {
    reportEditorModel = useConfig("reportEditorModel");

    resources = signal([]);
    currentResource = signal(null);
    currentResourceId = computed(() => this.currentResource()?.id ?? "");
    xmlChanges = signal.Object({});
    isDirty = computed(() => Object.keys(this.xmlChanges()).length > 0);

    resourcesMap = computed(() => Object.fromEntries(this.resources().map((r) => [r.id, r])));
    subResources = computed(() => {
        const resourcesMap = this.resourcesMap();
        const resources = this.resources().filter(
            (resource) =>
                this.isSubResource(resource) && !resourcesMap[resource.inherit_id[0]]?.combined_arch
        );
        return Object.groupBy(resources, (resource) => resource.inherit_id[0]);
    });
    mainResources = computed(() =>
        this.resources().filter((r) => !isCustomization(r) && !this.isSubResource(r))
    );
    customResources = computed(() => this.resources().filter((r) => isCustomization(r)));

    isResourceDirty(resource) {
        return this.xmlChanges()?.[resource.id];
    }

    isSubResource(resource) {
        return resource && resource.inherit_id && !("combined_arch" in resource);
    }

    async loadResources() {
        const { resources, defaultResource } = await loadResources({
            mainResourceId: this.reportEditorModel.reportData.report_name,
            url: "/web_studio/get_report_resources",
            checkMainViewKey: true,
        });

        this.xmlChanges.set({});
        this.resources.set(resources);

        if (this.currentResource()) {
            this.currentResource.set(this.resourcesMap()[this.currentResource().id]);
        } else {
            this.currentResource.set(defaultResource);
        }
    }
}

export class ReportResourceSelector extends Component {
    static template = "web_studio.ReportEditorXml.ResourceSelector";
    static components = { OptionsContainer };
    resourcesPlugin = usePlugin(ReportEditorResourcesPlugin);
}

export class ReportEditorXml extends Component {
    static components = {
        ReportEditorIframe,
        IrUiViewCodeEditor,
        ResizablePanel,
        TranslationButton,
    };
    static template = "web_studio.ReportEditorXml";

    props = useProps({ paperFormatStyle: t.string() });

    resourcesPlugin = usePlugin(ReportEditorResourcesPlugin);
    sidebarPlugin = usePlugin(ReportEditorSidebarPlugin);

    warningMessage = signal("");
    cursorPosition = signal.Object({ row: 0, column: 0 });

    xmlCode = computed(() => {
        if (!this.currentResource) {
            return "";
        }
        if (this.resourcesPlugin.xmlChanges()?.[this.currentResource.id]) {
            return this.resourcesPlugin.xmlChanges()[this.currentResource.id];
        }
        return this.currentResource[this.getResourceArchField(this.currentResource)];
    });

    translateButtonProps = computed(() => this._getTranslateButtonProps());

    setup() {
        this.action = useService("action");
        this.addDialog = useOwnedDialogs();
        this.reportEditorModel = proxy(this.env.reportEditorModel);
        this.codeEditorState = useCodeEditorState();

        onWillStart(async () => {
            await this.resourcesPlugin.loadResources();
            await this.reportEditorModel.loadReportHtml();
        });

        onWillUnmount(() => this.save({ urgent: true }));
        this.sidebarPlugin.useSave({
            isDirty: this.resourcesPlugin.isDirty,
            save: () => this.save(),
            discard: () => this.resourcesPlugin.loadResources(),
        });
        this.sidebarPlugin.addComponent(UndoRedo, "start", {
            canUndo: computed(() => this.codeEditorState.canUndo),
            canRedo: computed(() => this.codeEditorState.canRedo),
            undo: () => this.codeEditorState.undo(),
            redo: () => this.codeEditorState.redo(),
        });
    }

    get currentResource() {
        return this.resourcesPlugin.currentResource();
    }

    get editorInitialWidth() {
        const factor = 0.4;
        return Math.floor(document.documentElement.clientWidth * factor);
    }

    onCodeChange(code) {
        if (!this.currentResource) {
            return;
        }

        if (this.currentResource[this.getResourceArchField(this.currentResource)] !== code) {
            this.resourcesPlugin.xmlChanges()[this.currentResource.id] = code;
        } else {
            delete this.resourcesPlugin.xmlChanges()[this.currentResource.id];
        }
    }

    onFormat() {
        this.onCodeChange(window.vkbeautify.xml(this.xmlCode(), 4), { row: 0, column: 0 });
    }

    getResourceArchField(resource) {
        return "combined_arch" in resource ? "combined_arch" : "arch";
    }

    getChanges() {
        const changes = {};
        const mapResources = Object.fromEntries(
            this.resourcesPlugin.resources().map((res) => [res.id, res])
        );
        for (const [resourceId, code] of Object.entries({ ...this.resourcesPlugin.xmlChanges() })) {
            const resource = mapResources[resourceId];
            const codeField = this.getResourceArchField(resource);
            changes[resourceId] = { [codeField]: code };
        }
        return changes;
    }

    async save({ urgent = false } = {}) {
        const changes = this.getChanges();
        const result = await this.reportEditorModel.saveReport({
            urgent,
            xmlVerbatim: changes,
        });
        this.warningMessage.set(this.reportEditorModel.warningMessage);
        if (result !== false) {
            if (!urgent && Object.keys(changes).length) {
                await this.resourcesPlugin.loadResources();
            }
        }
    }

    getBrandingTargetInfo(target) {
        let viewId;
        let targetResource;
        const xmlResourceIds = this.resourcesPlugin.resourcesMap();
        while (target) {
            viewId = target.getAttribute(`data-ws-main-view-id`);
            viewId = viewId ? parseInt(viewId) : null;
            targetResource = viewId in xmlResourceIds ? viewId : null;
            if (!viewId || !targetResource) {
                target = target.parentElement?.closest(`[data-ws-main-view-id]`);
            } else {
                break;
            }
        }
        if (target) {
            const sourceLine = parseInt(target.getAttribute("data-ws-main-sourceLine"));
            return {
                viewId,
                sourceLine,
                target,
                targetResource,
            };
        }
        return {};
    }

    onIframeLoaded({ iframeRef }) {
        const iDocument = iframeRef().contentWindow.document;
        const highlightOverlay = iDocument.createElement("div");
        highlightOverlay.classList.add("pe-none", "position-fixed");
        highlightOverlay.style.setProperty(
            "background-color",
            "rgba(1, 186, 210, 0.3)",
            "important"
        );
        iDocument.body.style.cursor = "pointer";
        iDocument.body.append(highlightOverlay);

        let highlightData;
        iDocument.addEventListener("click", (ev) => {
            if (highlightData && highlightData.resourceId) {
                const sourceLine = highlightData.sourceLine ?? 1;
                const resource = this.resourcesPlugin.resourcesMap()[highlightData.resourceId];
                if (resource) {
                    this.resourcesPlugin.currentResource.set(resource);
                    this.cursorPosition.set({ row: sourceLine - 1 });
                }
            }
        });

        const onMouseover = throttleForAnimation((ev) => {
            const { sourceLine, targetResource, target } = this.getBrandingTargetInfo(ev.target);
            if (target) {
                highlightData = {
                    resourceId: targetResource,
                    sourceLine,
                };
                const targetRect = target.getBoundingClientRect();
                const highlightOverlayStyle = highlightOverlay.style;
                for (const measure of ["left", "top", "width", "height"]) {
                    highlightOverlayStyle.setProperty(measure, `${targetRect[measure]}px`);
                }
            }
        });
        iDocument.addEventListener("mouseover", onMouseover);
        iframeRef().addEventListener("mouseleave", () => {
            highlightData = null;
            const highlightOverlayStyle = highlightOverlay.style;
            for (const measure of ["left", "top", "width", "height"]) {
                highlightOverlayStyle.setProperty(measure, `0px`);
            }
        });
        this.reportEditorModel.setInEdition(false);
    }

    canEditDiff() {
        return this.currentResource && !this.currentResource.combined_arch;
    }

    async toggleDiff() {
        await this.save();
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "reset.view.arch.wizard",
                views: [[false, "form"]],
                target: "new",
                context: {
                    studio: false,
                    studio_report_diff: true,
                    active_ids: [this.resourcesPlugin.currentResourceId()],
                    active_model: "ir.ui.view",
                },
            },
            {
                onClose: (options) => {
                    if (!options || (!options.dismiss && !options.special)) {
                        this.reportEditorModel._resetInternalArchs();
                        this.reportEditorModel.loadReportHtml();
                        this.resourcesPlugin.loadResources();
                    }
                },
            }
        );
    }

    _getTranslateButtonProps() {
        const fieldName = this.currentResource?.inherit_id?.length ? "arch" : "combined_arch";
        return {
            fieldName,
            fieldType: "text",
            resId: this.resourcesPlugin.currentResourceId(),
            resModel: "ir.ui.view",
            dialogTitle: computed(() => _t(`Translate Report`)),
            classes: signal.Object({ "btn-flat": true, "btn-link": null }),
            beforeOpen: () => this.save({ urgent: true }),
            onSaved: () => this.resourcesPlugin.loadResources(),
        };
    }
}
