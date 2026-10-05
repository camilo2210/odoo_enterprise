import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { useCheckDuplicatePlugin } from "./account_duplicate_transaction_hook";
import { useService } from "@web/core/utils/hooks";

export class AccountDuplicateTransactionsFormController extends FormController {
    setup() {
        super.setup();
        this.duplicateCheckPlugin = useCheckDuplicatePlugin();
        this.actionService = useService("action");
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "delete_selected_transactions") {
            const selected = this.duplicateCheckPlugin.selectedLines;
            if (selected.size) {
                await this.orm.call("account.bank.statement.line", "unlink", [
                    Array.from(selected),
                ]);
                this.actionService.doAction({ type: "ir.actions.client", tag: "reload" });
            }
            return false;
        }
        return super.beforeExecuteActionButton(...arguments);
    }

    get cogMenuProps() {
        const props = super.cogMenuProps;
        props.items.action = [];
        return props;
    }
}

export const form = { ...formView, Controller: AccountDuplicateTransactionsFormController };

registry.category("views").add("account_duplicate_transactions_form", form);
