import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { _t } from "@web/core/l10n/translation";
import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export function openAllSetDirectSignDialog(env, signInfo) {
    env.services.dialog.add(
        AlertDialog,
        {
            title: signInfo.get("reference") || _t("Signature Request"),
            body: _t("All set! We'll let you know when everyone has signed."),
        },
        {
            onClose: () => {
                env.services.action.doAction("sign.sign_request_action", {
                    clearBreadcrumbs: true,
                });
            },
        }
    );
}

export class NextDirectSignDialog extends Component {
    static template = "sign.NextDirectSignDialog";
    static components = {
        Dialog,
    };

    props = useProps({
        close: t.function(),
    });

    setup() {
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.signInfo = usePlugin(SignInfoPlugin);
        this.uiService = useService("ui");
    }

    get title() {
        return this.lastEmailedName ? _t("Signing link sent") : _t("Signature Saved");
    }

    goToNextSigner() {
        const newCurrentToken = this.signInfo.get("tokenList").shift();
        this.signInfo.get("nameList").shift();
        this.signInfo.get("requestItemIdList").shift();
        this.action.doAction(
            {
                type: "ir.actions.client",
                tag: "sign.SignableDocument",
                name: _t("Sign"),
            },
            {
                additionalContext: {
                    id: this.signInfo.get("documentId"),
                    create_uid: this.signInfo.get("createUid"),
                    state: this.signInfo.get("signRequestState"),
                    token: newCurrentToken,
                    token_list: this.signInfo.get("tokenList"),
                    name_list: this.signInfo.get("nameList"),
                    request_item_id_list: this.signInfo.get("requestItemIdList"),
                    reference: this.signInfo.get("reference"),
                    some_signers_emailed: this.signInfo.get("someSignersEmailed"),
                },
                stackPosition: "replaceCurrentAction",
            }
        );
        this.props.close();
    }

    async continueByEmail() {
        const nextItemId = this.signInfo.get("requestItemIdList")[0];
        const emailedName = this.signInfo.get("nameList")[0];
        await this.orm.call("sign.request.item", "send_signature_accesses", [[nextItemId]]);
        this.signInfo.get("tokenList").shift();
        this.signInfo.get("nameList").shift();
        this.signInfo.get("requestItemIdList").shift();
        this.signInfo.set({ someSignersEmailed: true, lastEmailedName: emailedName });
        this.props.close();
        if (this.signInfo.get("nameList").length > 0) {
            this.dialog.add(NextDirectSignDialog);
        } else {
            openAllSetDirectSignDialog(this.env, this.signInfo);
        }
    }

    get nextSigner() {
        return this.signInfo.get("nameList")[0];
    }

    get lastEmailedName() {
        return this.signInfo.get("lastEmailedName");
    }

    get lastSignedName() {
        return this.signInfo.get("lastSignedName");
    }

    get dialogProps() {
        return {
            size: "md",
            technical: this.uiService.isSmall,
        };
    }
}
