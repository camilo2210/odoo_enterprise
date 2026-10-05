import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { AppraisalGanttModel } from "./appraisal_gantt_model";
import { registry } from "@web/core/registry";

const viewRegistry = registry.category("views");

export const appraisalGanttView = {
    ...hrGanttView,
    Model: AppraisalGanttModel,
    searchMenuTypes: ["filter", "groupBy", "favorite"],
};

viewRegistry.add("appraisal_gantt", appraisalGanttView);
