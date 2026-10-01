import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(FileViewer.prototype, {
    setup() {
        super.setup();
        this.documentService = useService("document.document");
    },
});
