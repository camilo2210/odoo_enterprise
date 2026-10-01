import { Settings } from "@mail/core/common/settings_model";

import { patch } from "@web/core/utils/patch";

patch(Settings.prototype, {
    setup() {
        super.setup(...arguments);
        // Output device used by VoIP ringtones, independently of call audio.
        this.ringtoneOutputDeviceId = this.localStorage("");
    },
});
