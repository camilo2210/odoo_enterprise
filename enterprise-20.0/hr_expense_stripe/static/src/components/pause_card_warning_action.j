import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class PauseCardWarning extends Component {
    static template = "hr_expense_stripe.pauseCardWarningDialog";
    static components = { Dialog };

    props = useProps({
        action: t.object(),
        close: t.function(),
    });

    setup() {
        this.card_id = this.props.action.params.res_id;

        this.dialog = useService("dialog");
        this.ui = useService("ui");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.close = this.props.close;
    }

    // Common
    async actionPauseCard() {
        await this.orm.call("hr.expense.stripe.card", 'action_pause_card', [ this.card_id ]);
        this.close();
    }
}

export function PauseCardAction(env, action) {
    const dialog = useService("dialog");
    return new Promise((resolve) => {
        dialog.add(
            PauseCardWarning,
            { action },
            {
                onClose: () => {
                    resolve({ type: "ir.actions.act_window_close" });
                },
            }
        );
    });
}

registry.category("actions").add("hr_expense_stripe.pause_card_warning_action", PauseCardAction);
