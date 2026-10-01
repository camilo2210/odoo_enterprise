import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { useService } from "@web/core/utils/hooks";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { SIZES } from "@web/core/ui/ui_utils";

import { Component, proxy, useProps } from "@odoo/owl";

export class KnowledgeArticleChatter extends Component {
    static template = "knowledge.KnowledgeArticleChatter";
    static components = { Chatter };

    props = useProps(standardWidgetProps);

    setup() {
        this.panelState = proxy(this.env.panelState);
        this.ui = useService("ui");
    }

    get isChatterAside() {
        return this.ui.size >= SIZES.LG;
    }
}
