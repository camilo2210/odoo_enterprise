import { patch } from "@web/core/utils/patch";
import {
    CalendarHoursByDay,
    calendarHoursByDay,
    formatHoursLabel,
    WEEKDAY_LABELS,
} from "@resource/views/fields/resource_calendar_hours_by_day/resource_calendar_hours_by_day";

patch(CalendarHoursByDay.prototype, {
    get hoursByDay() {
        const hoursByDay = [0, 0, 0, 0, 0, 0, 0];
        const wrmHoursByDay = [0, 0, 0, 0, 0, 0, 0];
        const wrmColorByDay = [0, 0, 0, 0, 0, 0, 0];
        for (const attendance of this.attendances) {
            const {
                dayofweek,
                date,
                duration_hours,
                l10n_be_is_time_credit,
                l10n_be_reorganisation_measure_color,
            } = attendance.data;
            if (date) {
                // ignore variable schedules (date-specific attendances)
                continue;
            }
            const index = Number(dayofweek);
            if (l10n_be_is_time_credit) {
                wrmHoursByDay[index] += duration_hours;
                wrmColorByDay[index] = l10n_be_reorganisation_measure_color || wrmColorByDay[index]; // keep this attendance's own color (calendar can have many WRM hours across different days' attendances)
            } else {
                hoursByDay[index] += duration_hours;
            }
        }
        return hoursByDay.map((hours, index) => ({
            hours: hours ? formatHoursLabel(hours) : "",
            wrmHours: wrmHoursByDay[index] ? formatHoursLabel(wrmHoursByDay[index]) : "",
            wrmColorClass: `o_wrm_text_color_${wrmColorByDay[index]}`,
            noHours: !hours && !wrmHoursByDay[index],
            label: WEEKDAY_LABELS[index],
        }));
    },
});

const superRelatedFields = calendarHoursByDay.relatedFields;
calendarHoursByDay.relatedFields = (fieldInfo) => [
    ...superRelatedFields(fieldInfo),
    { name: "l10n_be_is_time_credit", type: "boolean" },
    { name: "l10n_be_reorganisation_measure_color", type: "integer" },
];
