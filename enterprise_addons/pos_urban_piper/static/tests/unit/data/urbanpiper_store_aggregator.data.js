import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { models } from "@web/../tests/web_test_helpers";

export class UrbanpiperStoreAggregator extends models.ServerModel {
    _name = "urbanpiper.store.aggregator";

    _load_pos_data_fields() {
        return ["store_id", "delivery_provider_id", "is_online"];
    }

    _records = [{ id: 1, store_id: 1, delivery_provider_id: 1, is_online: true }];
}

patch(hootPosModels, [...hootPosModels, UrbanpiperStoreAggregator]);
