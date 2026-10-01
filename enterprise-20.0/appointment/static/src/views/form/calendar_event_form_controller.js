import { patch } from "@web/core/utils/patch";
import { CalendarEventFormController } from "@calendar/views/calendar_form/calendar_event_form_controller";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(CalendarEventFormController.prototype, {
    /**
     * Confirm before saving a resource booking that implicitly reserves more capacity
     * than the assigned resources can hold.
     *
     * @override
     */
    async onWillSaveRecord(record, changes) {
        const shouldSave = await super.onWillSaveRecord(...arguments);
        if (shouldSave === false) {
            return false;
        }
        const data = record.data;
        if (
            (changes.total_capacity_reserved === undefined && changes.resource_ids === undefined) ||
            !data.appointment_type_manage_capacity ||
            !(data.total_capacity_unassigned > 0)
        ) {
            return;
        }
        // Allow the inverse to create empty lines
        record.config.context = {
            ...record.config.context,
            appointment_allow_overbooking: true,
        };
        return new Promise((resolve) => {
            this.env.services.dialog.add(
                ConfirmationDialog,
                {
                    title: _t("Missing Seats"),
                    body: _t(
                        "%s seats cannot be assigned. Would you like to update the details?",
                        data.total_capacity_unassigned
                    ),
                    confirmLabel: _t("Book regardless"),
                    confirm: () => resolve(true),
                    cancelLabel: _t("Go back"),
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            );
        });
    },
});
