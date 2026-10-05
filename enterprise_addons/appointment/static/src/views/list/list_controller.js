import { _t } from "@web/core/l10n/translation";
import { useArchiveOrUnlinkCalendarEvents } from "@calendar/views/hooks";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { AppointmentTemplatePickerDialog } from "@appointment/components/appointment_template_picker_dialog/appointment_template_picker_dialog";

import { onWillStart } from "@odoo/owl";

export class AppointmentBookingListController extends ListController {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.archiveOrUnlinkCalendarEvents = useArchiveOrUnlinkCalendarEvents();

        onWillStart(async () => {
            this.isAppointmentManager = await user.hasGroup("appointment.group_appointment_manager");
        });
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
        });
    }

    async onDeleteSelectedRecords() {
        this.archiveOrUnlinkCalendarEvents({
            requestedAction: "unlink",
            records: this.model.root.selection,
            defaultAction: () => this.deleteRecordsWithConfirmation(this.deleteConfirmationDialogProps),
        });
    }
}

export class AppointmentTypeListController extends ListController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }
    /**
     * @override
     */
    async createRecord() {
        this.dialog.add(AppointmentTemplatePickerDialog, {});
    }
}
