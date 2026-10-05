import { Component, useProps, t } from "@odoo/owl";
import { getTimeUtil } from "@point_of_sale/utils";
import { CalendarEvent } from "@pos_appointment/app/models/calendar_event";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class ConfirmAppointmentPopup extends Component {
    static template = "pos_restaurant_appointment.ConfirmAppointmentPopup";
    static components = { Dialog };
    props = useProps({
        appointment: t.instanceOf(CalendarEvent),
        getPayload: t.function().optional(),
        close: t.function().optional(),
    });

    get appointment() {
        return this.props.appointment;
    }
    get title() {
        return _t("Open Table for %s?", this.appointment.attendeeName);
    }
    get message() {
        return _t(
            "Please confirm it's for the reservation of %s (%sp %s)",
            this.appointment.attendeeName,
            this.appointment.waiting_list_capacity,
            getTimeUtil(this.appointment.start)
        );
    }
    onConfirm() {
        this.props.getPayload("confirm");
        this.props.close();
    }
    onContinue() {
        this.props.getPayload("another_guest");
        this.props.close();
    }
}
