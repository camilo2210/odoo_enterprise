import { registry } from "@web/core/registry";
import { checkFileSize } from "@web/core/utils/files";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";

import { proxy } from "@odoo/owl";

export class VoipDocumentDropzoneField extends BinaryField {
    static template = "voip.DocumentDropzoneField";

    setup() {
        super.setup();
        this.dragState = proxy({ isDragOver: false });
    }

    onDragOver(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.dragState.isDragOver = true;
    }

    onDragLeave(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.dragState.isDragOver = false;
    }

    async onDrop(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.dragState.isDragOver = false;
        const file = ev.dataTransfer?.files?.[0];
        if (!file) {
            return;
        }
        if (!checkFileSize(file.size, this.notification)) {
            return;
        }
        const data = await getDataURLFromFile(file);
        await this.update({ name: file.name, data: data.split(",")[1] });
    }
}

export const voipDocumentDropzoneField = {
    ...binaryField,
    component: VoipDocumentDropzoneField,
};

registry.category("fields").add("voip_document_dropzone", voipDocumentDropzoneField);
