import { Store } from "@mail/core/common/store_service";
import { patch } from "@web/core/utils/patch";

patch(Store.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {number|false|undefined} source id of the AI chat wanting the insert button */
        this.aiInsertButtonTarget = undefined;
    },
});
