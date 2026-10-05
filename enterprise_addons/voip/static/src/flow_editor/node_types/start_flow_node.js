import { Component, t, useProps } from "@odoo/owl";

export class StartFlowNode extends Component {
    static template = "voip.StartFlowNode";

    props = useProps({
        node: t.object(),
        readonly: t.boolean(),
    });
}
