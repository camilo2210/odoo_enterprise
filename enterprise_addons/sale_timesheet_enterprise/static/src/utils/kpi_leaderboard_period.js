const { DateTime } = luxon;

const today = DateTime.local().endOf("day");

export function getPeriodRange(periodStart) {
    const start = (periodStart || today).startOf("month");
    const periodEnd = start.endOf("month");
    const stop = DateTime.min(today, periodEnd);
    return {
        start: start,
        stop: stop,
    }
}
