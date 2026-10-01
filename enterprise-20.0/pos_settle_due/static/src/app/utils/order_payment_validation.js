import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(OrderPaymentValidation.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.order;

        if (order.uiState.settlingInvoice) {
            return await this.settlingInvoices();
        } else if (order.uiState.depositMoney) {
            return await this.depositMoney();
        }

        return super.validateOrder(isForceValidate);
    },
    get isDepositOrder() {
        return this.order.uiState.is_settling_account;
    },
    async settlingInvoices() {
        const order = this.order;
        const isPayLater = order.payment_ids.some(
            (payment) => payment.payment_method_id.type === "pay_later"
        );

        if (isPayLater) {
            return this.pos.dialog.add(AlertDialog, {
                title: _t("Settle Invoice"),
                body: _t("Pay later payments cannot be used when settling invoices."),
            });
        }

        if (order.change) {
            // Maybe re-implment the whole change process later...
            // Add the change on the customer account ?
            return this.pos.dialog.add(AlertDialog, {
                title: _t("Settle Invoice"),
                body: _t("You cannot have a change when settling invoices."),
            });
        }

        const invoiceIds = order.uiState.settledInvoiceIds || [];
        const serializedPayments = order.payment_ids.map((payment) => payment.serializeForORM());

        try {
            await this.pos.data.call("account.move", "settle_invoices_from_pos", [
                invoiceIds,
                this.pos.session.id,
                serializedPayments,
            ]);
            this.pos.notification.add(_t("Invoice(s) settled successfully."), { type: "success" });
            await this.pos.deleteOrderAndGoToDefaultScreen(order);
        } catch {
            const message = _t(
                "An error occurred while settling the invoice(s). Please try again."
            );
            this.pos.notification.add(message, { type: "danger" });
        }
    },
    async depositMoney() {
        const order = this.order;
        const total = order.payment_ids.reduce((sum, payment) => sum + payment.amount, 0);
        const confirmed = await ask(this.pos.dialog, {
            title: _t("The order is empty"),
            body: _t(
                "Do you want to deposit %s to %s?",
                this.pos.formatCurrency(total),
                order.partner_id.name
            ),
            confirmLabel: _t("Yes"),
        });

        if (!confirmed) {
            return false;
        }

        const serializedPayments = order.payment_ids.map((payment) => payment.serializeForORM());
        try {
            await this.pos.data.call("res.partner", "deposit_money_from_pos", [
                this.order.partner_id.id,
                this.pos.session.id,
                serializedPayments,
            ]);
            this.pos.notification.add(_t("Deposit successful."), { type: "success" });
            await this.pos.deleteOrderAndGoToDefaultScreen(order);
        } catch {
            const message = _t("An error occurred while depositing the money. Please try again.");
            this.pos.notification.add(message, { type: "danger" });
        }
    },
});
