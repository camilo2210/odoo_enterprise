import { PosDataPlugin } from "@point_of_sale/app/plugins/pos_data_plugin";
import { patch } from "@web/core/utils/patch";

patch(PosDataPlugin.prototype, {
    /**
     * @override
     */
    async preLoadData(data) {
        const loadData = await super.preLoadData(data);
        const config = this.models["pos.config"].get(odoo.pos_config_id);
        if (!loadData || !config?.module_pos_urban_piper) {
            return loadData;
        }
        if (loadData["pos.order"]) {
            loadData["pos.order"] = loadData["pos.order"].filter((o) => !o.delivery_identifier);
        }
        if (loadData["pos.order.line"]) {
            loadData["pos.order.line"] = loadData["pos.order.line"].filter(
                (ol) => ol.order_id && !ol.order_id.delivery_identifier
            );
        }
        return loadData;
    },
});
