import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class ResourceResource extends models.ServerModel {
    _name = "resource.resource";

    _load_pos_data_fields() {
        return [];
    }

    _records = [
        {
            id: 1,
            name: "resource 1",
            user_id: 3,
            resource_type: "user",
            employee_id: [3],
            write_date: "2025-01-01 10:00:00",
        },
    ];
}
patch(hootPosModels, [...hootPosModels, ResourceResource]);
