import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, proxy, useProps, t } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { PRINTER_MESSAGES, FDM_MESSAGES } from "@iot/network_utils/iot_http_service";

export class TestIotDevice extends Component {
    static template = `iot.HeaderButton`;
    props = useProps({
        ...standardWidgetProps,
        btn_name: t.string(),
        btn_class: t.string(),
    });

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.iotHttp = useService("iot_http");
        this.orm = useService("orm");
        this.buttonState = proxy({ disabled: false });
    }

    async onClick() {
        const { iot_id, identifier, type } = this.props.record.data;
        this.buttonState.disabled = true;

        return this.iotHttp.action(
            iot_id,
            identifier,
            { action: "status" },
            (event) => this.onDeviceEvent(event, type),
            (event) => this.onDeviceEvent(event, type)
        );
    }

    onDeviceEvent(event, type) {
        const errorMessages = type === "printer" ? PRINTER_MESSAGES : FDM_MESSAGES;
        // Parse blackbox response
        if (type === "fiscal_data_module") {
            const fullErrorCode = event.message ?? event.result?.error?.errorCode;
            const errorCode = fullErrorCode?.substring(0, 3);
            if (FDM_MESSAGES[errorCode] && !["000", "102"].includes(errorCode)) {
                event.message = errorCode;
                event.status = "error";
            }
        }
        const errorMessage = errorMessages[event.message] ?? event.message;
        let defaultMessage;
        switch (type) {
            case "printer":
                defaultMessage = _t("Test page printed");
                break;
            case "fiscal_data_module":
                defaultMessage = _t("Fiscal Data Module is connected and operational");
                break;
            default:
                defaultMessage = _t("Device is connected and operational");
                break;
        }
        switch (event.status) {
            case "error":
            case "timeout":
                this.notification.add(errorMessage, { type: "danger" });
                break;
            case "warning":
                this.notification.add(errorMessage, { type: "warning" });
                break;
            case "disconnected":
                this.notification.add(_t("Device is disconnected"), { type: "danger" });
                break;
            default:
                this.notification.add(defaultMessage, { type: "info" });
                break;
        }
        this.buttonState.disabled = false;
    }
}

export const testIotDevice = {
    component: TestIotDevice,
    extractProps: ({ attrs }) => ({
        btn_name: attrs.btn_name,
        btn_class: attrs.btn_class,
    }),
};
registry.category("view_widgets").add("test_iot_device", testIotDevice);
