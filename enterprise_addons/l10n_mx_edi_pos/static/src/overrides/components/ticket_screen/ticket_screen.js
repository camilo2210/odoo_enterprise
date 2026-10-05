/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(TicketScreen.prototype, {
    //@override
    async onDoRefund() {
        if (this.pos.company.country_id?.code === "MX") {
            const order = this.getSelectedOrder();
            const orderLineToRefund = this.pos.linesToRefund.filter(
                (line) => line.line.order_id.uuid === order.uuid
            );

            let refundLinesTotal = orderLineToRefund.reduce(
                (sum, line) => sum + line.line.prices.total_included,
                0
            );
            if (order.discountLines) {
                refundLinesTotal += order.discountLines.reduce(
                    (sum, line) => sum + line.prices.total_included,
                    0
                );
            }
            const originalLinesTotal = order.lines.reduce(
                (sum, line) => sum + line.prices.total_included,
                0
            );
            if (order.currency.isPositive(refundLinesTotal - originalLinesTotal)) {
                this.dialog.add(AlertDialog, {
                    title: _t("Refund Amount Exceeds Original Order"),
                    body: _t(
                        "The refund amount exceeds the original order total. You are probably forgetting to include a discount."
                    ),
                });
                return;
            }
        }
        await super.onDoRefund(...arguments);
    },
});
