/* global posmodel */

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { PosAppointmentSearchFilter } from "../components/pos_appointment_search_filter/pos_appointment_search_filter";

export class PosKanbanController extends KanbanController {
    static template = "pos_appointment.KanbanController";
    static components = {
        ...KanbanController.components,
        PosAppointmentSearchFilter,
    };
    async createRecord() {
        const onRecordSaved = async () => {
            const root = this.env.model.root;
            const { limit, offset } = root;
            await root.load({ offset, limit });
        };
        return await posmodel.createBooking(onRecordSaved.bind(this));
    }

    async openRecord(record, { newWindow } = {}) {
        const onRecordSaved = async () => {
            const root = this.env.model.root;
            const { limit, offset } = root;
            await root.load({ offset, limit });
        };
        return await posmodel.editBooking(record.resId, onRecordSaved.bind(this));
    }
}
