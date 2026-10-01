import { Store } from "@mail/core/common/store_service";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Store} */
const storePatch = {
    setup() {
        super.setup(...arguments);
        this.resCountry = this.makeCachedFetchData("res.country");
    },

    initialize() {
        super.initialize(...arguments);
        this.resCountry.fetch();
    },
};
patch(Store.prototype, storePatch);
