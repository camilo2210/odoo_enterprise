import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class IssuingTermsViewDialog extends Component {
    static template = "hr_expense_stripe.issuingTermsViewDialog";
    static components = { Dialog };

    props = useProps({
        action: t.object(),
        close: t.function(),
    });

    setup() {
        this.close = this.props.close;
    }
}

export function IssuingTermsAction(env, action) {
    const dialog = useService("dialog");
    return new Promise((resolve) => {
        dialog.add(
            IssuingTermsViewDialog,
            { action },
            {
                onClose: () => {
                    resolve({ type: "ir.actions.act_window_close" });
                },
            }
        );
    });
}

registry.category("actions").add("hr_expense_stripe.expense_stripe_issuing_terms", IssuingTermsAction);
