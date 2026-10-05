import { patch } from "@web/core/utils/patch";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { TaskGanttModel } from "@project_enterprise/views/task_gantt/task_gantt_model";

patch(TaskGanttModel.prototype, {
    _processGanttData(metaData, data, ganttData) {
        if ("working_periods" in ganttData) {
            const workingPeriods = {};
            for (const [resource_id, periods] of Object.entries(ganttData.working_periods)) {
                workingPeriods[resource_id] = periods.map(({ start, end }) => ({
                        start: deserializeDateTime(start),
                        end: end && deserializeDateTime(end),
                }));
            }
            data.workingPeriods = workingPeriods;
        }
    }
});
