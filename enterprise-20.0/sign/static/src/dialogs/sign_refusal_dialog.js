import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { Component, signal, t, usePlugin, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ThankYouDialog } from "./thank_you_dialog";
import { isEmail } from "@web/core/utils/strings";

export class SignRefusalDialog extends Component {
    static template = "sign.SignRefusalDialog";
    static components = {
        Dialog,
    };

    props = useProps({
        close: t.function(),
    });

    refuseNameRef = signal.ref();
    refuseEmailRef = signal.ref();
    refuseReasonRef = signal.ref();
    refuseButtonRef = signal.ref();

    setup() {
        this.dialog = useService("dialog");
        this.signInfo = usePlugin(SignInfoPlugin);
        this.isShared = this.signInfo.get("signRequestState") === "shared";
    }

    get dialogProps() {
        return {
            size: "md",
            title: _t("Decline to sign"),
            contentClass: "o_seprate_dialog_content",
        };
    }

    checkForChanges() {
        const reason = this.refuseReasonRef().value.trim();
        const isReasonEmpty = reason.length === 0;
        const isSharedUnidentified =
            this.isShared &&
            (!this.refuseNameRef().value.trim() || !this.refuseEmailRef().value.trim());
        this.refuseButtonRef().disabled = isReasonEmpty || isSharedUnidentified;
    }

    async refuse() {
        const route = `/sign/refuse/${this.signInfo.get("documentId")}/${this.signInfo.get(
            "signRequestItemToken"
        )}`;
        let params = {
            refusal_reason: this.refuseReasonRef().value,
        };

        if (this.isShared) {
            const name = this.refuseNameRef().value;
            const email = this.refuseEmailRef().value;

            if (!email || !isEmail(email)) {
                this.refuseEmailRef().classList.add("is-invalid");
                return;
            }

            params = {
                ...params,
                refusal_name: name,
                refusal_email: email,
            };
        }

        const response = await rpc(route, params);
        if (!response) {
            this.dialog.add(
                AlertDialog,
                {
                    body: _t("Sorry, you cannot refuse this document"),
                },
                {
                    onClose: () => window.location.reload(),
                }
            );
        }
        await this.props.close();
        this.dialog.add(SignRefusalDialogTitle);
    }
}

export class SignRefusalDialogTitle extends ThankYouDialog {
    static template = "sign.SignRefusalDialogTitle";
    setup() {
        super.setup();
        this.message =
            this.props.message ||
            _t("The document has been refused and the sender has been notified.");
        this.dialog = useService("dialog");
        this.props.isRefused = true;
    }
}
