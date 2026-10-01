import { CalendarModel } from "@web/views/calendar/calendar_model";

export class SocialPostCalendarModel extends CalendarModel {
    /**
     * When scheduling the post today, set the date in 1 hour.
     */
    getAllDayDates(start, end = start) {
        const [startDate, endDate] = super.getAllDayDates(start, end);
        const now = luxon.DateTime.now();
        if (start.hasSame(now, "day")) {
            const nextHour = now.plus({ hours: 1 });
            return [nextHour, nextHour];
        }
        return [startDate, endDate];
    }

    /**
     * Write on `scheduled_date` to let the computed of
     * `min_calendar_date` and `max_calendar_date` if we changed the dates
     * after the creation.
     */
    makeContextDefaults(rawRecord) {
        const context = super.makeContextDefaults(rawRecord);
        context.default_scheduled_date = context.default_max_calendar_date;
        delete context.default_max_calendar_date;
        delete context.default_min_calendar_date;
        return context;
    }
}
