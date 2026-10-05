import { DocumentsAction } from "@documents/views/action/documents_action";
import { useService } from "@web/core/utils/hooks";
import { FileViewer as WebFileViewer } from "@web/core/file_viewer/file_viewer";
import { proxy, useEffect, untrack } from "@odoo/owl";

export class FileViewer extends WebFileViewer {
    static template = "documents.FileViewer";
    static components = {
        DocumentsAction,
    };

    setup() {
        super.setup();
        /** @type {import("@documents/core/document_service").DocumentService} */
        this.documentService = useService("document.document");
        this.onSelectDocument = this.documentService.documentList?.onSelectDocument;
        this.previewed = proxy({
            document: this.documentService.documentList.documents[this.state.index],
        });
        this.folderId = this.documentService.documentList?.folderId;
        useEffect(() => {
            const indexOfFileToPreview = this.props.startIndex;
            untrack(() => {
                if (indexOfFileToPreview !== this.state.index) {
                    this.activateFile(indexOfFileToPreview);
                    this.setPreviewedDocument(
                        this.documentService.documentList.documents[indexOfFileToPreview]
                    );
                }
            });
        });
    }

    close() {
        this.documentService.documentList?.onDeleteCallback();
        this.setPreviewedDocument(null);
        super.close();
    }

    next() {
        super.next();
        this.setPreviewedDocument(this.documentService.documentList.documents[this.state.index]);

        if (this.onSelectDocument) {
            const documentList = this.documentService.documentList;
            if (
                !documentList ||
                !documentList.selectedDocument ||
                !documentList.documents ||
                !documentList.documents.length
            ) {
                return;
            }
            const index = documentList.documents.findIndex(
                (document) => document === documentList.selectedDocument
            );
            const nextIndex = index === documentList.documents.length - 1 ? 0 : index + 1;
            documentList.selectedDocument = documentList.documents[nextIndex];
            this.onSelectDocument(documentList.selectedDocument.record);
        }
    }

    previous() {
        super.previous();
        this.setPreviewedDocument(this.documentService.documentList.documents[this.state.index]);

        if (this.onSelectDocument) {
            const documentList = this.documentService.documentList;
            if (
                !documentList ||
                !documentList.selectedDocument ||
                !documentList.documents ||
                !documentList.documents.length
            ) {
                return;
            }
            const index = documentList.documents.findIndex(
                (doc) => doc === documentList.selectedDocument
            );
            // if we're on the first document, go "back" to the last one
            const previousIndex = index === 0 ? documentList.documents.length - 1 : index - 1;
            documentList.selectedDocument = documentList.documents[previousIndex];
            this.onSelectDocument(documentList.selectedDocument.record);
        }
    }

    setPreviewedDocument(previewedDocument) {
        this.previewed.document = previewedDocument;
        this.documentService.setPreviewedDocument(previewedDocument);
    }
}
