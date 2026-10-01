import { fields } from "@web/../tests/web_test_helpers";

import { planningModels } from "@planning/../tests/planning_mock_models";

export class ResPartner extends planningModels.ResPartner {
    partner_latitude = fields.Float({ string: "Latitude" });
    partner_longitude = fields.Float({ string: "Longitude" });
    contact_address_complete = fields.Char({ string: "Address" });

    _records = [
        ...planningModels.ResPartner._records,
        {
            id: 520,
            name: "Foo",
            partner_latitude: 50.2,
            partner_longitude: 4.55,
            contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
        },
    ];

    update_latitude_longitude() {
        return true;
    }
}
