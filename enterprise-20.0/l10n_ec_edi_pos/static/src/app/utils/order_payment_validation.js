import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        if (this.pos.isEcuadorianCompany()) {
            if (
                this.order.isRefund &&
                this.order.getPartner().id === this.pos.config._final_consumer_id
            ) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Refund not possible"),
                    body: _t("You cannot refund orders for Consumidor Final."),
                });
                return false;
            }
            if (
                this.order.priceIncl > this.pos.config.l10n_ec_consumer_final_limit &&
                this.order.getPartner()?.vat === "9999999999999" && // This compliance is for the VAT number, not for the final consumer.
                this.order.isToInvoice()
            ) {
                this.pos.dialog.add(AlertDialog, {
                    body: _t(
                        "This sale exceeds the maximum amount allowed for an unidentified consumer.\nPlease select the real customer with a valid RUC/ID before continuing."
                    ),
                });
                return false;
            }
        }
        return super.isOrderValid(...arguments);
    },
    shouldDownloadInvoice() {
        return this.pos.isEcuadorianCompany() ? false : super.shouldDownloadInvoice();
    },
});
