import { DocumentsKanbanRecord } from "@documents/views/kanban/documents_kanban_record";
import { patch } from "@web/core/utils/patch";

export const AccountRenderingContext = {
    /**
     * @override
     */
    get renderingContext() {
        const context = super.renderingContext
        const has_embedded_pdf = this.props.record.data.has_embedded_pdf
        context.mimetype = has_embedded_pdf ? "application/pdf" : context.mimetype
        return context
    },
};

patch(DocumentsKanbanRecord.prototype, AccountRenderingContext);
