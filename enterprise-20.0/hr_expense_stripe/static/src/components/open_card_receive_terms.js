import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class CardReceiveTermsViewDialog extends Component {
    static template = "hr_expense_stripe.cardReceiveTermsViewDialog";
    static components = { Dialog };

    props = useProps({
        action: t.object(),
        close: t.function(),
    });
}

export function CardReceiveTermsAction(env, action) {
    const dialog = useService("dialog");
    dialog.add(CardReceiveTermsViewDialog, { action });
}

registry.category("actions").add("hr_expense_stripe.expense_stripe_card_receive_terms", CardReceiveTermsAction);
