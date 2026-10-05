import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { POSAppointmentQuickCreate } from "@pos_appointment/app/form_extend/form_view_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async manageBookings(viewMode = "") {
        this.orderToTransferUuid = null;
        this.navigate("ActionScreen", { actionName: "manage-booking", viewMode: viewMode });
    },
    async editBooking(appointmentId, onRecordSaved = () => {}) {
        if (this.config.module_pos_hr && !this.accessRight.canEditBooking) {
            return;
        }

        return this.dialog.add(POSAppointmentQuickCreate, {
            title: _t("Edit"),
            resModel: "calendar.event",
            resId: appointmentId,
            size: "md",
            context: {
                from_pos_booking: true,
                form_view_ref: "pos_appointment.calendar_event_view_form_gantt_booking",
            },
            onRecordSaved: onRecordSaved,
        });
    },
    async createBooking(onRecordSaved = () => {}, opt = {}) {
        if (this.config.module_pos_hr && !this.accessRight.canCreateBooking) {
            return;
        }

        let context = {
            default_appointment_type_id: this.config.raw.appointment_type_id,
            default_duration: 2,
            default_name: false,
            default_partner_ids: [],
            default_total_capacity_reserved: 0,
            default_waiting_list_capacity: 2,
            form_view_ref: "pos_appointment.calendar_event_view_form_gantt_booking",
        };
        if (opt.context && Object.keys(opt.context).includes("search_default_resource_ids")) {
            context = { ...context, ...opt.context };
        }
        return this.dialog.add(POSAppointmentQuickCreate, {
            title: _t("Create"),
            resModel: "calendar.event",
            size: "md",
            context: context,
            onRecordSaved: onRecordSaved,
        });
    },
});
