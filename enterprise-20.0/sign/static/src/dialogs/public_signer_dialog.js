import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { Component, signal, t, usePlugin, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { isEmail } from "@web/core/utils/strings";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class PublicSignerDialog extends Component {
    static template = "sign.PublicSignerDialog";
    static components = {
        Dialog,
    };

    props = useProps({
        name: t.string(),
        mail: t.string(),
        postValidation: t.function(),
        close: t.function(),
    });

    nameRef = signal.ref();
    mailRef = signal.ref();

    setup() {
        this.signInfo = usePlugin(SignInfoPlugin);
        this.dialogService = useService("dialog");
        this.uiService = useService("ui");
    }

    get dialogProps() {
        return {
            title: _t("Final Validation"),
            size: "md",
            technical: this.uiService.isSmall,
            fullscreen: this.uiService.isSmall,
        };
    }

    async submit() {
        const name = this.nameRef().value;
        const mail = this.mailRef().value;
        if (!this.validateForm(name, mail)) {
            return false;
        }

        try {
            const response = await rpc(
                `/sign/send_public/${this.signInfo.get("documentId")}/${this.signInfo.get(
                    "signRequestToken"
                )}`,
                { name, mail }
            );

            await this.props.postValidation(
                response["requestID"],
                response["requestToken"],
                response["accessToken"]
            );
            this.props.close();
        } catch (error) {
            this.dialogService.add(AlertDialog, {
                title: _t("Error"),
                body: error?.data?.message || error.message,
            });
        }
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
