/* global posmodel */

import { PosAppointmentListController } from "@pos_appointment/app/list_extend/list_controller";

export class PosResAppointmentListController extends PosAppointmentListController {
    static template = "pos_restaurant_appointment.PosResAppointmentListController";
    get totalAvailableCapacity() {
        return posmodel.getTotalAvailableCapacity(this.model.root.records);
    }
}
