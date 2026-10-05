export function getDocumentActionRequest(resId) {
    return {
        type: "ir.actions.client",
        tag: "document_action_preference",
        context: {
            documents_init_document_id: resId,
            documents_init_folder_id: 0,
        },
    };
}
