import { BankRecStatementLine } from "@account_accountant/components/bank_reconciliation/statement_line/statement_line";
import { patch } from "@web/core/utils/patch";

patch(BankRecStatementLine.prototype, {
    get hasSaleOrders() {
        return !!this.bankReconciliation.partnersWithSales[this.recordData.partner_id.id];
    },

    async actionOpenSaleOrders() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            target: "current",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            name: "Sale Orders",
            context: {
                search_default_partner_id: this.recordData.partner_id.id,
                bank_rec_widget_statement_line_id: this.recordData.id,
            },
        });
    },

    get buttonListProps() {
        return {
            ...super.buttonListProps,
            hasSaleOrders: this.hasSaleOrders,
            actionOpenSaleOrders: () => this.actionOpenSaleOrders(),
        };
    },
});
