import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    isChileanCompany() {
        return this.company.country_id?.code == "CL";
    },
    getDefaultPartnerId() {
        if (this.isChileanCompany()) {
            return this.config._consumidor_final_anonimo_id;
        }
        return super.getDefaultPartnerId();
    },
});
