/* global posmodel */

import { patch } from "@web/core/utils/patch";
import { POSAppointmentCalendarEventPopover } from "@pos_appointment/app/popover_extend/popover";

patch(POSAppointmentCalendarEventPopover.prototype, {
    async onclickAppointmentStatus(status) {
        super.onclickAppointmentStatus(...arguments);
        if (!posmodel || status !== "attended") {
            return;
        }
        const resources = this.props.record.data.resource_ids?.records || [];
        posmodel.showResourceAssignNotification(this.props.record, resources, {
            viewMode: "kanban",
        });
    },
});
