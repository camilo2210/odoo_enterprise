import { t } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import {
    PaymentScreenPaymentLines,
    paymentScreenPaymentLinesProps,
} from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";

Object.assign(paymentScreenPaymentLinesProps, {
    refundLines: t.array().optional(),
    selectRefundLine: t.function(),
});

patch(PaymentScreenPaymentLines.prototype, {
    getPaymentActionState(line) {
        const state = super.getPaymentActionState(line);

        if (
            ["waiting_refund", "waiting_card", "waiting_scan"].includes(state.id) &&
            line.payment_provider === "tyro"
        ) {
            state.title = line.tyro_status;
        }

        return state;
    },
});
