import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

import { worksheetTemplateDeleteConfirmationMessage } from "@worksheet/views/worksheet_template_form/worksheet_template_form";

export class WorksheetTemplateListController extends ListController {
    get deleteConfirmationDialogProps() {
        const deleteConfirmationDialogProps = super.deleteConfirmationDialogProps;
        if (this.model.root.selection.some((r) => r.data.worksheet_count)) {
            deleteConfirmationDialogProps.body = worksheetTemplateDeleteConfirmationMessage;
        }
        return deleteConfirmationDialogProps;
    }
}

export const worksheetTemplateListView = {
    ...listView,
    Controller: WorksheetTemplateListController,
};

registry.category("views").add("worksheet_template_list", worksheetTemplateListView);
