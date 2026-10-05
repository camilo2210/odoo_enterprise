import { patch } from "@web/core/utils/patch";
import { MrpDisplayAction } from "@mrp_workorder/mrp_display/mrp_display_action";

patch(MrpDisplayAction.prototype, {
    get fieldsStructure() {
        const result = super.fieldsStructure;
        result["quality.check"].push("obox_device_identifier");
        result["quality.check"].push("obox_ip");
        return result;
    },
});
