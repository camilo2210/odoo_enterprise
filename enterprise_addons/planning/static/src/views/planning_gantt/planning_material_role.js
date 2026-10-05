import { setupDisplayName } from "../planning_hooks";
import { Component, signal, t, useProps } from "@odoo/owl";

export class PlanningMaterialRole extends Component {
    static template = "planning.PlanningMaterialRole";

    props = useProps({
        displayName: t.string(),
    });

    setup() {
        this.displayNameRef = signal.ref();
        setupDisplayName(this.displayNameRef);
    }
}
