import { makeDocumentRecordData } from "@documents/../tests/helpers/document_data";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { Store } from "@mail/../tests/mock_server/store";

import { patch } from "@web/core/utils/patch";

patch(mailModels.IrAttachment.prototype, {
    /**
     * @param {number} id the python method is `ensure_one`
     */
    create_document(id) {
        /** @type {import("mock_models").DocumentsDocument} */
        const DocumentsDocument = this.env["documents.document"];
        const [attachment] = this.browse(id);
        // python names the document after its attachment, and sends a chatter attachment to the
        // destination of get_documents_operation_add_destination()
        DocumentsDocument.create(
            makeDocumentRecordData(undefined, attachment.name, {
                attachment_id: attachment.id,
                type: attachment.type,
                user_folder_id: "MY",
            })
        );
        this._compute_linked_document_id();
        return new Store()
            .add(this.browse(attachment.id), "_store_attachment_fields", {
                fields_params: { chatter_fields: true },
            })
            .as_dict();
    },

    _compute_linked_document_id() {
        // Simplified mock version: consider that the record always matches the conditions for a
        // direct sync of the attachment in document via the document's `attachment_id`.
        /** @type {import("mock_models").DocumentsDocument} */
        const DocumentsDocument = this.env["documents.document"];
        for (const attachment of this) {
            const [document] = DocumentsDocument.search_read([
                ["attachment_id", "=", attachment.id],
            ]);
            attachment.linked_document_id = document?.id ?? false;
        }
    },

    _store_attachment_fields(res, fields_params = {}) {
        super._store_attachment_fields(...arguments);
        if (fields_params.chatter_fields) {
            res.one("linked_document_id", "_store_document_fields");
        }
    },
});
