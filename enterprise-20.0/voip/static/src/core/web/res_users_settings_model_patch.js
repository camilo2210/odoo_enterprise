import { ResUsersSettings } from "@mail/core/common/res_users_settings_model";

import { FOREVER } from "@voip/core/common/res_users_settings_model_patch";

import { serializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

patch(ResUsersSettings.prototype, {
    setVoipDoNotDisturb(minutes) {
        if (minutes === 0) {
            // available
            this.do_not_disturb_until_dt = null;
        } else if (minutes === -1) {
            this.do_not_disturb_until_dt = FOREVER;
        } else {
            this.do_not_disturb_until_dt = luxon.DateTime.now().plus({ minutes });
        }
        this._saveVoipSettings();
    },

    /** @returns {Promise<any>} */
    _saveVoipSettings() {
        return this.store.env.services.orm.call(
            "res.users.settings",
            "set_res_users_settings",
            [[this.id]],
            {
                new_settings: {
                    do_not_disturb_until_dt: this.do_not_disturb_until_dt
                        ? serializeDateTime(this.do_not_disturb_until_dt)
                        : false,
                },
            }
        );
    },
});
