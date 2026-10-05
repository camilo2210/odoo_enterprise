import { useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { Order } from "@pos_enterprise/app/components/order/order";

patch(Order.prototype, {
    setup() {
        super.setup();
        this.didMount = false;
        // Ensure the correct duration is calculated immediately when switching from "pending" to a non-pending state
        useEffect(() => {
            const isPending = this.isPending;
            if (!this.didMount) {
                this.didMount = true;
                return;
            }
            if (!isPending) {
                this._updateDuration();
            }
        });
    },
    get isPending() {
        const course = this.props.order.course_id;
        return this.isInFirstStage() && course && !course.fired;
    },
    isInFirstStage() {
        return (
            this.prepDisplay.data.models["pos.prep.stage"].getFirst().id ===
            this.props.order.stage.id
        );
    },
    _getOrderDuration() {
        if (this.isInFirstStage() && this.props.order.course_id?.fired_date) {
            const timeDiff = (
                (luxon.DateTime.now().ts - this.props.order.course_id.fired_date?.ts) /
                1000
            ).toFixed(0);
            return Math.round(timeDiff / 60);
        }
        return super._getOrderDuration();
    },
    get cardColor() {
        const cardColor = super.cardColor;
        const tableId = this.order.pos_order_id.table_id?.id;
        let tableOrdersInStage = [];

        if (tableId && this.prepDisplay.tables[tableId].length) {
            const tableOrders = this.prepDisplay.tables[tableId];
            tableOrdersInStage = tableOrders.filter(
                (stageId) => stageId === this.props.order.stage.id
            );

            if (this.prepDisplay.selectedStageId === 0) {
                tableOrdersInStage = tableOrders;
            }
        }

        const index = tableId % 9 ? tableId % 9 : 4;
        return tableOrdersInStage.length > 1 ? "o_pdis_card_color_" + index : cardColor;
    },
    get order_name() {
        const table = this.order.pos_order_id.table_id;
        const course = this.props.order.course_id;
        const useCourseAllocation = this.order.pos_order_id.config_id.use_course_allocation;
        const courseLabel = useCourseAllocation && course?.name ? course.name : `C${course?.index}`;
        const courseSuffix = course ? ` - ${courseLabel}` : "";
        if (table) {
            return `T${table.table_number}${courseSuffix}`;
        }
        return (super.order_name || "Direct Sale") + courseSuffix;
    },
});
