import { _t } from "@web/core/l10n/translation";
import { pyToJsLocale } from "@web/core/l10n/utils/locales";

export function roundTimeSpent({ minutesSpent, minimum = 15, rounding = 15 }) {
    minutesSpent = Math.max(minimum, minutesSpent);
    if (rounding) {
        minutesSpent = Math.ceil(minutesSpent / rounding) * rounding;
    }
    return minutesSpent;
}

export function formatDurationTimesheet(totalHours, { hideZeroHours = true } = {}) {
    const currentLocale = pyToJsLocale(document.documentElement.getAttribute("lang")) || "en-US";
    const totalMinutes = Math.round(totalHours * 60);
    const hoursCount = Math.floor(totalMinutes / 60);
    const minutesCount = totalMinutes % 60;

    const formatter = new Intl.DurationFormat(currentLocale, {
        hours: "numeric",
        minutes: "2-digit",
        style: "narrow",
    });

    const parts = formatter.formatToParts({ hours: hoursCount, minutes: minutesCount });
    const hours = parts.find((p) => p.unit === "hour" && p.type === "integer").value;
    const minutes = parts.find((p) => p.unit === "minute" && p.type === "integer").value;

    if (hideZeroHours && hoursCount === 0) {
        return _t("%(minutes)sm", { minutes });
    }
    return _t("%(hours)sh %(minutes)sm", { hours, minutes });
}
