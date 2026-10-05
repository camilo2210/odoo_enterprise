import { DataServiceOptions } from "@point_of_sale/app/models/data_service_options";
import { patch } from "@web/core/utils/patch";

patch(DataServiceOptions.prototype, {
    get cascadeDeleteModels() {
        return [...super.cascadeDeleteModels, "pos.prep.line", "pos.order"];
    },
});
