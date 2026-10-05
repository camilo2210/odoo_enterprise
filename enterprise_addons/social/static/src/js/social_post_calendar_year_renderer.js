import { CalendarYearRenderer } from "@web/views/calendar/calendar_year/calendar_year_renderer";

export class SocialPostCalendarYearRenderer extends CalendarYearRenderer {
    get interactiveOptions() {
        return {
            ...super.interactiveOptions,
            selectable: false,
        };
    }
}
