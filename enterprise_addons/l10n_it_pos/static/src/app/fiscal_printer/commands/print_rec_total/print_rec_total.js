import { Component, useProps, t } from "@odoo/owl";
import { Justification } from "@l10n_it_pos/app/fiscal_printer/commands/types";

const PaymentType = {
    CASH: "0",
    CHECK: "1",
    CREDIT: "2",
    TICKET: "3",
    MULTIPLE_TICKETS: "4",
    NOT_PAID: "5",
    PAYMENT_DISCOUNT: "6",
};

export class PrintRecTotal extends Component {
    static template = "l10n_it_pos.PrintRecTotal";
    props = useProps({
        operator: t.number().optional(1),
        description: t.string(),
        payment: t.string(),
        paymentType: t.or([t.selection(Object.values(PaymentType)), t.literal(false)]),
        index: t.customValidator(t.number(), (index) => index >= 0).optional(),
        justification: t.selection(Object.values(Justification)).optional(Justification.FIRST_20),
    });
}
