import { RestaurantTable } from "@pos_restaurant/app/models/restaurant_table";
import { patch } from "@web/core/utils/patch";
import { getMin } from "@point_of_sale/utils";

const { DateTime } = luxon;
const MILLIS_IN_HOUR = 3600000;

patch(RestaurantTable.prototype, {
    startDateForDuration() {
        return this.firstAppointment?.start || super.startDateForDuration();
    },
    /**
     * Get the earliest upcoming appointment for a table.
     * Filters out past, cancelled, checked-in and no-show appointments.
     */
    get firstAppointment() {
        if (!this.appointment_resource_id) {
            return false;
        }

        const appointments = this.models["calendar.event"].getBy(
            "appointment_resource_ids",
            this.appointment_resource_id.id
        );

        if (!appointments) {
            return false;
        }

        const now = DateTime.now();
        const nowTs = now.ts;
        const startOfTodayTs = now.startOf("day").ts;
        const startOfTomorrowTs = now.plus({ days: 1 }).startOf("day").ts;
        const excludedStatuses = new Set(["attended", "no_show", "cancelled"]);

        const validAppointments = appointments.filter((a) => {
            const startTs = a.start.ts;
            const effectiveStartTs = Math.max(startTs, startOfTodayTs);
            const endTs = startTs + a.duration * MILLIS_IN_HOUR;

            return (
                effectiveStartTs < nowTs + MILLIS_IN_HOUR &&
                endTs > nowTs &&
                effectiveStartTs < startOfTomorrowTs &&
                !excludedStatuses.has(a.appointment_status)
            );
        });
        return validAppointments.length > 0
            ? getMin(validAppointments, { criterion: (a) => a.start.ts })
            : false;
    },
});
