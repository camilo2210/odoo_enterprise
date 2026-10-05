import { PlanningCalendarController } from "@planning/views/planning_calendar/planning_calendar_controller";
import { patch } from "@web/core/utils/patch";

patch(PlanningCalendarController.prototype, {
    get displayAutoPlanButton() {
        return (
            super.displayAutoPlanButton &&
            (!this.model.geolocation.useMapBoxAPI || this.model.scale === "day")
        );
    },
});
