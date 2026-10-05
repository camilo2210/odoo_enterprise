import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useEnv } from "@web/owl2/utils";

const cogMenuRegistry = registry.category("cogMenu");


export class RefreshAccountReturns extends Component {
    static template = "account_reports.RefreshAccountReturns";
    static components = { DropdownItem };

    env = useEnv();

    async refresh_all_account_returns() {
        await rpc("/web/dataset/call_kw/account.return/action_refresh_all_returns", {
            model: "account.return",
            method: "action_refresh_all_returns",
            args: [],
            kwargs: {},
        });
        await this.env.model.load();
    }
}

export const refreshAccountReturns = {
    Component: RefreshAccountReturns,
    groupNumber: 5,
    isDisplayed: ({ config }) => {
        return config.actionType === "ir.actions.act_window" &&
        ["kanban"].includes(config.viewType) &&
        ["account_return_kanban"].includes(config.viewSubType);
    },
};

cogMenuRegistry.add("refresh-account-returns-menu", refreshAccountReturns, { sequence: 10 });
