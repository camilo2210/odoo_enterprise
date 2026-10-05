import { ControlPanel } from "@web/search/control_panel/control_panel";
import { AccountReturnCheckEmbeddedActionsPanel } from "./account_return_check_embedded_actions_panel";

export class AccountReturnCheckControlPanel extends ControlPanel {
    static template = "account_reports.account_return_check_control_panel";
    static components = {
        ...ControlPanel.components,
        EmbeddedActionsPanel: AccountReturnCheckEmbeddedActionsPanel,
    };

    setup() {
        super.setup();
        this.embeddedPanelState.embeddedInfos.showEmbedded = true;
    }
}
