export function getAwRuleIcon(eventType) {
    if (!eventType) {
        return "";
    }
    const icons = {
        gmail_activity: { icon: "mail", class: "text-dark-lavender" },
        email: { icon: "mail", class: "text-dark-lavender" },
        call: { icon: "phone", class: "oi-filled text-meadow-green" },
        messaging: { icon: "chat_bubble", class: "text-sky-blue" },
        meeting: { icon: "calendar_today", class: "oi-filled text-hot-pink" },
        document: { icon: "description", class: "text-persimmon" },
        spreadsheet: { icon: "table_chart", class: "text-chartreuse" },
        presentation: { icon: "slideshow", class: "text-amber" },
        development: { icon: "code", class: "text-dark" },
        odoo: { icon: "oi_odoo", class: "text-primary" },
        planning: { icon: "checklist", class: "text-crimson" },
        afk: { icon: "dark_mode" },
        other: { icon: "more_horiz", class: "text-muted" },
    };
    return icons[eventType] || "more_horiz";
}

export function purgeOldCacheKeys(cacheObj, extractDateFn, daysToKeep) {
    const threshold = luxon.DateTime.now().minus({ days: daysToKeep }).startOf("day");
    let hasChanges = false;
    for (const key of Object.keys(cacheObj)) {
        try {
            const dateStr = extractDateFn(key);
            if (dateStr) {
                const eventDate = luxon.DateTime.fromISO(dateStr);
                if (!eventDate.isValid || eventDate < threshold) {
                    delete cacheObj[key];
                    hasChanges = true;
                }
            }
        } catch {
            delete cacheObj[key];
            hasChanges = true;
        }
    }
    return hasChanges;
}
