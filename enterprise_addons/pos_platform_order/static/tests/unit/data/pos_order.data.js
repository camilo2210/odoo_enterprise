import { PosOrder } from "@point_of_sale/../tests/unit/data/pos_order.data";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    mark_platform_prep_order_as_printed() {
        return true;
    },
});
