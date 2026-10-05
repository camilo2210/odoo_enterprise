import { patch } from "@web/core/utils/patch";
import { Order } from "@pos_enterprise/app/components/order/order";
import { useService } from "@web/core/utils/hooks";

patch(Order.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },
    async doneOrder() {
        const posOrder = this.order.pos_order_id;
        if (posOrder.platform_order_ref) {
            await this.orm.call("pos.order", "platform_order_status_update_from_ui", [
                posOrder.id,
                "food_ready",
            ]);
        }
        return super.doneOrder(...arguments);
    },
});
