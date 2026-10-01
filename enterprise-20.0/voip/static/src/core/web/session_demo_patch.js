/** @odoo-module **/

import { Session } from "@voip/core/web/session";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(Session.prototype, {
    /**
     * @override
     */
    get statusText() {
        if (this.__sipJsSession?.isMock && !this.isOnHold) {
            return _t("Demo call");
        }
        return super.statusText;
    },

    /**
     * @override
     */
    _getRecordingUploadOptions() {
        const options = super._getRecordingUploadOptions();
        if (this.__sipJsSession?.isMock) {
            options.is_production = false;
        }
        return options;
    },
});
