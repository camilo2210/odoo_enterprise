/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    // @Override
    getSyncAllOrdersContext(orders, options = {}) {
        const context = super.getSyncAllOrdersContext(orders, options);

        if (this.company.l10n_co_edi_pos_dian_enabled) {
            // this ensures that we send all the invoices (generated from pos orders) to dian
            context.generate_pdf = true;
        }

        return context;
    },
    // @Override
    getDefaultPartnerId() {
        if (this.company.l10n_co_edi_pos_dian_enabled) {
            return this.config._final_consumer_id;
        }
        return super.getDefaultPartnerId();
    },
});
