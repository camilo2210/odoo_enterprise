import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    get displayName() {
        if (this.pos_order_id?.planning_slot_id && this.payment_method_id.type === "resource") {
            return `${this.payment_method_id.name} (${this.pos_order_id.planning_slot_id.display_name})`;
        }
        return super.displayName;
    },
});
