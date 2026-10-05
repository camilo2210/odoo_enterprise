import { patch } from "@web/core/utils/patch";
import { Many2OneResourceCalendarField } from "@resource/views/fields/resource_calendar_many2one/resource_calendar_many2one";

patch(Many2OneResourceCalendarField.prototype, {
    get specification() {
        const spec = super.specification;
        return {
            ...spec,
            attendance_ids: {
                fields: {
                    ...spec.attendance_ids.fields,
                    l10n_be_is_time_credit: {},
                },
            },
            l10n_be_reorganisation_measure_ids: {
                fields: { name: {} },
            },
        };
    },

    // flag the days that have WRM hours with a "*"
    hoursByDay(record) {
        const days = super.hoursByDay(record);
        for (const attendance of record.attendance_ids || []) {
            if (!attendance.date && attendance.l10n_be_is_time_credit) {
                days[Number(attendance.dayofweek)].marker = "*";
            }
        }
        return days;
    },

    getWrmInfo(record) {
        const [measure] = record.l10n_be_reorganisation_measure_ids || [];
        return measure ? { marker: "*", name: measure.name } : null;
    },
});
