import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";

export class PosPrepOrder extends Base {
    static pythonModel = "pos.prep.order";

    get order() {
        return this.pos_order_id;
    }
}

registry.category("pos_available_models").add(PosPrepOrder.pythonModel, PosPrepOrder);
