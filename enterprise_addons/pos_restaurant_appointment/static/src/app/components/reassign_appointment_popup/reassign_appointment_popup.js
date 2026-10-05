import { Component, useProps, t } from "@odoo/owl";
import { getTimeUtil } from "@point_of_sale/utils";
import { CalendarEvent } from "@pos_appointment/app/models/calendar_event";
import { RestaurantTable } from "@pos_restaurant/app/models/restaurant_table";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class ReassignAppointmentPopup extends Component {
    static template = "pos_restaurant_appointment.ReassignAppointmentPopup";
    static components = { Dialog };
    props = useProps({
        appointment: t.instanceOf(CalendarEvent),
        existingAppointment: t.instanceOf(CalendarEvent),
        table: t.instanceOf(RestaurantTable),
        getPayload: t.function().optional(),
        close: t.function().optional(),
    });

    get appointment() {
        return this.props.appointment;
    }
    get existingAppointment() {
        return this.props.existingAppointment;
    }
    get title() {
        return _t("Table %s already booked", this.props.table.table_number);
    }
    get message() {
        return _t(
            "Booked by %s, %s guests at %s.",
            this.existingAppointment.attendeeName,
            this.getTotalCapacityReserved(this.existingAppointment),
            getTimeUtil(this.existingAppointment.start)
        );
    }
    get canSwap() {
        const apptWaitingListCapacity = this.getWaitingListCapacity(this.appointment);
        const existingApptWaitingListCapacity = this.getWaitingListCapacity(
            this.existingAppointment
        );
        const apptTotalCapacityReserved = this.getTotalCapacityReserved(this.appointment);
        const existingApptTotalCapacityReserved = this.getTotalCapacityReserved(
            this.existingAppointment
        );
        const capacitiesMatch =
            apptWaitingListCapacity === existingApptWaitingListCapacity ||
            apptTotalCapacityReserved === existingApptTotalCapacityReserved ||
            apptWaitingListCapacity === existingApptTotalCapacityReserved ||
            apptTotalCapacityReserved === existingApptWaitingListCapacity;
        return (
            capacitiesMatch &&
            this.appointment.appointment_resource_ids.length &&
            this.existingAppointment.appointment_resource_ids.length
        );
    }
    getWaitingListCapacity(appointment) {
        return appointment.waiting_list_capacity;
    }
    getTotalCapacityReserved(appointment) {
        return appointment.total_capacity_reserved;
    }
    onConfirm() {
        this.props.getPayload(this.canSwap ? "swap" : "reassign");
        this.props.close();
    }
    onContinue() {
        this.props.getPayload("double_book");
        this.props.close();
    }
}
