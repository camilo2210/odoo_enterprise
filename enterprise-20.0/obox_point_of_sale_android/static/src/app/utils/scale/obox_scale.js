import { patch } from "@web/core/utils/patch";
import { OboxScale } from "@obox_point_of_sale/app/utils/scale/obox_scale";

patch(OboxScale.prototype, {
    get address() {
        // The address includes the port the box listens on, if any.
        const { local_address } = this._scaleDevice.obox_id;
        return local_address ? `http://${local_address}` : super.address;
    },
});
