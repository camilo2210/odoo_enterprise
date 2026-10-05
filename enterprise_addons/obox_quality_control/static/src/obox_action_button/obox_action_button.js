import { Component, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

/**
 * Base class for Obox action buttons in quality checks.
 * Meant to add a button in the modal footer of quality checks
 * when triggered from manufacturing app (not shop floor).
 */
export class OboxActionButton extends Component {
    static template = "quality_iot.oboxActionButton";

    props = useProps({
        ...standardWidgetProps,
        btn_name: t.string(),
    });

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    }

    get address() {
        const { obox_ip } = this.props.record.data;
        if (!obox_ip) {
            return false;
        }
        return `http://${obox_ip}/usb/v1`;
    }

    get identifier() {
        return this.props.record.data.obox_device_identifier ?? false;
    }

    async onClick() {
        throw new Error("onClick method must be implemented by subclasses");
    }
}
