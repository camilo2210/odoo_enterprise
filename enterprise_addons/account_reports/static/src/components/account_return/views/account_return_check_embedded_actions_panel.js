import { EmbeddedActionsPanel } from "@web/search/control_panel/embedded_actions";

export class AccountReturnCheckEmbeddedActionsPanel extends EmbeddedActionsPanel {
    static template = "account_reports.account_return_check_embedded_actions_panel";

    isEmbeddedActionVisible(_action) {
        return true;
    }
}
