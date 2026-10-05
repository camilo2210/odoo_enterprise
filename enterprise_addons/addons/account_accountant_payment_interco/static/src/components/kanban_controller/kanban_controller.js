import { BankRecKanbanController } from "@account_accountant/components/bank_reconciliation/kanban_controller";
import { BankRecListController } from "@account_accountant/components/bank_reconciliation/list_view/list";
import { patch } from "@web/core/utils/patch";
import { makeActiveField } from "@web/model/relational_model/utils";

// Needed by getAvailableReconciledLinesDomain, called from both views
for (const Controller of [BankRecKanbanController, BankRecListController]) {
    patch(Controller.prototype, {
        get modelParams() {
            const params = super.modelParams;
            params.config.activeFields.available_inter_company_ids = makeActiveField();
            params.config.activeFields.available_inter_company_ids.related = {
                fields: {
                    id: { name: "id", type: "int" },
                    account_interco_receivable_id: {
                        name: "interco_receivable_account_id",
                        type: "int",
                    },
                    account_interco_payable_id: { name: "interco_payable_account_id", type: "int" },
                },
                activeFields: {
                    id: makeActiveField(),
                    account_interco_receivable_id: makeActiveField(),
                    account_interco_payable_id: makeActiveField(),
                },
            };
            return params;
        },
    });
}
