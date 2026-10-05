import { DocumentsRightPanel } from "@documents/components/documents_right_panel/documents_right_panel";
import { DocumentsRendererMixin } from "@documents/views/documents_renderer_mixin";
import { DocumentsFileViewer } from "@documents/views/helper/documents_file_viewer";

import { ActivityRenderer } from "@mail/views/web/activity/activity_renderer";
import { signal } from "@odoo/owl";

export class DocumentsActivityRenderer extends DocumentsRendererMixin(ActivityRenderer) {
    static template = "documents.DocumentsActivityRenderer";
    static components = {
        ...ActivityRenderer.components,
        DocumentsRightPanel,
        DocumentsFileViewer,
    };

    rootRef = signal.ref();

    /**
     * Overridden to avoid selecting the folder in the activity view as only document are selectable in that view.
     */
    getDefaultRefreshFocus() {
        return null;
    }
}
