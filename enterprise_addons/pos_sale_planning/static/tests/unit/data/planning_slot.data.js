import { patch } from "@web/core/utils/patch";
import { PlanningSlot } from "@pos_planning/../tests/unit/data/planning_slot.data";

patch(PlanningSlot.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "display_name", "partner_id"];
    },
});

PlanningSlot._records = PlanningSlot._records.map((record) => ({
    ...record,
    display_name: `Slot ${record.id} - Slot Partner`,
    partner_id: 3,
}));
