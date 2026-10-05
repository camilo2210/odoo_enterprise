import { AppointmentCalendarEventPopover } from "@appointment/views/popover/popover";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { usePopover } from "@web/core/popover/popover_hook";

export class AppointmentCalendarEventKanbanRecord extends KanbanRecord {
    setup() {
        super.setup(...arguments);
        this.popover = usePopover(AppointmentCalendarEventPopover, { position: "bottom" });
    }

    onGlobalClick(ev) {
        this.popover.open(ev.currentTarget, {
            data: {
                ...this.props.record.data,
                attendee_ids: Array.from(this.props.record.data.attendee_ids.resIds),
                partner_ids: Array.from(this.props.record.data.partner_ids.resIds),
            },
            reload: () => this.props.record.model.load(),
            resId: this.props.record._config.resId,
            resModel: this.props.record.resModel,
        });
    }
}
