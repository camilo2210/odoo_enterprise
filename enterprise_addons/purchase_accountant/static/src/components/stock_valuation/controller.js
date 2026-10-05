import { patch } from "@web/core/utils/patch";

import { StockValuationReportController } from "@account/components/stock_valuation/controller";

const PURCHASE_ACCRUAL_ACTIONS = {
    bill_to_receive: "purchase_accountant.purchase_order_line_accrual_bill_to_receive_action",
    billed_not_received: "purchase_accountant.purchase_order_line_accrual_prepaid_expenses_action",
};

patch(StockValuationReportController.prototype, {
    async loadReportData() {
        const data = await super.loadReportData();
        for (const line of this.data.accrual?.lines || []) {
            const action = PURCHASE_ACCRUAL_ACTIONS[line.accrual_type];
            if (action) {
                line.method = () => this.actionService.doAction(action, {
                    additionalContext: { search_default_tracked_goods: 1 },
                });
            }
        }
        return data;
    },
});
