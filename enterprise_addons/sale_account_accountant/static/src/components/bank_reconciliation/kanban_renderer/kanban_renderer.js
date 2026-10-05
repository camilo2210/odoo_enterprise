import { BankRecKanbanRenderer } from "@account_accountant/components/bank_reconciliation/kanban_renderer";
import { patch } from "@web/core/utils/patch";

patch(BankRecKanbanRenderer.prototype, {
    async prepareInitialState(records) {
        await Promise.all([
            super.prepareInitialState(records),
            this.bankReconciliation.fetchPartnersWithSales(records),
        ]);
    },
});
