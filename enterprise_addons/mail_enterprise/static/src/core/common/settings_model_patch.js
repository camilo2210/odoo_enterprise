import { Settings } from "@mail/core/common/settings_model";

import { patch } from "@web/core/utils/patch";

// web_enterprise columns of the settings row: declared here as mail_enterprise
// is the mail <-> web_enterprise bridge
patch(Settings.prototype, {
    setup() {
        super.setup();
        /** @type {"light"|"dark"} */
        this.color_scheme = undefined;
        /** @type {string} JSON of the home menu ordering */
        this.homemenu_config = undefined;
    },
});
