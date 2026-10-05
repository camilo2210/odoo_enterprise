import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async fetchSlots(paymentMethod, order, search = "", offset = 0, opts = {}) {
        if (paymentMethod.type !== "resource") {
            return [];
        }
        let resourceToCheck = paymentMethod.resource_ids.map((o) => o.id);
        if (paymentMethod.resource_ids.length === 0) {
            resourceToCheck = this.models["resource.resource"].map((o) => o.id);
        }
        const getPresetPlanningSlotsArgs = [resourceToCheck, this.config.id];
        const kwargs = {
            partner_id: order.getPartner()?.id,
            search: search,
            offset: offset,
            ...opts,
        };
        const data = await this.data.callRelated(
            "resource.resource",
            "get_planning_slots",
            getPresetPlanningSlotsArgs,
            kwargs
        );
        return data["planning.slot"];
    },
});
