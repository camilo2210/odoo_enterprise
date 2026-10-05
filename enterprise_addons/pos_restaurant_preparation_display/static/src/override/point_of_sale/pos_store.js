import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async onPrepLinesSynced(prepLinePairs) {
        await super.onPrepLinesSynced(prepLinePairs);
        if (prepLinePairs.length) {
            await this.data.call("pos.prep.line", "apply_stage_from_source", [prepLinePairs]);
        }
    },
    async fireCourse(course) {
        const order = course.order_id;
        if (typeof course.id !== "number" || order.isDirty()) {
            await this.syncAllOrders({ orders: [order] });
        }
        await super.fireCourse(course);
        await this.data.call("pos.prep.order", "fire_course", [course.order_id.id, course.id]);
    },
});
