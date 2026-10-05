import { SignRequest } from "@sign/backend_components/sign_request/sign_request_action";
import { SignableRequestControlPanel } from "@sign/backend_components/sign_request/signable_sign_request_control_panel";
import { SignablePDFIframe } from "@sign/components/sign_request/signable_PDF_iframe";
import { registry } from "@web/core/registry";

export class SignableSignRequest extends SignRequest {
    static components = {
        ...SignRequest.components,
        SignRequestControlPanel: SignableRequestControlPanel,
    };
    setup() {
        super.setup();
        const context = this.props.action.context;
        this.signInfo.set({
            tokenList: context.token_list,
            nameList: context.name_list,
            requestItemIdList: context.request_item_id_list,
            reference: context.reference,
            someSignersEmailed: context.some_signers_emailed || false,
        });
    }

    get documentProps() {
        return {
            ...super.documentProps,
            PDFIframeClass: SignablePDFIframe,
        };
    }
}

registry.category("actions").add("sign.SignableDocument", SignableSignRequest);
