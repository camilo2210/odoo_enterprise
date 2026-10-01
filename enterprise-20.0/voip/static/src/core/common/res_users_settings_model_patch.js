import { ResUsersSettings } from "@mail/core/common/res_users_settings_model";
import { fields } from "@mail/model/export";

import { patch } from "@web/core/utils/patch";

export const FOREVER = luxon.DateTime.utc(9999, 12, 31);

patch(ResUsersSettings.prototype, {
    setup() {
        super.setup();
        this.do_not_disturb_until_dt = fields.Datetime();
        this.onChange(
            () => [this.do_not_disturb_until_dt],
            function onChangeDoNotDisturbUntil(doNotDisturbUntil) {
                clearTimeout(this.resetDoNotDisturbTimeoutId);
                this.store.env.services.voip?.userAgent.updateIncomingRingtone();
                if (
                    !doNotDisturbUntil ||
                    doNotDisturbUntil <= luxon.DateTime.now() ||
                    doNotDisturbUntil.toMillis() == FOREVER.toMillis()
                ) {
                    return;
                }
                this.resetDoNotDisturbTimeoutId = setTimeout(() => {
                    this.do_not_disturb_until_dt = null;
                }, doNotDisturbUntil.diffNow().as("milliseconds"));
            },
            { immediate: true, initialRun: false }
        );
        /** @type {string} */
        this.external_device_number = undefined;
        /** @type {"ask"|"voip"|"phone"} */
        this.how_to_call_on_mobile = undefined;
        /** @type {number} */
        this.resetDoNotDisturbTimeoutId;
        /** @type {boolean} */
        this.should_call_from_another_device = undefined;
        /** @type {string} */
        this.voip_secret = undefined;
        /** @type {string} */
        this.voip_username = undefined;
    },
});
