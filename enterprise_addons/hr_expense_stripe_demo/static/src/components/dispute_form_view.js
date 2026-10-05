
import { props, t } from "@odoo/owl";
import { confirmationDialogProps } from "@web/core/confirmation_dialog/confirmation_dialog";
import { disputeFormViewController, disputeSubmissionConfirmationDialog } from '@hr_expense_stripe/components/dispute_form_view';
import { patch } from '@web/core/utils/patch';

patch(disputeSubmissionConfirmationDialog, {
    template: 'hr.expense.stripe.demo.disputeCreationConfirmationDialog',
});

patch(disputeSubmissionConfirmationDialog.prototype, {
    setup() {
        this.props = props({
            ...confirmationDialogProps,
            submit_and_win: t.function().optional(),
            submit_and_lose: t.function().optional(),
        });
        super.setup();
    },

    async submit_and_win() {
        await this.props.submit_and_win();
        return this._confirm();
    },

    async submit_and_lose() {
        await this.props.submit_and_lose();
        return this._confirm();
    },
});

patch(disputeFormViewController.prototype, {
    get confirmationDialogExtraProps() {
        return {
            submit_and_win: async () => {
                await this.orm.call('hr.expense.stripe.dispute', 'write', [[this.model.root.resId], { explanation: 'winning_evidence' }]);
                await this.orm.call('hr.expense.stripe.dispute', 'action_create_or_update_dispute', [[this.model.root.resId]]);
            },
            submit_and_lose: async () => {
                await this.orm.call('hr.expense.stripe.dispute', 'write', [[this.model.root.resId], { explanation: 'losing_evidence' }]);
                await this.orm.call('hr.expense.stripe.dispute', 'action_create_or_update_dispute', [[this.model.root.resId]]);
            },
        }
    },
});
