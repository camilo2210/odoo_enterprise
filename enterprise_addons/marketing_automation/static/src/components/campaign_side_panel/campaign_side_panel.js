import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { Component, proxy, t, useProps } from "@odoo/owl";
import { SIZES } from "@web/core/ui/ui_utils";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";

export class CampaignSidePanel extends Component {
    static template = "marketing_automation.CampaignSidePanel";

    static components = {
        Chatter,
    };

    props = useProps({
        ...standardWidgetProps,
        additionalClasses: t.string().optional(),
    });

    setup() {
        super.setup();
        this.panelState = proxy(this.env.panelState);
        this.ui = useService("ui");
    }

    closeSidePanel() {
        this.panelState.activePanel = undefined;
    }

    /** @returns {boolean} */
    get isChatterAside() {
        return this.ui.size >= SIZES.LG;
    }
}
