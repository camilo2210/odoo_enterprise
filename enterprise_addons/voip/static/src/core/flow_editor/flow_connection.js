import { Component, t, useProps } from "@odoo/owl";

export class FlowConnection extends Component {
    static template = "voip.FlowConnection";

    props = useProps({
        geometry: t.object(),
        onClick: t.function().optional(() => () => {}),
        selected: t.boolean().optional(false),
    });

    onClick(ev) {
        ev.stopPropagation();
        this.props.onClick({
            connectionId: this.props.geometry.id,
            originalEvent: ev,
        });
    }
}
