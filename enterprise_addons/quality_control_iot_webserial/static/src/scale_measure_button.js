import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUnmount, signal, usePlugin, useProps } from "@odoo/owl";
import { WebSerialScale } from "@iot_webserial/web_serial_scale";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { openWebSerialDevice } from "@iot_webserial/web_serial_device";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { _t } from "@web/core/l10n/translation";

export class ScaleMeasureButton extends Component {
    static template = "quality_control_iot_webserial.ScaleMeasureButton";

    props = useProps(standardWidgetProps);
    notification = usePlugin(NotificationPlugin);
    loading = signal(false);

    setup() {
        onWillStart(async () => {
            this.scale = await openWebSerialDevice(WebSerialScale);
        });
        onWillUnmount(() => {
            if (this.scale) {
                this.scale.close();
            }
        });
    }

    async onClick() {
        this.loading.set(true);

        try {
            const weight = await this.scale.readWeight();
            if (weight !== null) {
                this.props.record.update({ measure: weight });
            } else {
                if (this.scale.status.OVER_CAPACITY) {
                    this.notification.add(_t("Scale is over capacity"), { type: "warning" });
                }
                if (this.scale.status.UNDER_ZERO) {
                    this.notification.add(_t("Scale is under zero"), { type: "warning" });
                }
            }
        } catch (error) {
            this.notification.add(error.message, { type: "danger" });
        }

        this.loading.set(false);
    }
}

registry.category("view_widgets").add("quality_control_iot_webserial.scale_measure", {
    component: ScaleMeasureButton,
    extractProps: ({ attrs }) => ({ btn_name: attrs.btn_name }),
});
