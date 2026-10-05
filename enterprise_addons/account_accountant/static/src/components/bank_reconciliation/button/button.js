import { Component, useProps, t } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class BankRecButton extends Component {
    static template = "account_accountant.BankRecButton";
    props = useProps({
        label: t.string().optional(),
        action: t.function().optional(),
        count: t.or([t.number(), t.literal(null)]).optional(),
        primary: t.boolean().optional(false),
        toReview: t.boolean().optional(),
        classes: t.string().optional(""),
        isLarge: t.boolean().optional(),
        suggestion: t.number().optional(),
    });

    setup() {
        this.ui = useService("ui");
    }
}
