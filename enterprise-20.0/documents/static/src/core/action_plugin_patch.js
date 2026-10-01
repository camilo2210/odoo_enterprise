import { usePlugin } from "@odoo/owl";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";
import { UIPlugin } from "@web/core/ui/ui_plugin";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

/**
 * Saves the documents current view mode (only kanban or list)
 * in local storage to keep track of the user preferred mode.
 * Not applied in mobile environments (uses the "mobile_view_mode"
 * action field which defaults on "kanban").
 */
patch(ActionPlugin.prototype, {
    setup() {
        super.setup();
        const ui = usePlugin(UIPlugin);
        const superSwitchView = this.switchView;
        this.switchView = async (viewType, props = {}, { newWindow } = {}) => {
            if (
                !ui.isSmall() &&
                this.currentController?.action?.xml_id == "documents.document_action"
            ) {
                const defaultViewType = browser.localStorage.getItem("documentsDefaultViewType");
                if (["kanban", "list"].includes(viewType) && defaultViewType != viewType) {
                    browser.localStorage.setItem("documentsDefaultViewType", viewType);
                }
            }
            return superSwitchView(viewType, props, { newWindow });
        };
    },
});
