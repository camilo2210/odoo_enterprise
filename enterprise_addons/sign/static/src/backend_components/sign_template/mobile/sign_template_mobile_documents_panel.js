import { t } from "@odoo/owl";
import { SignTemplateSidebar } from "@sign/backend_components/sign_template/sign_template_sidebar";

/**
 * The mobile Documents tab. Document functionality (rename, select, move,
 * replace, delete, upload, etc...) is fully inherited from the desktop sidebar.
 * Only the presentation differs.
 */
export class SignTemplateMobileDocumentsPanel extends SignTemplateSidebar {
    static template = "sign.SignTemplateMobileDocumentsPanel";

    static propsSchema = {
        canAddDocument: t.boolean().optional(),
        deleteDocument: t.function(),
        documents: t.array(),
        hasSignRequests: t.boolean(),
        moveDocumentDown: t.function(),
        moveDocumentUp: t.function(),
        onUpdateDocument: t.function(),
        saveManually: t.function(),
        selectedDocumentId: t.number(),
        signTemplateId: t.number(),
        updateDocumentName: t.function(),
        updateDocuments: t.function(),
        updateSelectedDocument: t.function(),
    };
}
