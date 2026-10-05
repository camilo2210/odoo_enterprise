import {
    KanbanRecordQuickCreate,
    KanbanQuickCreateController,
} from "@web/views/kanban/kanban_record_quick_create";

export class BankRecQuickCreateController extends KanbanQuickCreateController {
    static template = "account_accountant.BankRecQuickCreateController";

    showFormDialogInError(e) {
        // Override because in the case of the bank rec widget, we do not want the bank statement line form view to be
        // opened when an error occurs. Instead, we close the quick create and display the error.
        this.props.quickCreateState.closeQuickCreate();
        throw e;
    }
}

export class BankRecQuickCreate extends KanbanRecordQuickCreate {
    static components = { KanbanQuickCreateController: BankRecQuickCreateController };
}
