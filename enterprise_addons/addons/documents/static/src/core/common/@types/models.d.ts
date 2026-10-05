declare module "models" {
    import { Documents as DocumentsClass } from "@documents/core/common/documents_model";

    export interface Documents extends DocumentsClass {}

    export interface Attachment {
        documentData: Object|undefined;
        documentId: number|undefined;
    }
    export interface Store {
        "documents.document": StaticMailRecord<Documents, typeof DocumentsClass>;
        hasDocumentsUserGroup: boolean;
    }
    export interface Thread {
        is_documents_mixin: boolean|undefined;
    }

    export interface Models {
        "documents.document": Documents;
    }
}
