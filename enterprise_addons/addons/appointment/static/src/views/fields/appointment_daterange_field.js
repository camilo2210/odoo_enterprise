import { registry } from "@web/core/registry";
import { DateTimeField, dateRangeField } from "@web/views/fields/datetime/datetime_field";
import { formatDateTime } from "@web/views/fields/formatters";

class AppointmentDateRangeField extends DateTimeField {

    /**@override*/
    getFormattedValue(valueIndex, numeric = this.props.numeric) {
        // get value (either start or end)
        const values = this.values;
        const value = values[valueIndex];
        if (!value) {
            return "";
        }
        const { showSeconds, showTime } = this.props;
        // end does not need to show its date if it's the same as the start's
        const showDate =
            !showTime || valueIndex !== 1 || !values[0] || !values[0].hasSame(value, "day");

        return formatDateTime(value, {
            numeric,
            showSeconds,
            showTime,
            showDate,
            showWeekday: showDate,
        });
    }
}

export const appointmentDateRangeField = {
    ...dateRangeField,
    component: AppointmentDateRangeField,
};

registry.category("fields").add("appointment_daterange", appointmentDateRangeField);
