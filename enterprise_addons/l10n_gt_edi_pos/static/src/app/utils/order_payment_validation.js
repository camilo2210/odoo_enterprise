import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";

patch(OrderPaymentValidation.prototype, {
    async askBeforeValidation() {
        const result = await super.askBeforeValidation(...arguments);
        if (!result) {
            return false;
        }
        if (
            this.pos.config.is_guatemalan_company &&
            this.order.isToInvoice() &&
            this.pos._isUnidentifiedCustomerLimitExceeded(this.order)
        ) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Limit Exceeded"),
                body: _t(
                    "This order exceeds the maximum amount allowed for an unidentified customer.\nMaximum allowed amount: %(limit)s\nPlease select a customer with a valid Identification Type and Number before continuing.",
                    {
                        limit: formatMonetary(this.pos.config.l10n_gt_final_consumer_limit, {
                            currencyId: this.pos.currency.id,
                        }),
                    }
                ),
            });
            return false;
        }
        return result;
    },
});
