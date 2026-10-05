import { Component, t, useProps, usePlugin } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ORM } from "@web/core/orm_plugin";

const payrunStartWarningDialogProps = {
    close: t.function(),
    warnings: t.array(t.object({
        title: t.string(),
        body: t.string(),
        reviewLabel: t.string(),
        reviewAction: t.object(),
    })),
    onReview: t.function(),
    onGenerate: t.function(),
    onDiscard: t.function(),
};

class PayrunStartWarningDialog extends Component {
    static template = "hr_payroll.PayrunStartWarningDialog";
    static components = { Dialog };
    props = useProps(payrunStartWarningDialogProps);

    async onReviewClick(reviewAction) {
        await this.props.onReview(reviewAction);
        this.props.close();
    }

    async onGenerateClick() {
        await this.props.onGenerate();
        this.props.close();
    }

    async onDiscardClick() {
        await this.props.onDiscard();
        this.props.close();
    }
}

function payrunStartWarning(env, actionDescr) {
    const action = useService("action");
    const dialog = useService("dialog");
    const orm = usePlugin(ORM);
    const params = actionDescr.params || {};
    dialog.add(PayrunStartWarningDialog, {
        warnings: params.warnings || [],
        onReview: (reviewAction) => action.doAction(reviewAction),
        onGenerate: async () => {
            const openAction = await orm.call("hr.payslip.run", "action_start_payrun", [params.createVals]);
            action.doAction(openAction);
        },
        onDiscard: () => {},
    });
}

registry.category("actions").add("hr_payroll.payrun_start_warning", payrunStartWarning);
