import { AddRecordToCampaign } from "../add_record_to_campaign/add_record_to_campaign";
import { Component, useProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { registry } from "@web/core/registry";

const cogMenuRegistry = registry.category("cogMenu");

export class MarketingAutomationCogMenu extends Component {
    static template = "marketing_automation.MarketingAutomationCogMenu";
    static components = { Dropdown, AddRecordToCampaign };
    props = useProps();

    get root() {
        return this.env.model.root;
    }
}

cogMenuRegistry.add("marketing_automation-cog-menu", {
    Component: MarketingAutomationCogMenu,
    groupNumber: 30,
    isDisplayed: ({ config, searchModel }) =>
        config.actionType === "ir.actions.act_window" &&
        config.viewType === "form" &&
        !["marketing.activity", "marketing.participant", "marketing.campaign"].includes(
            searchModel.resModel
        ),
});
