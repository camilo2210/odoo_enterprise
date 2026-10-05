import {
    SelectAddDocumentCreateDialog,
    selectAddDocumentCreateDialogProps,
} from "@documents/views/view_dialogs/select_add_document_create_dialog";
import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";
import { t } from "@odoo/owl";

Object.assign(selectAddDocumentCreateDialogProps, {
    addFromDocuments: t.function().optional(),
});

patch(SelectAddDocumentCreateDialog.prototype, {
    get viewProps() {
        const viewProps = super.viewProps;
        const thread = this.props.chatterParams?.thread || this.props.thread;
        if (thread?.channel?.isAiChat) {
            // indexable files and image types supported by most AI providers
            viewProps.domain = Domain.and([
                viewProps.domain,
                Domain.or([
                    [
                        [
                            "file_extension",
                            "in",
                            [
                                "docx",
                                "pptx",
                                "xlsx",
                                "odt",
                                "ods",
                                "odp",
                                "png",
                                "jpg",
                                "jpeg",
                                "webp",
                                "gif",
                            ],
                        ],
                    ],
                    [["mimetype", "=", "application/pdf"]],
                    [["mimetype", "=like", "text/%"]],
                ]),
            ]).toList();
        }
        return viewProps;
    },

    get addDocumentsAttachmentMethod() {
        return this.props.chatterParams?.addDocumentsAttachment || this.props.addFromDocuments || this.addDocumentsAttachment;
    },

    get showPasteDocumentsLink() {
        const thread = this.props.chatterParams?.thread || this.props.thread;
        return !thread?.channel?.isAiChat && !this.props.addFromDocuments;
    },
});
