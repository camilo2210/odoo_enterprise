import { DocumentsControllerMixin } from "@documents/views/documents_controller_mixin";
import { DocumentsSelectionBox } from "@documents/views/selection_box/documents_selection_box";
import { signal, onPatched, onMounted } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { ListController } from "@web/views/list/list_controller";

export class DocumentsListController extends DocumentsControllerMixin(ListController) {
    static template = "documents.DocumentsListController";
    static components = {
        ...ListController.components,
        Dropdown,
        SelectionBox: DocumentsSelectionBox,
    };

    uploadFileInputRef = signal.ref();

    get internalOnlyColumns() {
        return ["company_id"];
    }

    setup() {
        super.setup();

        if (!this.userIsInternal) {
            this.archInfo.columns = this.archInfo.columns.filter(
                (col) => !this.internalOnlyColumns.includes(col.name)
            );
        }

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
        return (
            this.rootRef()?.querySelectorAll(
                ".o_data_row.o_data_row_selected .o_list_record_selector"
            ) || []
        );
    }
}
