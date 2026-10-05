import { patch } from "@web/core/utils/patch";

import { StockValuationReportController } from "@account/components/stock_valuation/controller";

const SALE_ACCRUAL_ACTIONS = {
    invoice_to_be_issued: "sale_account_accountant.sale_order_line_accrual_to_bill_action",
    invoiced_not_delivered: "sale_account_accountant.sale_order_line_accrual_deferred_revenues_action",
};

patch(StockValuationReportController.prototype, {
    async loadReportData() {
        const data = await super.loadReportData();
        for (const line of this.data.accrual?.lines || []) {
            const action = SALE_ACCRUAL_ACTIONS[line.accrual_type];
            if (action) {
                line.method = () => this.actionService.doAction(action, {
                    additionalContext: { search_default_tracked_goods: 1 },
                });
            }
        }
        return data;
    },
});
