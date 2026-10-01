import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { SocialPostCalendarController } from "@social/js/social_post_calendar_controller";
import { SocialPostCalendarModel } from "@social/js/social_post_calendar_model";
import { SocialPostCalendarRenderer } from "@social/js/social_post_calendar_renderer";

export const SocialPostCalendarView = {
    ...calendarView,
    Controller: SocialPostCalendarController,
    Model: SocialPostCalendarModel,
    Renderer: SocialPostCalendarRenderer,
};
registry.category("views").add("social_post_calendar", SocialPostCalendarView);
