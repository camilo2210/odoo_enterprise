import { Component, signal, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DocumentsTypeIcon extends Component {
    static template = "documents.DocumentsTypeIcon";
    props = useProps(standardFieldProps);

    fileInputRef = signal.ref();

    onClickDocumentsRequest() {
        this.fileInputRef().click();
    }

    async onReplaceDocument() {
        if (!this.fileInputRef().files.length) {
            return;
        }
        await this.env.model.env.documentsView.bus.trigger("documents-upload-files", {
            files: this.fileInputRef().files,
            accessToken: this.props.record.data.access_token,
        });
        this.fileInputRef().value = "";
    }
}

const documentsTypeIcon = {
    component: DocumentsTypeIcon,
};

registry.category("fields").add("documents_type_icon", documentsTypeIcon);
