import { t, useProps } from "@odoo/owl";

import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { user } from "@web/core/user";
import { useEnv } from "@web/owl2/utils";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

import { AttendeeCalendarSidePanel } from "@calendar/views/attendee_calendar/side_panel/attendee_calendar_side_panel";

Object.assign(AttendeeCalendarSidePanel.components, {
    AutoComplete,
});


patch(AttendeeCalendarSidePanel.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.appointmentOptionsCollapsed = false;
        this.env = useEnv();
        this.uiService = useService("ui");
        this.appointmentProps = useProps({
            saveAndCopyAppointmentUrl: t.function(),
            setEditingAppointmentId: t.function(),
            setSelectedAppointmentTypeId: t.function(),
            openAppointmentForm: t.function(),
            copyAppointmentURL: t.function(),
        });
    },

    /**
     * Values of the default appointment, if one is set and it is in the list
     */
    get defaultAppointment() {
        const model = this.props.model;
        if (model.selectedAppointmentTypeId()) {
            return this.props.model.data.userAppointmentsData.get(
                model.selectedAppointmentTypeId()
            );
        }
        return undefined;
    },

    /**
     * Appointment types listed in the sidebar "Booking Pages" list.
     */
    get listedUserAppointments() {
        return Array.from(this.props.model.data.userAppointmentsData.values());
    },

    get editingAppointmentValues() {
        return this.props.model.slotsAppointmentData();
    },

    toggleAppointmentOptions() {
        // disabled while editing as toggle caret disappears
        if (!this.editingAppointmentValues) {
            this.state.appointmentOptionsCollapsed = !this.state.appointmentOptionsCollapsed;
        }
    },

    get userTimezone() {
        return user.tz;
    },

    get userTimezoneLocalized() {
        // Usually UTC+2 (or local variant) but can occasionally be something like "CET" etc..
        return luxon.DateTime.now().setZone(this.userTimezone).offsetNameShort;
    },
});
