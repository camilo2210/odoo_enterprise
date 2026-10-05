import { EventBus, Plugin, useListener } from "@odoo/owl";

export class MapTimelineCommunicationPlugin extends Plugin {
    bus = new EventBus();
    foldedGroupIds = new Set();
    shiftsToScheduleFolded = false;

    /**
     * @param {Function} handler
     */
    onNotify(handler) {
        useListener(this.bus, "MAP_TIMELINE:notify", handler);
    }

    notify() {
        this.bus.trigger("MAP_TIMELINE:notify");
    }

    /**
     * @param {Function} handler
     */
    onFoldedGroupsChange(handler) {
        useListener(this.bus, "MAP_TIMELINE:folded_group_change", handler);
    }

    /**
     * @param {Set<string>} groupIds
     */
    setFoldedGroups(groupIds) {
        this.foldedGroupIds = new Set(groupIds);
        this.bus.trigger("MAP_TIMELINE:folded_group_change");
    }

    /**
     * @param {Number} resId
     */
    isFolded(resId) {
        return this.foldedGroupIds.has(String(resId));
    }

    /**
     * @param {Boolean} folded
     */
    setShiftsToScheduleFolded(folded) {
        if (this.shiftsToScheduleFolded === folded) {
            return;
        }
        this.shiftsToScheduleFolded = folded;
        this.bus.trigger("MAP_TIMELINE:folded_group_change");
    }

    /**
     * @param {Function} handler
     */
    onHighlight(handler) {
        useListener(this.bus, "MAP_TIMELINE:highlight_records", ({ detail }) => handler(detail));
    }

    /**
     * @param {Number[]} recordIds
     * @param {Boolean} on
     */
    highlight(recordIds, on) {
        this.bus.trigger("MAP_TIMELINE:highlight_records", { recordIds, on });
    }
}
