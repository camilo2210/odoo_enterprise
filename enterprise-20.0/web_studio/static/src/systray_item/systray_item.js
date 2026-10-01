import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import "@web_enterprise/webclient/promote_studio/promote_studio_systray_item";

import { Component, signal, useListener } from "@odoo/owl";

class StudioSystray extends Component {
    static template = "web_studio.SystrayItem";

    rootRef = signal.ref();

    setup() {
        this.hm = useService("home_menu");
        this.studio = useService("studio");
        this.isLoading = false;
        useListener(this.env.bus, "ACTION_MANAGER:UPDATE", () => {
            this.isLoading = true;
            if (this.rootRef()) {
                this.rootRef().classList.toggle("o_disabled", this.buttonDisabled);
            }
        });
        useListener(this.env.bus, "ACTION_MANAGER:UI-UPDATED", (ev) => {
            this.isLoading = false;
            const mode = ev.detail;
            if (mode !== "new" && this.rootRef()) {
                this.rootRef().classList.toggle("o_disabled", this.buttonDisabled);
            }
        });
    }
    get buttonDisabled() {
        return this.isLoading || !this.studio.isStudioEditable();
    }
    _onClick() {
        if (!this.isLoading) {
            this.studio.open();
        }
    }
}

export const systrayItem = {
    Component: StudioSystray,
    isDisplayed: () => user.isSystem,
};

registry.category("systray").remove("PromoteStudioSystrayItem");
registry.category("systray").add("StudioSystrayItem", systrayItem, { sequence: 1 });
