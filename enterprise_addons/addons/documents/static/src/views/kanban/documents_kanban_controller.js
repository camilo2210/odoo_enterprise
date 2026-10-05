import { DocumentsControllerMixin } from "@documents/views/documents_controller_mixin";
import { DocumentsSelectionBox } from "@documents/views/selection_box/documents_selection_box";
import { onMounted, onPatched, signal } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { KanbanController } from "@web/views/kanban/kanban_controller";

export class DocumentsKanbanController extends DocumentsControllerMixin(KanbanController) {
    static template = "documents.DocumentsKanbanView";
    static components = {
        ...KanbanController.components,
        Dropdown,
        SelectionBox: DocumentsSelectionBox,
    };

    uploadFileInputRef = signal.ref();

    setup() {
        super.setup();

        onMounted(() => {
            this.openTrashIfNecessary();
            this.openInitialPreview();
        });
        onPatched(() => {
            this.openTrashIfNecessary();
            this.openInitialPreview();
        });
    }

    getSelectedDocumentsElements() {
        return this.rootRef()?.querySelectorAll(".o_kanban_record.o_record_selected") || [];
    }

    /**
     * Borrowed from ListController for ListView.Selection.
     */
    onUnselectAll() {
        this.model.root.selection.forEach((record) => {
            record.toggleSelection(false);
        });
        this.model.root.selectDomain(false);
    }

    /**
     * Select all the records for a selected domain
     */
    async onSelectDomain() {
        await this.model.root.selectDomain(true);
    }
}
