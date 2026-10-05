import { DocumentsChatter } from "@documents/views/chatter/documents_chatter";
import { useService } from "@web/core/utils/hooks";

import { DocumentsDetailsPanel } from "@documents/components/documents_details_panel/documents_details_panel";

import { Component, t, useProps } from "@odoo/owl";

export class DocumentsRightPanel extends Component {
    static template = "documents.DocumentsViews.RightPanel";

    props = useProps({
        nbViewItems: t.number(),
    });
    static components = {
        Chatter: DocumentsChatter,
        DocumentsDetailsPanel,
    };

    setup() {
        this.documentService = useService("document.document");
        this.state = this.documentService.state;
    }

    get panelDisabled() {
        return (
            !this.state.focusedRecord ||
            !this.state.focusedRecord.data ||
            typeof this.state.focusedRecord.data.id !== "number"
        );
    }
}
