import { ListController } from "@web/views/list/list_controller";
import { auditBalanceListChatterPlugin } from "./account_audit_balance_list_chatter_plugin";
import { onWillStart, providePlugins, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";

export class AccountAuditBalanceListController extends ListController {
    static template = "account_reports.account_audit_balance_list_controller";

    orm = usePlugin(ORM);

    setup() {
        providePlugins([auditBalanceListChatterPlugin]);
        super.setup();
        this.chatterPlugin = usePlugin(auditBalanceListChatterPlugin);

        onWillStart(async () => {
            const working_file_id = this.props.context?.working_file_id;
            if (!working_file_id) {
                return;
            }

            const working_file = await this.orm.searchRead(
                "account.return",
                [["id", "=", working_file_id]],
                ["date_to"],
                { limit: 1 }
            );
            if (working_file.length === 1) {
                this.chatterPlugin.date_to.set(working_file[0].date_to);
            }
        });
    }

    openJournalItems() {
        this.actionService.doActionButton({
            context: this.model.root.context,
            resModel: this.model.root.resModel,
            name: "action_audit_account",
            type: "object",
            resIds: this.model.root.selection.map((record) => record.data.code),
        });
    }
}
