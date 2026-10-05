import { ScheduleGanttModel } from "@sale_renting/views/schedule_gantt/schedule_gantt_model";
import { patch } from "@web/core/utils/patch";

patch(ScheduleGanttModel.prototype, {
    async _fetchData(metaData, additionalContext = {}) {
        return await super._fetchData(metaData, {
            ...additionalContext,
            display_renting_stock_quantity: true,
        });
    },
})
