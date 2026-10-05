import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { SignRequestDocumentsDropdown } from "@sign/backend_components/sign_request/sign_request_documents_dropdown";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import multiFileUpload from "@sign/backend_components/multi_file_upload";
import { SignerStatusBadge } from "@sign/components/sign_request/signer_status_badge";
import { SignHeaderTags } from "@sign/backend_components/sign_template/sign_header_tags";

export class SignRequestControlPanel extends Component {
    static template = "sign.SignRequestControlPanel";
    static components = {
        ControlPanel,
        Dropdown,
        DropdownItem,
        SignRequestDocumentsDropdown,
        SignerStatusBadge,
        SignHeaderTags,
    };

    props = useProps({
        goBackToKanban: t.function(),
        signer_status_props_json: t.object().optional(),
    });

    setup() {
        this.controlPanelDisplay = {};
        this.action = useService("action");
        this.orm = useService("orm");
        this.signInfo = usePlugin(SignInfoPlugin);
        this.nextTemplate = multiFileUpload.getNext();
        this.addDialog = useOwnedDialogs();
    }

    get showResendButtons() {
        const documentSent = this.signInfo.get("signRequestState") === "sent";
        const isAuthor = this.signInfo.get("createUid") === user.userId;
        return isAuthor && documentSent;
    }

    get allowCancel() {
        const needToSign = this.signInfo.get("needToSign");
        const state = this.signInfo.get("signRequestState");
        const isAuthor = this.signInfo.get("createUid") === user.userId;
        return (isAuthor || needToSign) && !["signed", "canceled"].includes(state);
    }

    // In a normal OWL context, this property ensures the dropdown renders fine.
    // However, in a signing session, the template is used statically and JS is not available
    // so this will be undefined and the component won't render which is needed.
    get shouldShowDownloadDropdown() {
        return true;
    }

    // Always true in normal mode, and explicitly false in signing mode
    // to hide the button.
    get shouldShowDetailsButton() {
        return true;
    }

    get hasMultipleDocuments() {
        const count = this.signInfo.get("document_count") || 1;
        return count > 1;
    }

    get signerStatusBadgeProps() {
        return {
            ...this.props.signer_status_props_json,
            showResendButtons: this.showResendButtons,
            onResendClick: this.ResendDocument.bind(this),
            sequencedSignatureMail: this.signInfo.get("sequencedSignatureMail"),
        };
    }

    get TagsProps() {
        const requestId = this.signInfo.get("documentId");
        if (!requestId) {
            return null;
        }
        return {
            resModel: "sign.request",
            resId: requestId,
            fieldsInfo: {
                template_tags: { type: "many2many", relation: "sign.request.tag", string: "Tags" },
            },
        };
    }

    async signDocument() {
        const action = await this.orm.call("sign.request", "go_to_signable_document", [
            [this.signInfo.get("documentId")],
        ]);
        action.name = _t("Sign");
        this.action.doAction(action);
    }

    async cancelDocument() {
        this.addDialog(ConfirmationDialog, {
            body: _t("Are you sure you want to cancel this sign request?"),
            confirm: async () => {
                await this.orm.call("sign.request", "cancel", [this.signInfo.get("documentId")]);
                const result = await this.orm.call("sign.request", "get_close_values", [
                    [this.signInfo.get("documentId")],
                ]);
                const context = result.custom_action ? {} : { clearBreadcrumbs: true };
                this.env.services.action.doAction(result.action, context);
            },
            cancel: () => {},
        });
    }

    async ResendDocument(signRequestItemId) {
        await this.orm.call("sign.request.item", "send_signature_accesses", [signRequestItemId], {
            context: user.context,
        });
    }

    async openFormView() {
        const action = await this.orm.call("sign.request", "get_record_default_action", [
            [this.signInfo.get("documentId")],
        ]);
        await this.action.doAction(action);
    }

    async openSendWizard() {
        const action = await this.orm.call("sign.request", "action_send", [
            this.signInfo.get("documentId"),
        ]);
        await this.action.doAction(action);
    }

    async saveAsTemplate() {
        const action = await this.orm.call("sign.request", "action_save_as_template", [
            this.signInfo.get("documentId"),
        ]);
        await this.action.doAction(action);
    }

    async goToNextDocument() {
        const templateName = this.nextTemplate.name;
        const templateId = parseInt(this.nextTemplate.template);
        multiFileUpload.removeFile(this.nextTemplate.template);
        await this.action.doAction(
            {
                type: "ir.actions.client",
                tag: "sign.Template",
                name: _t("Template %s", templateName),
                params: {
                    sign_edit_call: "sign_send_request",
                    id: templateId,
                    sign_directly_without_mail: false,
                },
            },
            { clear_breadcrumbs: true }
        );
    }
}
