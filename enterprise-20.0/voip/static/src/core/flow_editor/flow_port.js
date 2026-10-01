import { Component, t, useProps } from "@odoo/owl";

export class FlowPort extends Component {
    static template = "voip.FlowPort";

    props = useProps({
        connected: t.boolean().optional(false),
        nodeId: t.any(),
        offset: t.number(),
        onPointerDown: t.function().optional(() => () => {}),
        port: t.object(),
        validation: t.string().optional(),
    });

    get style() {
        return `top: ${this.props.offset * 100}%;`;
    }

    onClick(ev) {
        ev.stopPropagation();
    }

    onPointerDown(ev) {
        ev.stopPropagation();
        this.props.onPointerDown({
            nodeId: this.props.nodeId,
            port: this.props.port,
            originalEvent: ev,
        });
    }
}
