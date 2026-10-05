/* global posmodel */

import { POSAppointmentBookingGanttRenderer } from "@pos_appointment/app/gantt_overrides/gantt_renderer";
import { patch } from "@web/core/utils/patch";

patch(POSAppointmentBookingGanttRenderer, {
    rowContentTemplate: "pos_gantt.GanttRenderer.RowContent",
});

patch(POSAppointmentBookingGanttRenderer.prototype, {
    setup() {
        super.setup();
        this.orders = posmodel.models["pos.order"].getAll();
    },

    isBooked(column, row) {
        return (
            column.isToday &&
            this.orders.some(
                (o) =>
                    o.table_id?.appointment_resource_id?.id === row.resId &&
                    !o.finalized &&
                    o.isBooked
            )
        );
    },
    popoverButtons(record) {
        const buttons = super.popoverButtons(record);
        buttons.forEach((btn) => {
            if (btn.type === "check_in") {
                btn.onClick = async () => {
                    await this._updateAppointmentStatus(record, "attended");
                    if (!posmodel || record.appointment_type_schedule_based_on !== "resources") {
                        return;
                    }
                    const resources = await this.orm.read(
                        "appointment.resource",
                        record.resource_ids,
                        ["display_name"]
                    );
                    posmodel.showResourceAssignNotification(record, resources, {
                        viewMode: "gantt",
                    });
                };
            }
        });
        return buttons;
    },
});
