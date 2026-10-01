import { t, useProps } from "@odoo/owl";
import { AppointmentCalendarEventPopover } from "@appointment/views/popover/popover";
import { GanttPopover, ganttPopoverProps } from "@web_gantt/gantt_popover";

export class AppointmentGanttPopover extends GanttPopover {
    static template = "appointment.AppointmentGanttPopover";
    static components = { AppointmentCalendarEventPopover };
    props = useProps({ ...ganttPopoverProps, record: t.object() });

    get cardPopoverProps() {
        const props = super.cardPopoverProps;
        return {
            ...props,
            data: this.props.record,
            reload: async () => {
                await this.props.model.fetchData();
                this.props.close();
            },
        };
    }
}
