import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const order = this.currentOrder;
        const settleLines = [];
        if (settleLines.length || order.uiState?.settlingInvoice || order.uiState?.depositMoney) {
            this.payment_methods_from_config = this.payment_methods_from_config.filter(
                (pm) => pm.type !== "pay_later"
            );
        }
    },
    get hideChange() {
        return this.currentOrder.uiState?.depositMoney;
    },
    get isForcedToInvoice() {
        const order = this.currentOrder;
        return order.uiState?.settlingInvoice || super.isForcedToInvoice;
    },
    get canValidateDeposit() {
        const totalAmount = this.currentOrder.payment_ids.reduce(
            (acc, payment) => acc + payment.amount,
            0
        );
        return !this.currentOrder.uiState?.depositMoney || totalAmount > 0;
    },
    async onClickValidate() {
        const totalAmount = this.currentOrder.payment_ids.reduce(
            (acc, payment) => acc + payment.amount,
            0
        );
        if (this.currentOrder.uiState?.depositMoney && totalAmount === 0) {
            return this.pos.dialog.add(AlertDialog, {
                title: _t("Invalid Payment"),
                body: _t(
                    "You cannot validate a payment of 0 amount when you are depositing money."
                ),
            });
        }
        return super.onClickValidate(...arguments);
    },
    get partner() {
        return this.currentOrder.getPartner();
    },
    get highlightPartnerBtn() {
        const order = this.currentOrder;
        const partner = order.getPartner();
        return (!this.partner?.useLimit && partner) || (!this.partner?.overDue && partner);
    },
    getLineToRemove() {
        return this.currentOrder.lines.filter((line) => line.product_id.uom_id.isZero(line.qty));
    },
});
