import { Component, t, useProps } from "@odoo/owl";

export class HangupFlowNode extends Component {
    static template = "voip.HangupFlowNode";

    props = useProps({
        node: t.object(),
        readonly: t.boolean(),
    });
}
