import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { AccountAuditBalanceListRenderer } from "./account_audit_balance_list_renderer";
import { AccountAuditBalanceListController } from "./account_audit_balance_list_controller";
import { AccountReturnCheckControlPanel } from "./account_return_check_control_panel";

export const accountAuditBalanceList = {
    ...listView,
    Renderer: AccountAuditBalanceListRenderer,
    Controller: AccountAuditBalanceListController,
    ControlPanel: AccountReturnCheckControlPanel,
};

registry.category("views").add("account_audit_balance_list", accountAuditBalanceList);
