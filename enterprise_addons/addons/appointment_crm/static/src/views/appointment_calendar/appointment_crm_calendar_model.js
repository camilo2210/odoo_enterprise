import { AttendeeCalendarModel } from "@calendar/views/attendee_calendar/attendee_calendar_model";
import { patch } from "@web/core/utils/patch";

patch(AttendeeCalendarModel.prototype, {
    _getInviteParams() {
        return {
            ...super._getInviteParams(),
            opportunity_id: this.meta.context.default_opportunity_id,
        };
    },
});
