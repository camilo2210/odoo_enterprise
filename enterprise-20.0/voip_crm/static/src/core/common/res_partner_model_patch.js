import { ResPartner } from "@mail/core/common/res_partner_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").ResPartner} */
const resPartnerPatch = {
    setup() {
        super.setup(...arguments);
        /** @type {number|undefined} */
        this.commercial_partner_opportunity_count = undefined;
    },
};
patch(ResPartner.prototype, resPartnerPatch);
