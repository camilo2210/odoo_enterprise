import { SlotStateSelectionField } from "@planning/components/slot_state_selection/slot_state_selection_field";
import { patch } from "@web/core/utils/patch";

patch(SlotStateSelectionField.prototype, {
    setup() {
        super.setup();
        this.colors = {
            "2_published": "blue",
            "4_completed": "green",
        };
    },
});
