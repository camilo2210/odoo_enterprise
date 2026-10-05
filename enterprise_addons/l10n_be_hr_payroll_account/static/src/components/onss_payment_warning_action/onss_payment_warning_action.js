import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class OnssPaymentWarning extends Component {
    static template = "l10n_be_hr_payroll_account.onssPaymentWarning";
    static components = { Dialog };

    props = useProps({
        action: t.object(),
    });

    setup() {
        this.reportId = this.props.action.params.report_id;
        this.paymentId = this.props.action.params.payment_id;
        this.OnssAccountId = this.props.action.params.onss_account_id;
        this.OnssBankAccountId = this.props.action.params.onss_bank_account_id;
        this.OnssBankAccountNumber = this.props.action.params.onss_bank_account_number;
        this.OnssBalance = this.props.action.params.onss_balance.toFixed(2);
        this.paidAmount = this.props.action.params.paid_amount.toFixed(2);
        this.action = useService("action");
        this.orm = useService("orm");
    }

    async actionMarkDone() {
        await this.orm.call("l10n_be.dmfa", "action_mark_paid", [this.reportId]);
        this.props.close();
        this.action.doAction({ type: "ir.actions.client", tag: "soft_reload" });
    }

    async actionInitiatePayment() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.payment",
            res_id: this.paymentId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: {
                dmfa_id: this.reportId,
                default_payment_type: "outbound",
                default_amount: this.OnssBalance - this.paidAmount,
                default_partner_bank_id: this.OnssBankAccountId,
            },
        });
    }

    async actionViewOnssBalance() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("ONSS Balance"),
            res_model: "account.move.line",
            view_mode: "list",
            views: [[false, "list"]],
            target: "current",
            context: {
                search_default_reconcilable_account: 1,
                search_default_account_id: this.OnssAccountId,
            },
        });
    }
}

export function OnssPaymentWarningAction(env, action) {
    const dialog = useService("dialog");
    dialog.add(OnssPaymentWarning, { action });
}

registry
    .category("actions")
    .add("l10n_be_hr_payroll_account.onss_payment_warning_action", OnssPaymentWarningAction);
