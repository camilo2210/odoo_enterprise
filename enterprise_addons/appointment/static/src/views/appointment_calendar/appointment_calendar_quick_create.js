import { patch } from "@web/core/utils/patch";
import { CalendarEventQuickCreateFormController } from "@calendar/views/calendar_form/calendar_event_quick_create";

patch(CalendarEventQuickCreateFormController.prototype, {
    getFullEventContext() {
        const context = super.getFullEventContext(...arguments);
        if (this.model.root.data.appointment_type_id) {
            context.default_is_draft = false;
        }
        return context;
    },
});
