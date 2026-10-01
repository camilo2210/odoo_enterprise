import { registry } from "@web/core/registry";
import { Component, t, useProps } from "@odoo/owl";
import { useInactivity } from "../use_inactivity";

export class EndPage extends Component {
    static template = "frontdesk.EndPage";

    props = useProps({
        hostData: t.any().optional(),
        isMobile: t.boolean(),
        onClose: t.function(),
        showScreen: t.function(),
        theme: t.string(),
    });
    setup() {
        if (!this.props.isMobile) {
            useInactivity(() => this.props.onClose(), 15000);
        }
    }
}

registry.category("frontdesk_screens").add("EndPage", EndPage);
