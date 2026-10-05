import { patch } from "@web/core/utils/patch";
import { PosConfig } from "@point_of_sale/../tests/unit/data/pos_config.data";

patch(PosConfig.prototype, {
    _load_self_data_models() {
        return [...super._load_self_data_models(), "iot.device", "iot.box"];
    },
});
