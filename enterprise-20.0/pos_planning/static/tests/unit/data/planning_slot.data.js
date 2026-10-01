import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class PlanningSlot extends models.ServerModel {
    _name = "planning.slot";

    _load_pos_data_fields() {
        return ["start_datetime", "end_datetime", "state", "resource_ids"];
    }

    _records = [
        {
            id: 1,
            start_datetime: "2025-09-17 10:00:00",
            end_datetime: "2025-09-17 12:00:00",
            resource_ids: [1],
            state: "2_published",
            write_date: "2025-01-01 10:00:00",
        },
    ];
}
patch(hootPosModels, [...hootPosModels, PlanningSlot]);
