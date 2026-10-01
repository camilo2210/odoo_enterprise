import { CallCalendarModel } from "@voip/views/call_calendar/call_calendar_model";
import { CallCalendarRenderer } from "@voip/views/call_calendar/call_calendar_renderer";

import { calendarView } from "@web/views/calendar/calendar_view";
import { registry } from "@web/core/registry";

export const CallCalendarView = {
    ...calendarView,
    Model: CallCalendarModel,
    Renderer: CallCalendarRenderer,
};

registry.category("views").add("voip_call_calendar", CallCalendarView);
