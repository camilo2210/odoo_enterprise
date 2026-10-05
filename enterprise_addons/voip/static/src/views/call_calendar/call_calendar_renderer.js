import { CallCalendarCommonRenderer } from "@voip/views/call_calendar/common/call_calendar_common_renderer";

import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";

export class CallCalendarRenderer extends CalendarRenderer {
    static components = {
        ...CalendarRenderer.components,
        day: CallCalendarCommonRenderer,
        week: CallCalendarCommonRenderer,
        month: CallCalendarCommonRenderer,
    };
}
