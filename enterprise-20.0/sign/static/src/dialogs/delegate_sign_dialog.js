import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { Component, onWillStart, signal, t, usePlugin, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { user } from "@web/core/user";
import { isEmail } from "@web/core/utils/strings";

export class DelegateSignDialog extends Component {
    static template = "sign.DelegateSignDialog";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
    });

    nameRef = signal.ref();
    mailRef = signal.ref();

    setup() {
        this.signInfo = usePlugin(SignInfoPlugin);
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.user = user.userId;

        onWillStart(async () => {
            if (!session.is_frontend) {
                const result = await this.orm.call("sign.request", "get_close_values", [
                    [this.signInfo.get("documentId")],
                ]);
                this.closeAction = result.action;
                const closeContext = result.custom_action
                    ? { stackPosition: "replacePreviousAction" }
                    : { clearBreadcrumbs: true };
                this.closeContext = closeContext;
            }
        });
    }

    get dialogProps() {
        return {
            title: _t("Delegate"),
            size: "md",
            contentClass: "o_seprate_dialog_content",
        };
    }

    async submit() {
        const name = this.nameRef().value;
        const mail = this.mailRef().value;

        if (!this.validateForm(name, mail)) {
            return false;
        }

        const response = await rpc("/sign/delegate_signing/", {
            sign_request_id: this.signInfo.get("documentId"),
            request_item_id: this.signInfo.get("signRequestItemId"),
            request_item_token: this.signInfo.get("signRequestItemToken"),
            delegate_name: name,
            delegate_email: mail,
        });

        if (!response) {
            this.dialog.add(
                AlertDialog,
                {
                    body: _t(
                        "Sorry, an error occurred while delegating the signing. Please try again later."
                    ),
                },
                {
                    onClose: () => window.location.reload(),
                }
            );
        }

        this.props.close();

        this.dialog.add(DelegateSignSuccessDialog, {
            onConfirm: () => {
                if (!this.user) {
                    window.open("https://odoo.com/app/sign", "_self");
                    return;
                }

                if (session.is_frontend) {
                    window.location.assign("/my/signatures");
                    return;
                }

                this.env.services.action.doAction(this.closeAction, this.closeContext);
            },
        });
    }

    validateForm(name, mail) {
        const isEmailInvalid = !mail || !isEmail(mail);
        if (!name || isEmailInvalid) {
            this.nameRef().classList.toggle("is-invalid", !name);
            this.mailRef().classList.toggle("is-invalid", isEmailInvalid);
            return false;
        }
        return true;
    }
}

export class DelegateSignSuccessDialog extends Component {
    static template = "sign.DelegateSignSuccessDialog";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
        onConfirm: t.function(),
    });

    get dialogProps() {
        return {
            size: "md",
        };
    }

    onClickClose() {
        this.props.close();
        this.props.onConfirm();
    }
}
