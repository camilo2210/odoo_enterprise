import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { patch } from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    /** @override */
    get bankRecSelectCreateDialogContext() {
        return {
            ...super.bankRecSelectCreateDialogContext,
            can_use_factoring: this.statementLineData.l10n_mx_edi_can_use_factoring,
        };
    },
});
