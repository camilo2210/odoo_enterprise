/** @odoo-module **/

import { StreamPostDashboard } from "@social/js/stream_post_kanban_dashboard";
import { patch } from "@web/core/utils/patch";

patch(StreamPostDashboard.prototype, {
    _getRelinkContext(account) {
        return {
            ...super._getRelinkContext(...arguments),
            linkedin_link_personal: account.linkedin_is_personal_account,
        };
    },

    /**
     * Hide the engagement statistic for personal LinkedIn account.
     */
    _hasEngagement(account) {
        if (account.media_type === "linkedin" && account.linkedin_is_personal_account) {
            return false;
        }
        return super._hasEngagement(...arguments);
    },

    /**
     * Hide the stories statistic for personal LinkedIn account.
     */
    _hasStories(account) {
        if (account.media_type === "linkedin" && account.linkedin_is_personal_account) {
            return false;
        }
        return super._hasStories(...arguments);
    },
});
