import { Activity } from "@mail/core/common/activity_model";

import { patch } from "@web/core/utils/patch";

patch(Activity.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {number|undefined} */
        this.sign_request_id = undefined;
        /** @type {number|undefined} */
        this.sign_template_id = undefined;
    },
});
