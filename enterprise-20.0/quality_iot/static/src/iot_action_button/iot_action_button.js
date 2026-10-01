import { Component, useProps, t } from "@odoo/owl";
import { useService } from '@web/core/utils/hooks';
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

/**
 * Base class for IoT action buttons in quality checks.
 * Meant to add a button in the modal footer of quality checks
 * when triggered from manufacturing app (not shop floor).
 */
export class IotActionButton extends Component {
    static template = "quality_iot.iotActionButton";
    props = useProps({
        ...standardWidgetProps,
        btn_name: t.string(),
    });

    setup() {
        super.setup();
        this.dialog = useService('dialog');
        this.notification = useService('notification');
        this.iotHttpService = useService('iot_http');
    }

    get iotDevice() {
        const { iot_box_id , identifier } = this.props.record.data;
        if (!iot_box_id || !identifier) {
            return false;
        }
        return {
            iotBoxId: iot_box_id.id,
            deviceIdentifier: identifier,
        }
    }

    async onClick() {
        throw new Error("onClick method must be implemented by subclasses");
    }
}
