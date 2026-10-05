import { onMounted, onPatched, useProps, proxy, t } from "@odoo/owl";
import { formView } from "@web/views/form/form_view";
import { formControllerProps } from "@web/views/form/form_controller";
import { useModelConfigFetchInvisible } from "@web_studio/client_action/view_editor/editors/utils";

/**
 * This hook ensures that a record datapoint has the "parent" key in its evalContext, allowing
 * to access to field values of the parent record. This is useful in Studio because an x2many
 * record can be opened, but in a standalone fashion. It will be the root of its model, even
 * though, in practice, there's a parent record and a parent form view. This allows snippets like
 * `<field name="..." invisible="not parent.id" />` in the child view to work.
 */
function useExternalParentInModel(model, parentRecord) {
    model._createRoot = (config, data) =>
        new model.constructor.Record(model, config, data, { parentRecord });
}

export class FormEditorController extends formView.Controller {
    props = useProps({
        ...formControllerProps,
        parentRecord: t.or([t.object(), t.literal(null)]).optional(),
    });

    setup() {
        super.setup();
        useModelConfigFetchInvisible(this.model);
        this.mailTemplate = null;
        this.hasFileViewerInArch = false;

        this.viewEditorModel = proxy(this.env.viewEditorModel);

        if (this.props.parentRecord) {
            useExternalParentInModel(this.model, this.props.parentRecord);
        }

        const xpathTargetIsPageRe = /\/notebook(\[\d*?\])?\/page(\[\d*?\])?$/;
        onMounted(() => {
            const xpath = this.viewEditorModel.lastActiveNodeXpath;
            const autoClickParams = this.viewEditorModel.autoClickParams();
            if (
                xpath &&
                xpath.includes("notebook") &&
                !(
                    (autoClickParams.targetInfo?.xpath || "").match(xpathTargetIsPageRe) &&
                    autoClickParams.targetInfo?.position !== "inside"
                )
            ) {
                const tabXpath = xpath.match(/.*\/page\[\d+\]/)[0];
                const tab = document.querySelector(`[data-studio-xpath='${tabXpath}']`);
                if (tab) {
                    // store the targetted element to restore it after being patched
                    this.notebookElementData = {
                        xpath,
                        restore: Boolean(this.viewEditorModel.activeNodeXpath),
                        sidebarTab: this.viewEditorModel.sidebarTab,
                        isTab: xpath.length === tabXpath.length,
                    };
                    tab.dispatchEvent(
                        new CustomEvent("click", {
                            bubbles: true,
                            detail: {
                                discard_studio_click: true,
                            },
                        })
                    );
                }
            } else {
                this.notebookElementData = null;
            }
        });

        onPatched(() => {
            if (this.notebookElementData) {
                if (
                    this.notebookElementData.isTab &&
                    this.viewEditorModel.lastActiveNodeXpath !== this.notebookElementData.xpath
                ) {
                    return;
                }
                if (this.notebookElementData.restore) {
                    this.env.config.onNodeClicked(this.notebookElementData.xpath);
                } else {
                    // no element was currently highlighted, the editor sidebar must display the stored tab
                    this.viewEditorModel.resetSidebar(this.notebookElementData.sidebarTab);
                }
                this.notebookElementData = null;
            }
        });
    }

    beforeUnload() {}

    _shouldUseSubEnv() {
        return false;
    }
}
