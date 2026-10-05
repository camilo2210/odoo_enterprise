import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    isSaleOrderLineNote(orderLine) {
        return (
            super.isSaleOrderLineNote(orderLine) ||
            orderLine.display_type === "subscription_discount"
        );
    },
});
