import { GanttController } from "@web_gantt/gantt_controller";
import {
    CalendarEventQuickCreateFormViewDialog,
    QUICK_CREATE_CALENDAR_EVENT_FIELDS,
} from "@calendar/views/calendar_form/calendar_event_quick_create";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

import { onWillStart } from "@odoo/owl";

// add fields to be carried over when clicking "options" button on quick-edit form dialog
Object.assign(QUICK_CREATE_CALENDAR_EVENT_FIELDS, {
    appointment_status: { type: "string" },
    resource_ids: { type: "many2many" },
    total_capacity_reserved: { type: "number" },
});

const { DateTime } = luxon;

export class AppointmentBookingGanttController extends GanttController {
    /**
     * @override
     */
   setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");

        onWillStart(async () => {
            this.isAppointmentManager = await user.hasGroup("appointment.group_appointment_manager");
        });
    }

    /**
     * @override
     */
    create(context) {
        super.create({...context, 'booking_gantt_create_record': true});
    }

    /**
     * @override
     * When creating a new booking using the "New" button, round the start datetime to the next
     * half-hour (e.g. 10:12 => 10:30, 11:34 => 12:00).
     * The stop datetime is set by default to start + 1 hour to override the calendar.event's default_stop, which is currently setting the stop based on now instead of start.
     * The stop datetime will be updated in the default_get method on python side to match the appointment type duration.
    */
    _onNewClicked() {
        const focusDate = this.getCurrentFocusDate();
        const now = DateTime.now();
        const start =
            now.minute > 30
                ? focusDate.set({ hour: now.hour + 1, minute: 0, second: 0 })
                : focusDate.set({ hour: now.hour, minute: 30, second: 0 });
        const stop = start.plus({ hour: 1 });
        const context = this.model.getDialogContext({ start, stop, withDefault: true });
        this.create(context);
    }

    async onAddClosingDay() {
        const defaultAppointmentTypeId = this.props.context.default_appointment_type_id;
        const scheduleBasedOn = this.props.context.appointment_schedule_based_on;
        this.actionService.doAction({
            name: _t("New Closing Day"),
            type: "ir.actions.act_window",
            res_model: "appointment.leave",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                ...(defaultAppointmentTypeId && { default_appointment_type_ids: [defaultAppointmentTypeId] }),
                ...(scheduleBasedOn && { appointment_schedule_based_on: scheduleBasedOn }),
            },
        }, {
            onClose: () => this.model.fetchData(),
        });
    }

    /**
     * @override
     * Add props required by the quick create form view
     * and open the calendar-specific form dialog
     * unless otherwise specified.
     */
    openDialog(props, options = {}, dialogComponent = null) {
        if (dialogComponent !== null) {
            return super.openDialog(...arguments);
        }
        return super.openDialog(props, options, CalendarEventQuickCreateFormViewDialog);
    }

    _getDialogProps(props) {
        props.title = props.title || (props.resId ? _t("Open") : _t("New Booking"));
        return super._getDialogProps(props);
    }
}
