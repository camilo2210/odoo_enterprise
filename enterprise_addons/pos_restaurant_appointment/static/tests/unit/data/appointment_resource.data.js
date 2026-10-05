import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class AppointmentResource extends models.ServerModel {
    _name = "appointment.resource";

    _load_pos_data_fields() {
        return ["pos_table_ids"];
    }

    _records = [
        {
            id: 1,
            pos_table_ids: [2],
            write_date: "2025-01-01 10:00:00",
        },
        {
            id: 2,
            pos_table_ids: [3],
            write_date: "2025-01-01 10:00:00",
        },
        {
            id: 3,
            pos_table_ids: [4],
            write_date: "2025-01-01 10:00:00",
        },
        {
            id: 4,
            pos_table_ids: [14],
            write_date: "2025-01-01 10:00:00",
        },
        {
            id: 5,
            pos_table_ids: [15],
            write_date: "2025-01-01 10:00:00",
        },
        {
            id: 6,
            pos_table_ids: [16],
            write_date: "2025-01-01 10:00:00",
        },
    ];
}

patch(hootPosModels, [...hootPosModels, AppointmentResource]);
