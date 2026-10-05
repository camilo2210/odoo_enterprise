import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const cogMenuRegistry = registry.category("cogMenu");

/**
 * 'Run Auto Reconciliation' cog menu entry.
 *
 * Opens a wizard letting the user pick a journal and a starting date, then runs
 * the auto reconciliation on the unreconciled bank statement lines in that range.
 * Only displayed in the bank reconciliation widget views.
 */
export class AutoReconcileCogMenu extends Component {
    static template = "account_accountant.AutoReconcileCogMenu";
    static components = { DropdownItem };

    setup() {
        this.action = useService("action");
    }

    async openAutoReconcileWizard() {
        const { context } = this.env.searchModel;
        let journalId = false;
        if (context.active_model === "account.journal") {
            journalId = context.active_id;
        } else if (context.default_journal_id) {
            journalId = context.default_journal_id;
        }
        // clicking a cog menu item unmounts this component before
        // the RPC resolves, and OWL's service protection would
        // cancel the promise, preventing doAction from ever running.
        // Accessing the orm service directly via this.env.services skips that
        // lifecycle guard so the call completes even after unmount.
        const action = await this.env.services.orm.call(
            "account.journal",
            "action_open_auto_reconcile_wizard",
            [journalId]
        );
        return this.action.doAction(action);
    }
}

export const autoReconcileCogMenuItem = {
    Component: AutoReconcileCogMenu,
    groupNumber: 5,
    isDisplayed: ({ config }) => {
        const ui = useService("ui");
        return (
            !ui.isSmall &&
            config.actionType === "ir.actions.act_window" &&
            ["kanban", "list"].includes(config.viewType) &&
            ["bank_rec_widget_kanban", "bank_rec_list"].includes(config.viewSubType)
        );
    },
};

cogMenuRegistry.add("auto-reconcile-menu", autoReconcileCogMenuItem, { sequence: 5 });

registry.category("actions").add("bank_rec_reload_reconciled_lines", async (env, actionDescr) => {
    const action = useService("action");
    const bankReconciliation = useService("bankReconciliation");

    await action.doAction({ type: "ir.actions.act_window_close" });
    const { reconciled_ids } = actionDescr.params;
    await bankReconciliation.reloadRecordsByIds(reconciled_ids);
});
