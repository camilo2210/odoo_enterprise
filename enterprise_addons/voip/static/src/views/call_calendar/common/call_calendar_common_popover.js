import { is24HourFormat } from "@web/core/l10n/time";
import { _t } from "@web/core/l10n/translation";
import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { getFormattedDateSpan } from "@web/views/calendar/utils";

export class CallCalendarCommonPopover extends CalendarCommonPopover {
    /**
     * @param {DateTime} start
     * @param {DateTime} end
     * @param {string} timeFormat
     * @returns {string|ReturnType<_t>}
     */
    callFormatTimeRange(start, end, timeFormat) {
        if (this.props.record.hasEndDate) {
            return _t("%(start_time)s – %(end_time)s", {
                start_time: start.toFormat(timeFormat),
                end_time: end.toFormat(timeFormat),
            });
        }
        return start.toFormat(timeFormat);
    }

    /**
     * @override
     * @param {DateTime} start
     * @param {DateTime} end
     * @returns {string}
     */
    formatDateRange(start, end) {
        if (this.timeDuration) {
            return _t("%(date)s • %(time)s (%(duration)s)", {
                date: getFormattedDateSpan(start, end, {
                    sameDayFormat: "cccc, DDD",
                }),
                time: this.callFormatTimeRange(
                    this.props.record.start,
                    this.props.record.end,
                    is24HourFormat() ? "HH:mm" : "hh:mm a"
                ),
                duration: this.timeDuration,
            });
        }
        return _t("%(date)s • %(time)s", {
            date: getFormattedDateSpan(start, end, {
                sameDayFormat: "cccc, DDD",
            }),
            time: this.callFormatTimeRange(
                this.props.record.start,
                this.props.record.end,
                is24HourFormat() ? "HH:mm" : "hh:mm a"
            ),
        });
    }

    /**
     * @override Overrides the parent method to return null to hide the time range in the popover.
     * @param {DateTime} start
     * @param {DateTime} end
     * @param {string} timeFormat
     * @returns {string|ReturnType<_t>}
     */
    formatTimeRange(start, end, timeFormat) {
        return null;
    }

    /**
     * @override
     * @param {number} duration
     * @returns {string|null}
     */
    formatTimeDuration(duration) {
        if (this.props.record.hasEndDate) {
            return super.formatTimeDuration(duration);
        }
        return null;
    }
}
