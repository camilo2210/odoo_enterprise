import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";

patch(Navbar.prototype, {
    get showOderTrackerDropdown() {
        return (
            super.showOderTrackerDropdown ||
            (this.pos.config.module_pos_urban_piper && this.pos.config.urbanpiper_store_id)
        );
    },

    get shouldDisplayPresetTime() {
        return !this.pos.getOrder()?.isDeliveryOrder && super.shouldDisplayPresetTime;
    },
});
