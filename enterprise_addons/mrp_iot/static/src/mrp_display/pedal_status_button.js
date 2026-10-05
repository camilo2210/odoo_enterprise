import { Component, useProps, t } from "@odoo/owl";

export class PedalStatusButton extends Component {
    static template = "mrp_iot.PedalStatusButton";
    props = useProps({
        pedalConnected: t.boolean(),
        takeOwnership: t.function(),
    });
}
