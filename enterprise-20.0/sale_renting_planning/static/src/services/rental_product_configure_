import { registry } from "@web/core/registry";

/**
 * Tracks which sale.order.line IDs have already had their product configuration
 * modal shown during the current browser session. This avoids using a DB field
 * solely to manage a one-time UI trigger.
 */
const shownModals = new Set();

registry.category("services").add("rental_product_configure", {
    start() {
        return {
            hasShown: (lineId) => shownModals.has(lineId),
            markShown: (lineId) => lineId && shownModals.add(lineId),
        };
    },
});
