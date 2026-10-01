import { patch } from "@web/core/utils/patch";
import { OboxScale } from "@obox_point_of_sale/app/utils/scale/obox_scale";
import { resolveDeviceAddress } from "@obox_pos_mobile/app/utils/device_address";

patch(OboxScale.prototype, {
    get address() {
        return this._localAddress ?? super.address;
    },

    async _readWeight() {
        this._localAddress ??= await resolveDeviceAddress(super.address);
        return super._readWeight(...arguments);
    },
});
