import { SignInfoPlugin } from "@sign/services/sign_info_plugin";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, markup, signal, usePlugin, useProps } from "@odoo/owl";
import { SignRequestControlPanel } from "@sign/backend_components/sign_request/sign_request_control_panel";
import { Document } from "@sign/components/sign_request/document_signable";
import { PDFIframe } from "@sign/components/sign_request/PDF_iframe";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

export class SignRequest extends Component {
    static template = "sign.SignRequest";
    static components = {
        SignRequestControlPanel,
        Document,
    };

    props = useProps(standardActionServiceProps);

    signDocumentRef = signal.ref();

    get markupHtml() {
        return markup(this.html);
    }

    get documentProps() {
        return {
            parent: this.signDocumentRef,
            PDFIframeClass: PDFIframe,
        };
    }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.signInfo = usePlugin(SignInfoPlugin);
        const action = this.props.action;
        const context = action?.context;

        this.signInfo.reset({
            documentId: context.id || (action.params && action.params.id),
            signRequestToken: context.token || (action.params && action.params.token), // token could be sign.request.item's token if signabledocument
            createUid: context.create_uid || (action.params && action.params.create_uid),
            signRequestState: context.state || (action.params && action.params.state),
            requestItemStates: context.request_item_states,
            needToSign: context.need_to_sign || (action.params && action.params.need_to_sign),
            todayFormattedDate: context.today_formatted_date,
            dateFormat: context.date_format,
            sequencedSignatureMail:
                context.sequenced_signature_mail ||
                (action.params && action.params.sequenced_signature_mail),
            name: action.name || (action.params && action.params.name),
            canSignNow: context.can_sign_now || (action.params && action.params.can_sign_now),
            document_count:
                context.document_count || (action.params && action.params.document_count),
            template_id: context.template_id || (action.params && action.params.template_id),
        });

        if (this.signInfo) {
            this.props.updateActionState({
                id: this.signInfo.get("documentId"),
                token: this.signInfo.get("signRequestToken"),
                create_uid: this.signInfo.get("createUid"),
                state: this.signInfo.get("signRequestState"),
                sequenced_signature_mail: this.signInfo.get("sequencedSignatureMail"),
                need_to_sign: this.signInfo.get("needToSign"),
                name: this.signInfo.get("name") || "",
                can_sign_now: this.signInfo.get("canSignNow"),
                document_count: this.signInfo.get("document_count"),
                template_id: this.signInfo.get("template_id"),
            });
            this.env.config.setDisplayName(this.signInfo.get("name") || "");
        }

        onWillStart(() => this.fetchDocument());
    }

    async fetchDocument() {
        if (!this.signInfo.get("documentId")) {
            return this.goBackToKanban();
        }
        const result = await rpc(
            `/sign/get_document/${this.signInfo.get("documentId")}/${this.signInfo.get(
                "signRequestToken"
            )}`
        );
        if (!result || result.error) {
            return this.goBackToKanban();
        }
        const { html, context } = result;
        this.html = html.trim();
        if (Object.keys(context).length > 0) {
            this.signInfo.set({
                signRequestItemToken: this.signInfo.get("signRequestToken"),
                signRequestToken: context.sign_request_token,
                showDelegateButton: context.show_delegate_button,
                signer_status_props_json: JSON.parse(context.signer_status_props_json),
            });
        }
    }

    goBackToKanban() {
        return this.action.doAction("sign.sign_request_action", { clearBreadcrumbs: true });
    }

    get controlPanelProps() {
        return {
            goBackToKanban: this.goBackToKanban.bind(this),
            signer_status_props_json: this.signInfo.get("signer_status_props_json"),
        };
    }
}

registry.category("actions").add("sign.Document", SignRequest);
