import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

import { PlanningGanttRendererControls } from "@planning/views/planning_gantt/planning_gantt_renderer_controls";

patch(PlanningGanttRendererControls.prototype, {
    get updateTravelTimesTitle() {
        return _t("Update travel times as they are out-of-date");
    },
});
