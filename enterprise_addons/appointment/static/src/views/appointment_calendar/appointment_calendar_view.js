import { AppointmentAttendeeCalendarModel } from "@appointment/views/appointment_calendar/appointment_calendar_model";
import { AppointmentAttendeeCalendarCommonRenderer } from "@appointment/views/appointment_calendar/common/appointment_calendar_common_renderer";
import { attendeeCalendarView } from "@calendar/views/attendee_calendar/attendee_calendar_view";
import { registry } from "@web/core/registry";

class AppointmentAttendeeRenderer extends attendeeCalendarView.Renderer {
    static components = {
        ...super.components,
        day: AppointmentAttendeeCalendarCommonRenderer,
        week: AppointmentAttendeeCalendarCommonRenderer,
    };
}

export const appointmentCalendarView = {
    ...attendeeCalendarView,
    Model: AppointmentAttendeeCalendarModel,
    Renderer: AppointmentAttendeeRenderer,
};

registry.category("views").add("appointment_calendar", appointmentCalendarView);
