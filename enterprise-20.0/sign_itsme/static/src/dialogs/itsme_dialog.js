import { Component, proxy, t, useProps } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ItsmeDialog extends Component {
    static template = "sign_itsme.ItsmeDialog";
    static components = {
        Dialog,
    };

    props = useProps({
        route: t.string(),
        params: t.object(),
        onSuccess: t.function(),
        close: t.function(),
        isQualifiedSignature: t.boolean().optional(),
    });

    setup() {
        this.dialog = useService("dialog");
        this.state = proxy({ loading: false });
    }

    get dialogProps() {
        return {
            size: "lg",
            title: this.props.isQualifiedSignature
                ? _t("Sign with itsme")
                : _t("Confirm identity with Itsme"),
        };
    }

    async onItsmeClick() {
        this.state.loading = true;
        let success, authorization_url, message;
        try {
            // the button has a loading indicator, so hide the global loading indicator
            ({ success, authorization_url, message } = await rpc(
                this.props.route,
                this.props.params,
                { silent: true }
            ));
        } finally {
            this.state.loading = false;
        }
        if (success) {
            if (authorization_url) {
                window.location.replace(authorization_url);
            } else {
                this.props.onSuccess();
            }
        } else {
            this.dialog.add(
                AlertDialog,
                {
                    body: message,
                },
                {
                    onClose: () => window.location.reload(),
                }
            );
        }
    }
}
