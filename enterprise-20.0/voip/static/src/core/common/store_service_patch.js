import { Store } from "@mail/core/common/store_service";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Store} */
const storePatch = {
    setup() {
        super.setup(...arguments);
        /** @type {object|undefined} server-provided voip configuration, consumed once by the voip service */
        this.voipConfig = undefined;
    },
};
patch(Store.prototype, storePatch);
