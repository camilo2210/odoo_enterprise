/* global posmodel */
import { AppointmentCalendarEventPopover } from "@appointment/views/popover/popover";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export class POSAppointmentCalendarEventPopover extends AppointmentCalendarEventPopover {
    static template = "pos_appointment.POSAppointmentCalendarEventPopover";

    setup() {
        super.setup();
        this.pos = usePos();
    }

    onClickDelete() {
        this.onClickAppointmentStatus("cancelled");
    }

    async onClickEdit() {
        const onRecordSaved = async () => {
            await this.props.reload();
        };
        return await posmodel.editBooking(this.props.resId, onRecordSaved.bind(this));
    }
}
