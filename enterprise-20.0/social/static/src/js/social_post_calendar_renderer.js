import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { SocialPostCommonRenderer } from "@social/js/social_post_calendar_common_renderer";
import { SocialPostCalendarYearRenderer } from "@social/js/social_post_calendar_year_renderer";

export class SocialPostCalendarRenderer extends CalendarRenderer {
    static components = {
        ...CalendarRenderer.components,
        day: SocialPostCommonRenderer,
        week: SocialPostCommonRenderer,
        month: SocialPostCommonRenderer,
        year: SocialPostCalendarYearRenderer,
    };
}
