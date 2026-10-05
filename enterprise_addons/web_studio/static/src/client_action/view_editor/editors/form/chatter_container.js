import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import "@mail/chatter/web/chatter_patch";

import { Component, useProps, t } from "@odoo/owl";

export class ChatterContainer extends Chatter {
    static template = "web_studio.ChatterContainer";

    setup() {
        super.setup(...arguments);
        this.studioProps = useProps({ studioXpath: t.string().optional() });
    }

    onClick(ev) {
        this.env.config.onNodeClicked(this.studioProps.studioXpath);
    }
}

export class ChatterContainerHook extends Component {
    static template = "web_studio.ChatterContainerHook";
    static components = { Chatter };

    props = useProps({
        chatterData: t.object(),
        threadModel: t.string(),
    });

    onClick() {
        this.env.viewEditorModel.doOperation({
            type: "chatter",
            model: this.env.viewEditorModel.resModel,
            ...this.props.chatterData,
        });
    }
}
