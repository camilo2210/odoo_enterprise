import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    isEcuadorianCompany() {
        return this.company.country_id?.code == "EC";
    },
    getDefaultPartnerId() {
        if (this.isEcuadorianCompany()) {
            return this.config._final_consumer_id;
        }
        return super.getDefaultPartnerId();
    },
    // @Override
    // For EC, if the partner on the refund was End Consumer we need to allow the user to change it.
    async selectPartner() {
        if (!this.isEcuadorianCompany()) {
            return super.selectPartner(...arguments);
        }
        const currentOrder = this.getOrder();
        if (!currentOrder) {
            return;
        }
        const currentPartner = currentOrder.getPartner();
        if (currentPartner && currentPartner.id === this.config._final_consumer_id) {
            this.dialog.add(PartnerList, {
                partner: currentPartner,
                getPayload: (newPartner) => newPartner && currentOrder.setPartner(newPartner),
            });
            return currentPartner;
        }
        return super.selectPartner(...arguments);
    },
});

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        if (this.company.country_id?.code == "EC" && vals.to_invoice === undefined) {
            this.to_invoice = true;
        }
    },

    get isCustomerRequired() {
        if (this.company.country_id?.code == "EC" && !this.partner_id) {
            return true;
        }
        return super.isCustomerRequired;
    },
});
