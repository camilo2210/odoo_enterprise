import { AttendeeCalendarModel } from "@calendar/views/attendee_calendar/attendee_calendar_model";
import { patch } from "@web/core/utils/patch";

patch(AttendeeCalendarModel.prototype, {
    // Avoid fetching working hours on the appointment attendee calendar
    // since the view already includes available slots.
    async fetchWorkingHours() {
        if (
            this.meta.context.active_model === "appointment.type" &&
            this.meta.context.active_id &&
            ["day", "week"].includes(this.scale)
        ) {
            return [];
        }
        return super.fetchWorkingHours(...arguments);
    },
});
