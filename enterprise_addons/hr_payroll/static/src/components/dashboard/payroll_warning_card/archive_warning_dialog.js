import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class ArchiveWarningDialog extends Component {
    static template = "hr_payroll.ArchiveWarningDialog";
    static components = { Dialog };

    props = useProps({
        resId: t.number(),
        warningTitle: t.string(),
        close: t.function(),
        onDismiss: t.function().optional(),
    });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = proxy({ neverShowAgain: false });
    }

    async confirmHide() {
        if (this.state.neverShowAgain) {
            await this.orm.call("hr.payroll.warning", "action_archive", [this.props.resId]);
        } else {
            await this.orm.call("hr.payroll.warning", "action_snooze", [this.props.resId]);
        }

        if (this.props.onDismiss) {
            this.props.onDismiss(this.props.resId);
        }

        this.props.close();
    }
}
