import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { redirect } from "@web/core/utils/urls";

export class OboxActionButton extends Component {
    static template = "obox.OboxActionButton";

    props = useProps({
        ...standardWidgetProps,
        function: t.string(),
        class: t.string().optional(),
        delete: t.boolean().optional(false),
    });

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    get ip() {
        return this.props.record.data.local_ip;
    }

    get label() {
        switch (this.props.function) {
            case "action_disconnect_obox":
                return _t("Disconnect");
            case "action_restart_obox":
                return _t("Restart");
            case "action_check_websocket":
                return _t("Test Connection");
            case "action_discover_devices":
                return _t("Discover Devices");
            default:
                return "";
        }
    }

    get confirmationSentence() {
        switch (this.props.function) {
            case "action_restart_obox":
                return _t("Are you sure that you want to restart this Obox?");
            case "action_check_websocket":
                return _t("Are you sure that you want to test the connection with this Obox?");
            case "action_discover_devices":
                return _t(
                    "This action will scan for any new devices connected to the Obox. It can take up to a minute to complete."
                );
            default:
                return "";
        }
    }

    async onClick() {
        this.dialog.add(ConfirmationDialog, {
            body: this.confirmationSentence,
            confirmLabel: this.label,
            confirm: async () => {
                const result = await this.orm.call("obox.obox", this.props.function, [
                    this.props.record.resId,
                ]);

                if (!result) {
                    this.notification.add(_t("Failed to perform the action on Obox"), {
                        type: "danger",
                    });
                } else if (this.props.delete) {
                    await this.props.record.update({
                        active: false,
                    });
                    redirect("/odoo/device");
                } else {
                    await this.props.record.load();
                }
            },
            cancel: () => {},
        });
    }
}

export const oboxActionButton = {
    component: OboxActionButton,
    extractProps: ({ attrs }) => ({
        function: attrs.function,
        class: attrs.class,
        delete: attrs.delete === "True",
    }),
};

registry.category("view_widgets").add("obox_action_button", oboxActionButton);
