/* global posmodel */

import { AppointmentBookingGanttController } from "@appointment/views/gantt/gantt_controller";

export class POSAppointmentBookingGanttController extends AppointmentBookingGanttController {
    async create(context) {
        const onRecordSaved = async () => {
            this.model.fetchData();
        };
        return await posmodel.createBooking(onRecordSaved.bind(this), { context });
    }
    _getDialogProps(props) {
        const dialogProps = super._getDialogProps(props);
        dialogProps.context = {
            ...dialogProps.context,
            from_pos_booking: true,
        };
        return dialogProps;
    }
}
