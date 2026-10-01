import { PosDataPlugin } from "@point_of_sale/app/plugins/pos_data_plugin";
import { patch } from "@web/core/utils/patch";

patch(PosDataPlugin.prototype, {
    setup() {
        this.custom = {};
        super.setup();
    },
});
