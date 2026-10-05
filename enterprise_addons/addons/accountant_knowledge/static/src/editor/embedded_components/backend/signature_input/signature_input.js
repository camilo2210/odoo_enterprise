import { Component, t, useProps } from "@odoo/owl";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { SignatureDialog } from "@web/core/signature/signature_dialog";

export class SignatureInputComponent extends Component {
    static template = "accountant_knowledge.EmbeddedSignatureInput";

    props = useProps({
        host: t.object(),
        replaceSignatureInputWithImage: t.function(),
    });

    setup() {
        this.dialog = useService("dialog");
    }

    openSignatureDialog() {
        this.dialog.add(SignatureDialog, {
            defaultName: user.name,
            nameAndSignatureProps: {
                displaySignatureRatio: 3,
            },
            uploadSignature: signature => {
                this.props.replaceSignatureInputWithImage(
                    this.props.host,
                    signature.signatureImage
                );
            },
        });
    }
}

export const signatureInputEmbedding = {
    name: "signatureInput",
    Component: SignatureInputComponent,
    getProps: (host) => ({ host, ...getEmbeddedProps(host) }),
};
