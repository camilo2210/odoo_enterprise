import { Order } from "@pos_enterprise/app/components/order/order";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    async doneOrder() {
        super.doneOrder();
        if (this.order.pos_order_id.delivery_identifier) {
            const orderPrepTime =
                (luxon.DateTime.now().ts - this.order.create_date.setZone("local").ts) /
                (1000 * 60);
            await this.prepDisplay.orm.call("pos.order", "order_status_update", [
                this.order.pos_order_id.id,
                "Food Ready",
                null,
                {
                    preparation_time: orderPrepTime,
                },
            ]);
        }
    },

    _computeDuration() {
        if (this.order.pos_order_id.delivery_identifier) {
            const total_order_time = this.order.create_date
                .setZone("local")
                .plus({ minutes: this.order.pos_order_id.prep_time || 0 });
            return Math.max(
                Math.round((total_order_time.ts - luxon.DateTime.now().ts) / (1000 * 60)),
                0
            );
        }
        return super._computeDuration();
    },
});
