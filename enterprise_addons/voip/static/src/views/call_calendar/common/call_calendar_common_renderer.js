import { CallCalendarCommonPopover } from "@voip/views/call_calendar/common/call_calendar_common_popover";

import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";

export class CallCalendarCommonRenderer extends CalendarCommonRenderer {
    static components = {
        ...CalendarCommonRenderer.components,
        Popover: CallCalendarCommonPopover,
    };
}
