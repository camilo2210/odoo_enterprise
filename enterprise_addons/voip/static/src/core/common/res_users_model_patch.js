import { ResUsers } from "@mail/core/common/res_users_model";

import { patch } from "@web/core/utils/patch";

patch(ResUsers.prototype, {
    setup() {
        super.setup(...arguments);
        /** @type {boolean|undefined} whether the in-call icon may show in the user's im status */
        this.should_display_in_call_im_status = undefined;
    },
});
