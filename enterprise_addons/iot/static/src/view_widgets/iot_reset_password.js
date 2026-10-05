import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, useProps, t } from "@odoo/owl";

export class IoTResetPassword extends Component {
    static template = `iot.HeaderButton`;
    props = useProps({
        ...standardWidgetProps,
        btn_name: t.string(),
        btn_class: t.string(),
    });

    setup() {
        super.setup();
        this.iotHttp = useService("iot_http");
        this.notification = useService("notification");
    }

    async onClick() {
        const { identifier, name } = this.props.record.data;
        this.iotHttp.websocket.onMessage(
            identifier,
            identifier,
            (result) => {
                this.notification.add(_t("%s new password: %s", name, result.result?.password), {
                    type: "info",
                });
            },
            this.doWarnFail.bind(this)
        );
        this.iotHttp.websocket.sendMessage(
            identifier,
            { action: "reset_password" },
            null,
            "reset_password"
        );
    }

    doWarnFail() {
        this.notification.add(_t("Failed to reset %s password.", this.name), { type: "danger" });
    }
}

export const ioTResetPassword = {
    component: IoTResetPassword,
    extractProps: ({ attrs }) => ({
        btn_name: attrs.btn_name,
        btn_class: attrs.btn_class,
    }),
};
registry.category("view_widgets").add("iot_reset_password", ioTResetPassword);
