import { patch } from "@web/core/utils/patch";

import { PlanningGanttController } from "@planning/views/planning_gantt/planning_gantt_controller";

patch(PlanningGanttController.prototype, {
    get displayAutoPlanButton() {
        return !this.model.geolocation.useMapBoxAPI || this.model.metaData.rangeId === "day";
    },
    async autoPlan() {
        await this.planningControllerActions.autoPlan(async (res) => {
            const { open_shift_assigned = [], sale_line_planned = [] } = res;
            const plannedRecordIds = open_shift_assigned.concat(sale_line_planned);
            // reload to gather assigned records
            await this.model.fetchData();
            const plannedResourceIds = new Set(
                this.model.data.records
                    .filter((r) => plannedRecordIds.includes(r.id))
                    .flatMap((r) => r.resource_ids)
            );
            await this.model._updateTravelTimes(true, plannedResourceIds);
            // reload to gather rescheduled records
            await this.model.fetchData();
        });
    },
});
