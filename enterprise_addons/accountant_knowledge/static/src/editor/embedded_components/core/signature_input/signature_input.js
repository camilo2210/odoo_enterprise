import { Component } from "@odoo/owl";

export class ReadonlySignatureInputComponent extends Component {
    static template = "accountant_knowledge.ReadonlyEmbeddedSignatureInput";
}

export const readonlySignatureInputEmbedding = {
    name: "signatureInput",
    Component: ReadonlySignatureInputComponent,
};
