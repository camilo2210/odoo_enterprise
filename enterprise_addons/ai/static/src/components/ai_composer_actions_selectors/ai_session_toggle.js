import { Component, useProps, t } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";

export class AiSessionToggle extends Component {
    static template = "ai.SessionToggle";
    static components = { CheckBox };

    props = useProps({
        aiSession: t.object(),
        configAttribute: t.string(),
    });

    setup() {
        this.attr = this.props.configAttribute;
    }
}
