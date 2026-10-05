/* global posmodel */

import { ListController } from "@web/views/list/list_controller";
import { PosAppointmentSearchFilter } from "../components/pos_appointment_search_filter/pos_appointment_search_filter";

export class PosAppointmentListController extends ListController {
    static template = "pos_appointment.PosAppointmentListController";
    static components = {
        ...ListController.components,
        PosAppointmentSearchFilter,
    };
    async createRecord(context) {
        const onRecordSaved = async () => {
            const root = this.model.root;
            const { limit, offset } = root;
            await root.load({ offset, limit });
        };
        return await posmodel.createBooking(onRecordSaved.bind(this));
    }
    async openRecord(record, { force, newWindow } = { force: false }) {
        const onRecordSaved = async () => {
            const root = this.model.root;
            const { limit, offset } = root;
            await root.load({ offset, limit });
        };
        return await posmodel.editBooking(record.resId, onRecordSaved.bind(this));
    }
}
