import { _t } from "@web/core/l10n/translation";

export function toDateOnly(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function formatDateLabel(date, showDays = false) {
    const today = luxon.DateTime.now().startOf("day");
    const diff = date.diff(today, "days");

    if (showDays) {
        switch (diff.days) {
            case -2:
                return _t("2 days ago");
            case -1:
                return _t("Yesterday");
            case 0:
                return _t("Today");
            case 1:
                return _t("Tomorrow");
            case 2:
                return _t("In 2 days");
        }
    }

    const options = {
        day: "numeric",
        month: "short",
        year: !today.hasSame(date, "year") ? "numeric" : undefined,
    };
    return date.toLocaleString(options);
}
