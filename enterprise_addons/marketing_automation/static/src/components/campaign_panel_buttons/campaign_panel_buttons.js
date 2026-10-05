import { _t } from "@web/core/l10n/translation";
import { Component, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class MarketingCampaignPanelButtons extends Component {
    static template = "marketing_automation.MarketingCampaignPanelButtons";

    props = useProps(standardWidgetProps);

    setup() {
        this.panelState = proxy(this.env.panelState);
    }

    /** @param {string} panelName */
    togglePanel(panelName) {
        if (this.panelState.activePanel === panelName) {
            this.panelState.activePanel = undefined;
        } else {
            this.panelState.activePanel = panelName;
        }
    }

    /** @returns {string} */
    get chatterButtonTitle() {
        return this.panelState.activePanel === "chatter"
            ? _t("Close chatter panel")
            : _t("Open chatter panel");
    }
}

registry.category("view_widgets").add("campaign_panel_buttons", {
    component: MarketingCampaignPanelButtons,
});
