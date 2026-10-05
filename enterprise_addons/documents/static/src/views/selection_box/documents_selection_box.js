import { SelectionBox } from "@web/views/view_components/selection_box";

export class DocumentsSelectionBox extends SelectionBox {
    setup() {
        super.setup();
        // The root is replaced when the model reloads, do not cache it
        Object.defineProperty(this, "root", { get: () => this.props.root });
    }

    onUnselectAll() {
        super.onUnselectAll();
        this.props.root.model.documentService.bus.trigger("UPDATE-DOCUMENT-FOLDER");
    }
}
