/* global posmodel */

import { PosAppointmentListRenderer } from "@pos_appointment/app/list_extend/list_renderer";

export class PosResAppointmentListRenderer extends PosAppointmentListRenderer {
    static recordRowTemplate = "pos_restaurant_appointment.PosResAppointmentListRenderer.RecordRow";
    async setTable(appointment) {
        if (posmodel) {
            await posmodel.assignResourceToAppointment(
                appointment.resId,
                posmodel.manageBookings.bind(posmodel),
                {
                    viewMode: "list",
                }
            );
        }
    }
}
