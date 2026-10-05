import { CalendarEventFormController } from "@calendar/views/calendar_form/calendar_event_form_controller";
import { patch } from "@web/core/utils/patch";

patch(CalendarEventFormController.prototype, {
    /**
     * @override
     */
    shouldUseArchiveWizard() {
        return this.model.root.data.appointment_type_id ? false : super.shouldUseArchiveWizard(...arguments);
    },
 });
