import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    AccountMoveLineListController,
    AccountMoveLineListRenderer,
    AccountMoveLineListView,
} from "../move_line_list/move_line_list";

function useAutoReconcileAction() {
    const action = useService("action");
    return (group = null) => {
        const options = {};
        if (group) {
            options.additionalContext = {
                domain: group.list.domain,
            };
        }
        return action.doAction("account_accountant.action_open_auto_reconcile_wizard", options);
    };
}

export class AccountMoveLineReconcileListController extends AccountMoveLineListController {
    openAutoReconcileWizard = useAutoReconcileAction();
}

export class AccountMoveLineReconcileListRenderer extends AccountMoveLineListRenderer {
    static groupRowTemplate = "account_accountant.AccountMoveLineReconcileGroupRow";

    callAutoReconcileAction = useAutoReconcileAction();

    setup() {
        super.setup();
        this.props.list.groups?.map((group) => this.toggleGroup(group)); // unfold the first groups (account_id)
    }
}

export const AccountMoveLineReconcileLineListView = {
    ...AccountMoveLineListView,
    Controller: AccountMoveLineReconcileListController,
    Renderer: AccountMoveLineReconcileListRenderer,
    buttonTemplate: "account_accountant.ListViewReconcile.Buttons",
};

registry
    .category("views")
    .add("account_move_line_reconcile_list", AccountMoveLineReconcileLineListView);
