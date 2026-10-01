import { onMounted } from "@odoo/owl";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            if (this.pos.config.is_guatemalan_company && !this.isRefundOrder) {
                this.currentOrder.setToInvoice(true);
            }
        });
    },
    async toggleIsToInvoice() {
        if (
            this.pos.config.is_guatemalan_company &&
            this.isRefundOrder &&
            !this.currentOrder.refunded_order_id?.is_singly_invoiced
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("Linked Order Not Invoiced"),
                body: _t(
                    "The order linked to this refund has not been electronically invoiced. Please make sure the original order has an electronic invoice before trying to create an electronic credit note for this refund."
                ),
            });
        } else {
            await super.toggleIsToInvoice(...arguments);
        }
    },
});
