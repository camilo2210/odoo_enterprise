/** @odoo-module */

import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    // @Extend
    async askBeforeValidation() {
        if (this.pos.company.l10n_co_edi_pos_dian_enabled) {
            const currentPartner = this.order.getPartner();

            if (
                !currentPartner ||
                currentPartner.id === this.pos.config._l10n_co_final_consumer_id
            ) {
                this.order.to_invoice = false;
            } else {
                this.order.to_invoice = true;
            }
        }

        return super.askBeforeValidation();
    },
    // @Override
    shouldDownloadInvoice() {
        return this.pos.company.l10n_co_edi_pos_dian_enabled
            ? false
            : super.shouldDownloadInvoice();
    },
});
