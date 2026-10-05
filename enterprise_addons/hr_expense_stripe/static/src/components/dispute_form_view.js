import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { FormController } from "@web/views/form/form_controller";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

// To be overriden in the demo module
export class disputeSubmissionConfirmationDialog extends ConfirmationDialog {}

export class disputeFormViewController extends FormController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.action = useService("action");
        this.canEdit = false;
        onWillStart(async () => {
            this.canEdit = await user.hasGroup("hr_expense.group_hr_expense_manager");
        });
    }

    get canSubmit() {
        return this.model.root.data.can_submit;
    }

    get isSubmitted() {
        return this.model.root.data.state !== 'unsubmitted';
    }

    get confirmationDialogExtraProps() {
        // To be overriden in the demo module
        return {}
    }

    async submit() {
        if (!this.canSubmit) {
            return;
        }

        const saved = await this.save();
        if (!saved || !this.model.root.resId) {
            return;
        }
        await this.orm.call("hr.expense.stripe.dispute", "action_create_or_update_dispute", [this.model.root.resId]);

        await this.dialog.add(disputeSubmissionConfirmationDialog, {
            title: _t("Submit Dispute"),
            body: _t(
                'You can only submit a dispute once. If you have additional evidence, press "Discard" and add it later.'
            ),
            confirmLabel: _t("Submit"),
            cancelLabel: _t("Discard"),
            confirm: async () => {
                await this.orm.call("hr.expense.stripe.dispute", "action_submit", [this.model.root.resId]);
                this.action.doAction({ type: "ir.actions.act_window_close" });
            },
            cancel: () => {},
            ...this.confirmationDialogExtraProps,
        });
    }

    async saveForLater() {
        const saved = await this.save();
        if (!saved || !this.model.root.resId) {
            return;
        }

        await this.orm.call("hr.expense.stripe.dispute", "action_create_or_update_dispute", [this.model.root.resId]);
        this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

export const disputeFormView = {
    ...formView,
    Controller: disputeFormViewController,
    buttonDialogTemplate: "hr.expense.stripe.disputeFormView.buttons",
};

registry.category("views").add("stripe_dispute_form", disputeFormView);
