import { negateStep } from "@point_of_sale/../tests/generic_helpers/utils";

export function checkCustomerAmount(partner, dueAmount = 0) {
    let step = {
        trigger: `tr:contains(${partner}) .partner-due:contains(${dueAmount})`,
    };

    if (!dueAmount) {
        step = negateStep(step);
    }

    return step;
}

export function selectOrderToSettle(name) {
    return {
        trigger: `tr.o_data_row td[name='name']:contains("${name}")`,
        run: "click",
    };
}

export function checkInvoicePaymentState(state) {
    return {
        trigger: `tr.o_data_row td[name='payment_state']:contains("${state}")`,
        run: "click",
    };
}
