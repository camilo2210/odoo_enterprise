import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { oboxActionButton, OboxActionButton } from "./obox_action_button";
import { useProps, t, Component, proxy, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class OboxRemoteDebug extends OboxActionButton {
    setup() {
        super.setup();
        this.bus = useService("bus_service");

        const onRemoteDebugNotification = ({ message, type }) => {
            this.notification.add(message, { type });
            this.props.record.load();
        };

        this.bus.subscribe("obox.remote_debug_notification", onRemoteDebugNotification);
        onWillUnmount(() =>
            this.bus.unsubscribe("obox.remote_debug_notification", onRemoteDebugNotification)
        );
    }

    get label() {
        return _t("Remote Debug");
    }

    async toggleRemoteDebug(token) {
        if (token) {
            await this.orm.call("obox.obox", "action_enable_remote_debug", [
                this.props.record.resId,
                token,
            ]);
        } else {
            await this.orm.call("obox.obox", "action_disable_remote_debug", [
                this.props.record.resId,
            ]);
        }
    }

    async onClick() {
        this.dialog.add(TokenDialog, {
            onSubmit: this.toggleRemoteDebug.bind(this),
            enabled: this.props.record.data.remote_debug_enabled,
        });
    }
}

export class TokenDialog extends Component {
    static template = "obox.RemoteDebugDialog";
    static components = { Dialog };
    props = useProps({
        onSubmit: t.function([t.string()]),
        close: t.function([]),
        enabled: t.boolean(),
    });

    setup() {
        this.state = proxy({ token: "" });
    }

    onSubmit() {
        this.props.onSubmit(this.state.token);
        this.props.close();
    }
}

export const oboxRemoteDebug = {
    ...oboxActionButton,
    component: OboxRemoteDebug,
};

registry.category("view_widgets").add("obox_remote_debug", oboxRemoteDebug);
