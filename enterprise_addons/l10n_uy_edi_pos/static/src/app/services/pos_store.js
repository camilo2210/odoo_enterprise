import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    isUruguayanCompany() {
        return this.company.account_fiscal_country_id?.code === "UY";
    },
    // @Override
    getDefaultPartnerId() {
        if (this.isUruguayanCompany()) {
            return this.config._l10n_uy_consumidor_final_id;
        }
        return super.getDefaultPartnerId();
    },
    l10nUyIsUnidentifiedCustomer(order) {
        const partner = order.getPartner()?.commercial_partner_id;
        const isPartnerCF = !partner || partner.id === this.config._l10n_uy_consumidor_final_id;
        const isIdentified =
            !!partner?.vat ||
            Object.values(partner?.additional_identifiers || {}).some((value) => value);
        return isPartnerCF || !isIdentified;
    },
    l10nUyIsUnidentifiedCustomerLimitExceeded(order) {
        return (
            this.l10nUyIsUnidentifiedCustomer(order) &&
            order.priceIncl > this.config.l10n_uy_final_consumer_limit
        );
    },
});
