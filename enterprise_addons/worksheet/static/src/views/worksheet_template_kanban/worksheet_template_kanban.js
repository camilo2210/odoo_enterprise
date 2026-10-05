import { registry } from "@web/core/registry";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";

import { worksheetTemplateDeleteConfirmationMessage } from "@worksheet/views/worksheet_template_form/worksheet_template_form";

export class WorksheetTemplateKanbanController extends KanbanController {
    get deleteConfirmationDialogProps() {
        const deleteConfirmationDialogProps = super.deleteConfirmationDialogProps;
        if (this.model.root.selection.some((r) => r.data.worksheet_count)) {
            deleteConfirmationDialogProps.body = worksheetTemplateDeleteConfirmationMessage;
        }
        return deleteConfirmationDialogProps;
    }
}

export const worksheetTemplateKanbanView = {
    ...kanbanView,
    Controller: WorksheetTemplateKanbanController,
};

registry.category("views").add("worksheet_template_kanban", worksheetTemplateKanbanView);
