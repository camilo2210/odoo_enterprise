import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";

patch(PartnerList.prototype, {
    get isBalanceDisplayed() {
        return true;
    },
    async searchPartner() {
        const partners = await super.searchPartner();
        this.pos.setAllTotalDueOfPartners(partners);
        return partners;
    },
});
