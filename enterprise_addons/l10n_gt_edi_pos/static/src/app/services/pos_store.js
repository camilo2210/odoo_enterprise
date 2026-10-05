import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    _isUnidentifiedCustomerLimitExceeded(order) {
        const commercialPartner = order.getPartner().commercial_partner_id;
        const isPartnerCF = commercialPartner.id === this.config._consumidor_final_id;

        const isIdentified =
            !!commercialPartner.vat ||
            Object.values(commercialPartner.additional_identifiers || {}).some((value) => value);
        const isUnidentifiedCustomer = isPartnerCF || !isIdentified;

        const exceedsLimit = order.priceIncl > this.config.l10n_gt_final_consumer_limit;

        return isUnidentifiedCustomer && exceedsLimit;
    },
    getDefaultPartnerId() {
        if (this.config.is_guatemalan_company) {
            return this.config._consumidor_final_id;
        }
        return super.getDefaultPartnerId();
    },
});
