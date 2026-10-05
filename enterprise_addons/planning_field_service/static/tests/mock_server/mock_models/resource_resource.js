import { fields, serverState } from "@web/../tests/web_test_helpers";

import { planningModels } from "@planning/../tests/planning_mock_models";

export class ResourceResource extends planningModels.ResourceResource {
    color = fields.Integer();
    resource_type = fields.Selection({
        selection: [
            ["user", "Human"],
            ["material", "Material"],
        ],
    });
    live_latitude = fields.Float();
    live_longitude = fields.Float();
    live_location_last_update = fields.Datetime();

    _records = [
        ...planningModels.ResourceResource._records,
        { id: 1, name: "Mitchell Admin", user_id: serverState.userId },
        { id: 2, name: "Technician", user_id: 8 },
    ];
}
