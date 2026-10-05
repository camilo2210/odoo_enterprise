import { _t } from "@web/core/l10n/translation";

/**
 * @param {number|undefined} seconds
 * @returns {string}
 */
export function formatTimerText(seconds) {
    if (!seconds) {
        return _t("%(minutes)s:%(seconds)s", { minutes: "00", seconds: "00" });
    }
    if (seconds < 3600) {
        return _t("%(minutes)s:%(seconds)s", {
            minutes: String(Math.floor(seconds / 60)).padStart(2, "0"),
            seconds: String(seconds % 60).padStart(2, "0"),
        });
    }
    return _t("%(hours)s:%(minutes)s:%(seconds)s", {
        hours: String(Math.floor(seconds / 3600)).padStart(2, "0"),
        minutes: String(Math.floor((seconds % 3600) / 60)).padStart(2, "0"),
        seconds: String(seconds % 60).padStart(2, "0"),
    });
}
