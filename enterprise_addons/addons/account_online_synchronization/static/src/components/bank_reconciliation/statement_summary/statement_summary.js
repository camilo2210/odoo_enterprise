import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { t, usePlugin } from "@odoo/owl";
import {
    BankRecStatementSummary,
    bankRecStatementSummaryProps,
} from "@account_accountant/components/bank_reconciliation/statement_summary/statement_summary";
import { ORM } from "@web/core/orm_plugin";

Object.assign(bankRecStatementSummaryProps, {
    journalAvailableBalanceAmount: t.string().optional(),
});

patch(BankRecStatementSummary.prototype, {
    setup() {
        super.setup();
        this.orm = usePlugin(ORM);
        this.action = useService("action");
    },

    async actionOpenPendingBankStatementLines() {
        this.action.doActionButton({
            type: "object",
            resId: this.props.journalId,
            name: "action_open_pending_bank_statement_lines",
            resModel: "account.journal",
        });
    },
});
