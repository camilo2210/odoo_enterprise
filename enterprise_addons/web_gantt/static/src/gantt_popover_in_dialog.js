import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class GanttPopoverInDialog extends Component {
    static components = { Dialog };
    static template = "web_gantt.GanttPopoverInDialog";

    props = useProps({
        close: t.any(),
        component: t.any(),
        componentProps: t.any(),
        dialogTitle: t.any(),
    });
    get componentProps() {
        return { ...this.props.componentProps, close: this.props.close };
    }
}
