import { Store } from "@mail/core/common/store_service";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Store} */
const storePatch = {
    setup() {
        super.setup(...arguments);
        this.has_access_create_ticket = false;
        /** @type {boolean|undefined} */
        this.helpdesk_livechat_active = undefined;
    },
};
patch(Store.prototype, storePatch);
