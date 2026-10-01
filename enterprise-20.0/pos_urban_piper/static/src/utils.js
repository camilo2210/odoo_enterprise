import { formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
const { DateTime } = luxon;
/**
 * This method converts time from milliseconds to the user's time zone.
 */
export function getTime(time) {
    return formatDateTime(DateTime.fromMillis(time));
}

export const URBANPIPER_ORDER_STATUS = {
    placed: _t("Placed"),
    acknowledged: _t("Acknowledged"),
    food_ready: _t("Food Ready"),
    dispatched: _t("Dispatched"),
    completed: _t("Completed"),
    cancelled: _t("Cancelled"),
};

export const UP_CONSOLE_COLOR = "#ff7722";

export function base64ToBlob(base64, mimeType) {
    if (!mimeType || !base64 || typeof base64 !== "string") {
        return;
    }
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    return new Blob([bytes], { type: mimeType });
}
