import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { OptionsDropdown } from "@knowledge/components/options_dropdown/options_dropdown";

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";

export class SidePanelToolbar extends Component {
    static template = "knowledge.SidePanelToolbar";
    static components = {
        OptionsDropdown,
    };

    props = useProps(standardWidgetProps);

    setup() {
        this.panelState = proxy(this.env.panelState);
        this.tocButton = proxy(this.env.tocButton);

        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup("base.group_user");
        });
    }

    get chatterButtonTitle() {
        return this.panelState.isDisplayed("chatter")
            ? _t("Close chatter panel")
            : _t("Open chatter panel");
    }

    get commentButtonTitle() {
        return this.panelState.isDisplayed("comments")
            ? _t("Close comments panel")
            : _t("Open comments panel");
    }

    togglePanel(panelName) {
        if (this.panelState.isDisplayed(panelName)) {
            this.panelState.setActivePanel();
        } else {
            this.panelState.setActivePanel(panelName);
        }
    }
}
