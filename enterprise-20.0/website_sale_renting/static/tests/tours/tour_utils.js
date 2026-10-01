import { localization } from "@web/core/l10n/localization";
import { Time } from "@web/core/l10n/time";
import { session } from "@web/session";

export function getFutureDate(days) {
    return luxon.DateTime.now().set({ weekday: 1 }).plus({ weeks: 1, days });
}

/**
 * First, if a product is rented by the hour, the default rental dates are computed as one hour
 * starting at the next hour from now. Move to a future date to ensure the time is not in the past.
 *
 * Second, since we move the rental period to the future, we first set the end date to avoid a
 * warning for setting a future start date after the current end date.
 */
export function chooseFutureRentalDates({
    offset =  { hours: 0 },
    duration = { hours: 1 },
    select_hours = true,
} = {}) {
    const futureStartDate = getFutureDate()
        .setZone(session.website_tz)  // Ensure time part is computed in the website timezone
        .set({ hour: 0, minute: 0, second: 0, millisecond: 0 })
        .plus(offset);
    const futureEndDate = futureStartDate.plus(duration);
    return [
        {
            content: "Set explicit future end date",
            trigger: "input[name=renting_end_date]",
            run: `edit ${futureEndDate.toFormat(localization.dateFormat)} && press Enter`,
        },
        {
            content: "Set explicit future start date",
            trigger: "input[name=renting_start_date]",
            run: `edit ${futureStartDate.toFormat(localization.dateFormat)} && press Enter`,
        },
        ...(select_hours ? [
            {
                content: "Set explicit future end time",
                trigger: "select[name=rental_end_time]:visible",
                run: `select ${Time.from(futureEndDate).toString()}`,
            },
            {
                content: "Set explicit future start time",
                trigger: "select[name=rental_start_time]:visible",
                run: `select ${Time.from(futureStartDate).toString()}`,
            },
        ] : []),
    ]
}
