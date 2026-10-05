import { registry } from "@web/core/registry";
import {
    StateSelectionField,
    stateSelectionField,
} from "@web/views/fields/state_selection/state_selection_field";

export class SlotStateSelectionField extends StateSelectionField {
    setup() {
        super.setup();
        this.colors = {
            "2_published": "green",
        };
    }
}

export const slotStateSelectionField = {
    ...stateSelectionField,
    component: SlotStateSelectionField,
};

registry.category("fields").add("slot_state_selection", slotStateSelectionField);
