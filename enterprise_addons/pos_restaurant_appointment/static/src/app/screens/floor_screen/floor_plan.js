import { FloorPlan } from "@pos_restaurant/app/screens/floor_screen/floor_plan/floor_plan";
import { patch } from "@web/core/utils/patch";
import { usePopover } from "@web/core/popover/popover_hook";
import { useTimedPress } from "@point_of_sale/app/utils/use_timed_press";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ConfirmAppointmentPopup } from "@pos_restaurant_appointment/app/components/confirm_appointment_popup/confirm_appointment_popup";
import { LONG_PRESS_DURATION } from "@point_of_sale/utils";
import { _t } from "@web/core/l10n/translation";
import { Tooltip } from "@web/core/tooltip/tooltip";

const { DateTime } = luxon;

patch(FloorPlan.prototype, {
    setup() {
        super.setup(...arguments);

        // Setup long press handlers for table appointments
        useTimedPress(this.containerRef, [
            {
                type: "hold",
                delay: LONG_PRESS_DURATION,
                callback: async (event) => {
                    if (!this.pos.isAppointmentTransferMode) {
                        const appointmentId = this.getAppointmentFromTimedPressEvent(event);
                        if (appointmentId) {
                            await this.pos.assignResourceToAppointment(appointmentId);
                            this._updateTimer();
                        }
                    }
                },
            },
            {
                type: "release",
                delay: LONG_PRESS_DURATION,
                callback: (event) => {
                    event.stopPropagation();
                },
            },
        ]);
        this.tooltip = usePopover(Tooltip, { position: "bottom" });
    },

    onClickAppointment(event) {
        event.stopPropagation();
        this.tooltip.open(event.target, { tooltip: _t("Long press to reassign") });
        setTimeout(this.tooltip.close, 1000);
    },
    isCustomerLate(appointment) {
        const dateNow = DateTime.now();
        return (
            appointment &&
            dateNow > appointment.start &&
            appointment.appointment_status === "booked"
        );
    },

    getAppointmentFromTimedPressEvent(event) {
        const label = event.target.closest("[data-appointment-id]");
        const appointmentId = Number(label?.dataset.appointmentId);
        return appointmentId ? appointmentId : false;
    },

    async onClickTable(table, ev) {
        if (this.pos.isAppointmentTransferMode) {
            return;
        }

        const currentOrder = table.getOrders().find((order) => !order.finalized);
        const appointment = table.firstAppointment;

        if (!appointment || currentOrder?.calendar_event_ids.length) {
            return await super.onClickTable(...arguments);
        }

        const payload = await makeAwaitable(this.pos.dialog, ConfirmAppointmentPopup, {
            appointment,
        });
        if (!payload) {
            return;
        }
        await super.onClickTable(...arguments);
        const order = currentOrder || this.pos.getOrder();

        if (payload === "confirm" && order) {
            await this.pos.data.write("calendar.event", [appointment.id], {
                appointment_status: "attended",
                start: DateTime.now().toUTC().toFormat("yyyy-LL-dd HH:mm:ss"),
            });
            order.update({
                calendar_event_ids: [appointment.id],
                partner_id: appointment.partner_ids[0],
            });
        } else if (payload === "another_guest") {
            this.pos.assignResourcesAutomatically(appointment, table.appointment_resource_id.id);
        }
    },
    getTimerClasses(table) {
        const appointment = table.firstAppointment;
        if (
            this.floorPlanStore.isKanban() &&
            appointment &&
            appointment.id === this.pos.bookingSelectionAppointment?.id
        ) {
            return "text-bg-info bg-opacity-50";
        } else if (this.isCustomerLate(appointment)) {
            return "text-bg-danger bg-opacity-75";
        } else {
            return super.getTimerClasses(table);
        }
    },
});
