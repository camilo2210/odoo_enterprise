import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";

patch(OrderPaymentValidation.prototype, {
    // @Extend
    async askBeforeValidation() {
        if (this.pos.isUruguayanCompany()) {
            const partner = this.order.getPartner()?.commercial_partner_id;
            // Only RUT-identified customers are invoiced, everyone else gets an e-Ticket
            this.order.to_invoice = !!partner?.vat && partner?.country_id?.code === "UY";
        }

        const result = await super.askBeforeValidation(...arguments);
        if (!result) {
            return false;
        }

        if (
            this.pos.isUruguayanCompany() &&
            this.pos.l10nUyIsUnidentifiedCustomer(this.order) &&
            this.order.payment_ids.some((line) => line.payment_method_id.type === "pay_later")
        ) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Customer Required"),
                body: _t(
                    "Customer Account cannot be used for an unidentified customer.\nPlease select a customer with a valid identification number before continuing."
                ),
            });
            return false;
        }

        if (
            this.pos.isUruguayanCompany() &&
            !this.order.to_invoice &&
            this.pos.l10nUyIsUnidentifiedCustomerLimitExceeded(this.order)
        ) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Limit Exceeded"),
                body: _t(
                    "This order exceeds the maximum amount allowed for an unidentified customer.\nMaximum allowed amount: %(limit)s\nPlease select a customer with a valid identification number before continuing.",
                    {
                        limit: formatMonetary(this.pos.config.l10n_uy_final_consumer_limit, {
                            currencyId: this.pos.currency.id,
                        }),
                    }
                ),
            });
            return false;
        }

        return result;
    },
    // @Override
    shouldDownloadInvoice() {
        return this.pos.isUruguayanCompany() ? false : super.shouldDownloadInvoice();
    },
});
