import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class PosUrbanpiperStore extends models.ServerModel {
    _name = "pos.urbanpiper.store";

    _load_pos_data_fields() {
        return ["name", "config_id", "delivery_provider_ids", "aggregator_lines"];
    }

    _records = [
        {
            name: "Gada Electronics",
            id: 1,
            config_id: 1,
            delivery_provider_ids: [1],
            aggregator_lines: [1],
        },
    ];
}

patch(hootPosModels, [...hootPosModels, PosUrbanpiperStore]);
