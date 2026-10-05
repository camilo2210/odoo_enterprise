import { CalendarModel } from "@web/views/calendar/calendar_model";
import { is24HourFormat } from "@web/core/l10n/time";
import { _t } from "@web/core/l10n/translation";
import { unique } from "@web/core/utils/arrays";

export class CallCalendarModel extends CalendarModel {
    setup(params) {
        // always fetch those fields as they'll be used by this model
        const extraFields = ["partner_id", "phone_number", "direction"];
        params.fieldNames = unique(params.fieldNames.concat(extraFields));

        super.setup(...arguments);
    }

    /**
     * Adds a customized title with contact info and time, sets a titleIcon
     * based on call direction, and adds a hasEndDate property to mark records
     * with end date.
     *
     * @override
     * @param {Object} rawRecord The raw record object.
     * @returns {Object} The normalized record object.
     */
    normalizeRecord(rawRecord) {
        const record = super.normalizeRecord(...arguments);
        const { fieldMapping } = this.meta;

        const hasEndDate = Boolean(rawRecord[fieldMapping.date_stop]);
        if (!hasEndDate) {
            record.end = record.start;
            record.duration = 0;
        }
        record.hasEndDate = hasEndDate;

        record.title = _t("%(contact_info)s, %(time)s", {
            contact_info: rawRecord.partner_id?.[1] || rawRecord.phone_number,
            time: record.start.toFormat(is24HourFormat() ? "HH:mm" : "hh:mm a"),
        });
        record.titleIcon = rawRecord.direction === "outgoing" ? "north_east" : "south_west";

        return record;
    }
}
