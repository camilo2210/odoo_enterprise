import { patch } from "@web/core/utils/patch";
import { PosConfig } from "@point_of_sale/../tests/unit/data/pos_config.data";

patch(PosConfig.prototype, {
    get_urbanpiper_order_data() {
        return {
            delivery_order_count: 1,
            delivery_providers: [{ code: "doordash", name: "DoorDash", id: 1 }],
            total_new_order: 2,
        };
    },
});

PosConfig._records = PosConfig._records.map((record) => ({
    ...record,
    module_pos_urban_piper: true,
    urbanpiper_store_id: 1,
}));
